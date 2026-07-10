"""
레딧 명소명 키워드 검색 크롤러 (공식 API 키 불필요, 공개 search.json 사용)

설치:
    pip install requests

사용법:
    python reddit_keyword_crawler.py

동작:
    KEYWORDS 의 각 명소명으로 레딧 전체(사이트 전역) 검색을 실행해
    최신순으로 POSTS_PER_KEYWORD개 게시물을 가져와 OUTPUT_CSV 에 저장한다.

주의:
    비공식(로그인 없는 공개 JSON) 엔드포인트라 요청이 많으면 레이트리밋(429)에
    걸릴 수 있다. 걸릴 경우 SLEEP_BETWEEN_CALLS_SEC 값을 늘려서 재시도할 것.
"""

from __future__ import annotations

import csv
import time
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

POSTS_PER_KEYWORD = 25
SLEEP_BETWEEN_CALLS_SEC = 2.0
OUTPUT_CSV = Path("reddit_posts.csv")
HEADERS = {"User-Agent": "keyword-research-bot/1.0"}


def search_reddit(keyword: str, limit: int) -> list[dict]:
    url = (
        "https://www.reddit.com/search.json"
        f"?q={quote(keyword)}&sort=new&limit={limit}"
    )
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return [c["data"] for c in data.get("data", {}).get("children", [])]


def main() -> None:
    rows: list[dict] = []

    for keyword in KEYWORDS:
        print(f"[검색] {keyword}")
        try:
            posts = search_reddit(keyword, POSTS_PER_KEYWORD)
        except Exception as e:
            print(f"  ! 검색 실패: {e}")
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
            continue

        for p in posts:
            rows.append({
                "keyword": keyword,
                "subreddit": p.get("subreddit"),
                "title": p.get("title", ""),
                "selftext": (p.get("selftext") or "").replace("\n", " ")[:1000],
                "author": p.get("author"),
                "score": p.get("score"),
                "num_comments": p.get("num_comments"),
                "created_utc": p.get("created_utc"),
                "url": f"https://www.reddit.com{p.get('permalink', '')}",
            })

        print(f"  -> {len(posts)}건")
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    if rows:
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[완료] {len(rows)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 게시물 없음")


if __name__ == "__main__":
    main()
