"""
네이버 블로그 본문/공감(좋아요)수/댓글수 크롤러 (Playwright 사용)

설치:
    pip install playwright pandas openpyxl
    playwright install chromium

사용법:
    python 1_search_naver_blog.py 를 먼저 실행해 INPUT_CSV 를 만든 뒤
    python 2_crawl_naver_blog_detail.py 실행

동작:
    INPUT_CSV(키워드/채널/제목/작성자/작성일/URL)에 있는 각 URL을 모바일
    블로그 페이지(m.blog.naver.com)로 열어 본문, 공감수(좋아요 대체),
    댓글수를 추출해 OUTPUT_XLSX 에 저장한다.

    URL 수가 많을 경우(수만 건) 몇 시간씩 걸릴 수 있으므로, 처리할 때마다
    CHECKPOINT_CSV 에 한 건씩 바로 append해 중간에 중단돼도 그동안 수집한
    데이터는 보존된다. 스크립트를 다시 실행하면 CHECKPOINT_CSV 에 이미
    있는 URL은 건너뛰고 이어서 진행한다. 끝까지 완료되면 CHECKPOINT_CSV
    전체 내용을 OUTPUT_XLSX 로도 저장한다.

주의 (조회수 관련):
    네이버 블로그는 대부분 포스트 조회수를 블로그 주인에게만 공개하고
    방문자에게는 보여주지 않는다. 블로거가 별도로 방문자 위젯을 켜둔
    경우에만 페이지에서 조회수가 노출되므로, 대부분의 게시글에서
    "조회수" 값은 공란으로 남는다. 이는 스크립트 결함이 아니라 네이버
    블로그 자체의 공개 정책 때문이다.

주의 (선택자 관련):
    블로그 스킨(테마)마다 HTML 구조가 달라 공감수/댓글수 선택자가
    안 맞을 수 있다. 여러 선택자를 순서대로 시도하도록 만들었지만,
    실제 실행 후 값이 계속 비어 있는 스킨이 있다면 해당 블로그 글을
    직접 열어 선택자를 추가해야 한다.
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

INPUT_CSV = "naver_blog_urls_202604_202606.csv"
CHECKPOINT_CSV = "naver_blog_detail_202604_202606_checkpoint.csv"
OUTPUT_XLSX = "naver_blog_detail_202604_202606.xlsx"

FIELDNAMES = [
    "키워드", "채널", "제목", "본문", "작성일", "작성자",
    "조회수", "좋아요수", "댓글수", "URL",
]

BODY_SELECTORS = [
    "div.se-main-container",   # 스마트에디터 ONE/3
    "div#postViewArea",        # 구 스킨
    "div.post_ct",
]
LIKE_SELECTORS = [
    "em.u_cnt._count",
    "span.u_cnt._count",
    "a.btn_like .num",
    ".area_sympathy .u_cnt",
]
COMMENT_SELECTORS = [
    "a#commentCount",
    ".area_comment .num",
    "span.__comment_count",
]
VIEW_SELECTORS = [
    ".area_view_cnt .count",
    ".visit_cnt .num",
]


def to_mobile_url(url: str) -> str:
    return url.replace("://blog.naver.com", "://m.blog.naver.com")


def extract_text(page, selectors: list[str]) -> str:
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el:
                text = el.inner_text().strip()
                if text:
                    return text
        except Exception:
            continue
    return ""


def extract_number(page, selectors: list[str]) -> str:
    text = extract_text(page, selectors)
    digits = re.sub(r"[^\d]", "", text)
    return digits


def crawl_one(page, url: str) -> dict:
    mobile_url = to_mobile_url(url)
    page.goto(mobile_url, timeout=20000, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    body = extract_text(page, BODY_SELECTORS)
    like_count = extract_number(page, LIKE_SELECTORS)
    comment_count = extract_number(page, COMMENT_SELECTORS)
    view_count = extract_number(page, VIEW_SELECTORS)

    return {
        "본문": body,
        "좋아요수": like_count,
        "댓글수": comment_count,
        "조회수": view_count,
    }


def main() -> None:
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        print(f"[오류] {INPUT_CSV} 파일이 없습니다. 1_search_naver_blog.py 를 먼저 실행하세요.")
        return

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    print(f"[📋] 전체 URL {len(df)}개")

    checkpoint_path = Path(CHECKPOINT_CSV)
    done_urls: set[str] = set()
    if checkpoint_path.exists():
        prev = pd.read_csv(checkpoint_path, encoding="utf-8-sig")
        done_urls = set(prev["URL"].dropna())
        print(f"[⏩] 이전에 저장된 {len(done_urls)}건은 건너뜀 (이어서 진행)")
    else:
        with checkpoint_path.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    todo = df[~df["URL"].isin(done_urls)]
    print(f"[📋] 이번에 크롤링할 URL {len(todo)}개\n")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )

        with checkpoint_path.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)

            try:
                for idx, row in todo.iterrows():
                    url = row["URL"]
                    print(f"\n[{idx + 1}/{len(df)}] {row.get('제목', '')[:40]!r}")
                    try:
                        detail = crawl_one(page, url)
                        body_len = len(detail["본문"])
                        print(f"  본문 {body_len}자 / 좋아요 {detail['좋아요수'] or '-'} / 댓글 {detail['댓글수'] or '-'}"
                              + ("  ⚠️ 본문 비어있음(선택자 확인 필요)" if body_len == 0 else ""))
                    except Exception as e:
                        print(f"  ! 크롤링 실패: {e}")
                        detail = {"본문": f"크롤링 실패: {e}", "좋아요수": "", "댓글수": "", "조회수": ""}

                    writer.writerow({
                        "키워드": row.get("키워드", ""),
                        "채널": row.get("채널", "네이버블로그"),
                        "제목": row.get("제목", ""),
                        "본문": detail["본문"],
                        "작성일": row.get("작성일", ""),
                        "작성자": row.get("작성자", ""),
                        "조회수": detail["조회수"],
                        "좋아요수": detail["좋아요수"],
                        "댓글수": detail["댓글수"],
                        "URL": url,
                    })
                    f.flush()  # 중단돼도 방금 쓴 줄까지는 파일에 남도록 즉시 반영
                    time.sleep(1.0)
            except KeyboardInterrupt:
                print("\n[⏸️] 사용자 중단 감지. 지금까지 저장된 내용으로 마무리합니다.")

        browser.close()

    out_df = pd.read_csv(checkpoint_path, encoding="utf-8-sig")
    out_df.to_excel(OUTPUT_XLSX, index=False)
    print(f"\n[💾] 총 {len(out_df)}건 저장 -> {Path(OUTPUT_XLSX).resolve()}")


if __name__ == "__main__":
    main()
