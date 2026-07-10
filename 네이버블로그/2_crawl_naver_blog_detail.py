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

import re
import time
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

INPUT_CSV = "naver_blog_urls_202604_202606.csv"
OUTPUT_XLSX = "naver_blog_detail_202604_202606.xlsx"

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
    print(f"[📋] 크롤링할 URL {len(df)}개")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )

        for idx, row in df.iterrows():
            url = row["URL"]
            print(f"\n[{idx + 1}/{len(df)}] {row.get('제목', '')[:40]!r}")
            try:
                detail = crawl_one(page, url)
            except Exception as e:
                print(f"  ! 크롤링 실패: {e}")
                detail = {"본문": f"크롤링 실패: {e}", "좋아요수": "", "댓글수": "", "조회수": ""}

            results.append({
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
            time.sleep(1.0)

        browser.close()

    out_df = pd.DataFrame(results, columns=[
        "키워드", "채널", "제목", "본문", "작성일", "작성자",
        "조회수", "좋아요수", "댓글수", "URL",
    ])
    out_df.to_excel(OUTPUT_XLSX, index=False)
    print(f"\n[💾] {len(out_df)}건 저장 -> {Path(OUTPUT_XLSX).resolve()}")


if __name__ == "__main__":
    main()
