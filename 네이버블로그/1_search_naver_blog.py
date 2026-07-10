"""
네이버 블로그 명소명 키워드 검색 (공식 네이버 검색 API 사용)

설치:
    pip install requests

환경변수 (네이버 개발자센터 https://developers.naver.com 에서 발급):
    NAVER_CLIENT_ID
    NAVER_CLIENT_SECRET

사용법:
    export NAVER_CLIENT_ID="..."
    export NAVER_CLIENT_SECRET="..."
    python 1_search_naver_blog.py

동작:
    KEYWORDS 의 각 명소명으로 네이버 블로그 검색 API(sort=date, 최신순)를
    페이지네이션하며 호출해 START_DATE~END_DATE 기간에 작성된 글만 골라
    OUTPUT_CSV 에 저장한다. (검색 API는 키워드당 최대 1000건까지만 조회 가능)

    이 단계에서는 제목/링크/작성자(블로거)/작성일만 확보된다. 본문과
    조회수/좋아요수/댓글수는 2_crawl_naver_blog_detail.py 에서 실제 게시글
    페이지를 열어 수집한다.
"""

from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from pathlib import Path

import requests

KEYWORDS = [
    "구름산산림욕장",
    "북한산국립공원",
    "임진각",
    "용문산",
    "소요산",
    "자라섬캠핑장",
    "한탄강오토캠핑장",
    "남한강자전거길",
    "안산갈대습지공원",
    "의정부실내빙상장",
    "에버랜드",
    "서울대공원",
    "서울랜드",
    "허브아일랜드",
    "캐리비안베이",
    "한국민속촌",
    "아침고요수목원",
    "안성팜랜드",
    "경기도립물향기수목원",
    "쁘띠프랑스",
    "국립현대미술관 과천관",
    "광명동굴",
    "시화호조력발전소",
    "아쿠아플라넷일산",
    "한국잡월드",
    "경기도어린이박물관",
    "양평양떼목장",
    "바라산자연휴양림",
    "행주산성",
    "남한산성행궁",
    "포천아트밸리",
    "헤이리예술마을",
    "수원화성박물관",
    "융건릉",
    "세종대왕 영릉",
    "장릉",
    "동구릉",
    "다산유적지",
    "통일전망대",
    "신구대학교식물원",
    "세미원",
    "시흥갯골생태공원",
    "수리산입구",
    "관악산자연학습장",
    "대부해솔길",
    "잣향기푸른숲",
    "비둘기낭폭포",
    "두물머리",
    "마장호수",
    "포천한탄강하늘다리",
    "재인폭포",
    "화성행궁",
    "제3땅굴",
    "송학김전시관",
    "가평레일파크",
    "대장금파크",
    "스타필드수원",
]

CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "").strip()
SEARCH_URL = "https://openapi.naver.com/v1/search/blog.json"

# 수집 기간 (postdate 형식: YYYYMMDD)
START_DATE = "20260401"
END_DATE = "20260630"

DISPLAY_PER_PAGE = 100
MAX_START = 1000  # 네이버 검색 API 제약: start는 1~1000까지만 허용
SLEEP_BETWEEN_CALLS_SEC = 0.5
OUTPUT_CSV = Path("naver_blog_urls_202604_202606.csv")

FIELDNAMES = ["키워드", "채널", "제목", "작성자", "작성일", "URL"]


def strip_tags(text: str) -> str:
    return (text or "").replace("<b>", "").replace("</b>", "")


def search_blog_in_range(keyword: str) -> list[dict]:
    rows: list[dict] = []
    headers = {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }

    for start in range(1, MAX_START + 1, DISPLAY_PER_PAGE):
        params = {
            "query": keyword,
            "display": DISPLAY_PER_PAGE,
            "start": start,
            "sort": "date",  # 최신순
        }
        resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            print(f"    ! HTTP {resp.status_code}: {resp.text[:200]}")
            break

        items = resp.json().get("items", [])
        if not items:
            break

        reached_before_start = False
        for item in items:
            postdate = item.get("postdate", "")  # 예: "20260615"

            if postdate > END_DATE:
                continue  # 기간보다 최신 -> 건너뜀
            if postdate < START_DATE:
                reached_before_start = True
                continue  # 기간보다 과거 -> 건너뜀 (date 정렬이므로 이후도 계속 과거)

            rows.append({
                "키워드": keyword,
                "채널": "네이버블로그",
                "제목": strip_tags(item.get("title", "")),
                "작성자": item.get("bloggername", ""),
                "작성일": f"{postdate[:4]}-{postdate[4:6]}-{postdate[6:8]}" if len(postdate) == 8 else postdate,
                "URL": item.get("link", ""),
            })

        if reached_before_start or len(items) < DISPLAY_PER_PAGE:
            break

        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    return rows


def main() -> None:
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[오류] 환경변수 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 을 설정해주세요.")
        return

    print(f"[수집 기간] {START_DATE} ~ {END_DATE}")
    print(f"[대상 키워드] {len(KEYWORDS)}개\n")

    rows: list[dict] = []
    for keyword in KEYWORDS:
        print(f"[검색] {keyword}")
        try:
            found = search_blog_in_range(keyword)
        except Exception as e:
            print(f"  ! 검색 실패: {e}")
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
            continue

        print(f"  -> {len(found)}건 (기간 내)")
        rows.extend(found)
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    if rows:
        rows = list({r["URL"]: r for r in rows if r.get("URL")}.values())
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[완료] {len(rows)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 게시물 없음")


if __name__ == "__main__":
    main()
