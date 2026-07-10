"""
레딧 명소명 키워드 검색 크롤러 (공식 API 키 불필요, 공개 search.json 사용)

설치:
    pip install requests

사용법:
    python reddit_keyword_crawler.py

동작:
    KEYWORDS 의 각 명소명으로 레딧 전체(사이트 전역) 검색을 실행해,
    START_DATE ~ END_DATE 기간에 작성된 게시물만 골라 OUTPUT_CSV 에 저장한다.
    최신순(new) 정렬로 페이지네이션하며 게시물 작성일이 START_DATE 이전으로
    내려가면 해당 키워드 수집을 멈춘다.

수집 항목:
    제목, 본문, 작성일, 작성자, 좋아요수, 댓글수, URL
    (조회수는 레딧 API가 제공하지 않아 공란으로 남긴다. 좋아요수는 레딧의
    추천(score, 순 업보트)수로 대체한다.)

주의:
    비공식(로그인 없는 공개 JSON) 엔드포인트라 요청이 많으면 레이트리밋(429)에
    걸릴 수 있다. 걸릴 경우 SLEEP_BETWEEN_CALLS_SEC 값을 늘려서 재시도할 것.
"""

from __future__ import annotations

import csv
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

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

# 수집 기간 (UTC 기준)
START_DATE = "2026-04-01T00:00:00+00:00"
END_DATE = "2026-06-30T23:59:59+00:00"
START_TS = datetime.fromisoformat(START_DATE).timestamp()
END_TS = datetime.fromisoformat(END_DATE).timestamp()

PAGE_SIZE = 100
MAX_PAGES_PER_KEYWORD = 30
SLEEP_BETWEEN_CALLS_SEC = 2.0
MAX_RETRIES = 3
OUTPUT_CSV = Path("reddit_posts_202604_202606.csv")
HEADERS = {"User-Agent": "keyword-research-bot/1.0"}

FIELDNAMES = [
    "키워드", "채널", "제목", "본문", "작성일", "작성자",
    "조회수", "좋아요수", "댓글수", "URL",
]


def fetch_page(keyword: str, after: str | None) -> dict:
    url = (
        "https://www.reddit.com/search.json"
        f"?q={quote(keyword)}&sort=new&limit={PAGE_SIZE}"
    )
    if after:
        url += f"&after={after}"

    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 429:
            wait = SLEEP_BETWEEN_CALLS_SEC * attempt * 2
            print(f"    ! 429 레이트리밋, {wait:.0f}초 대기 후 재시도 ({attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()

    raise RuntimeError("최대 재시도 횟수 초과 (429)")


def search_reddit_in_range(keyword: str) -> list[dict]:
    """START_DATE~END_DATE 기간의 게시물만 골라 반환한다."""
    rows: list[dict] = []
    after = None

    for page in range(MAX_PAGES_PER_KEYWORD):
        try:
            data = fetch_page(keyword, after)
        except Exception as e:
            print(f"    ! 페이지 {page + 1} 요청 실패: {e}")
            break

        children = data.get("data", {}).get("children", [])
        if not children:
            break

        reached_before_start = False
        for c in children:
            p = c["data"]
            created = p.get("created_utc", 0)

            if created > END_TS:
                continue  # 기간보다 최신 -> 건너뜀
            if created < START_TS:
                reached_before_start = True
                continue  # 기간보다 과거 -> 건너뜀 (new 정렬이므로 이후도 계속 과거)

            rows.append({
                "키워드": keyword,
                "채널": "레딧",
                "제목": p.get("title", ""),
                "본문": (p.get("selftext") or "").replace("\n", " "),
                "작성일": datetime.fromtimestamp(created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                "작성자": p.get("author"),
                "조회수": "",  # 레딧 API는 조회수를 제공하지 않음
                "좋아요수": p.get("score"),
                "댓글수": p.get("num_comments"),
                "URL": f"https://www.reddit.com{p.get('permalink', '')}",
            })

        after = data.get("data", {}).get("after")
        if reached_before_start or not after:
            break

        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    return rows


def main() -> None:
    print(f"[수집 기간] {START_DATE} ~ {END_DATE}")
    print(f"[대상 키워드] {len(KEYWORDS)}개\n")

    rows: list[dict] = []

    for keyword in KEYWORDS:
        print(f"[검색] {keyword}")
        try:
            found = search_reddit_in_range(keyword)
        except Exception as e:
            print(f"  ! 검색 실패: {e}")
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
            continue

        print(f"  -> {len(found)}건 (기간 내)")
        rows.extend(found)
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    if rows:
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[완료] {len(rows)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 게시물 없음")


if __name__ == "__main__":
    main()
