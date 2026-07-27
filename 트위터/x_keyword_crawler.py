"""
X(트위터) 명소명 키워드 검색 크롤러 (공식 API v2 사용, Bearer Token 필요)

설치:
    pip install requests

환경변수:
    TWITTER_BEARER_TOKEN  - X 개발자 포털에서 발급받은 Bearer Token

사용법:
    export TWITTER_BEARER_TOKEN="..."
    python x_keyword_crawler.py

동작:
    KEYWORDS 의 각 명소명으로 전체 아카이브 검색(full-archive search) API를
    호출해, START_DATE~END_DATE(2026-04-01~2026-06-30) 기간의 리트윗 제외
    트윗을 키워드당 TWEETS_PER_KEYWORD개까지 수집, OUTPUT_CSV 에 저장한다.

주의:
    - /2/tweets/search/all(전체 아카이브 검색)은 Pro/Enterprise/Academic 등
      유료·상위 티어에서만 열려 있다. 무료/Basic 티어의 recent search는
      "최근 7일" 데이터만 제공하므로 2026-04~06 과거 데이터는 조회할 수
      없다 (해당 티어라면 이 스크립트를 실행해도 403/401이 발생한다).
    - 요청당 max_results는 10~100, 티어별 rate limit이 있으니 SLEEP_BETWEEN_CALLS_SEC 조절.
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

BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "").strip().strip('"')
SEARCH_URL = "https://api.twitter.com/2/tweets/search/all"

# 수집 기간 (X API는 RFC3339 형식 요구)
START_DATE = "2026-04-01T00:00:00Z"
END_DATE = "2026-06-30T23:59:59Z"

TWEETS_PER_KEYWORD = 50
SLEEP_BETWEEN_CALLS_SEC = 2.0

# 테스트 모드: True면 KEYWORDS의 첫 번째 키워드만 수집한다.
# 전체 키워드로 돌리려면 False로 바꿀 것.
TEST_MODE = True
OUTPUT_CSV = Path("x_posts_test.csv" if TEST_MODE else "x_posts_202604_202606.csv")


def fetch_tweets(keyword: str, count: int) -> list[dict]:
    query = f"\"{keyword}\" -is:retweet"
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}
    params = {
        "query": query,
        "max_results": min(max(count, 10), 100),
        "sort_order": "recency",
        "start_time": START_DATE,
        "end_time": END_DATE,
        "tweet.fields": "created_at,lang,public_metrics,text",
        "expansions": "author_id",
        "user.fields": "name,username,public_metrics,verified",
    }

    rows: list[dict] = []
    next_token = None
    collected = 0

    while collected < count:
        if next_token:
            params["next_token"] = next_token

        try:
            resp = requests.get(SEARCH_URL, headers=headers, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"    ! HTTP {resp.status_code}: {resp.text[:200]}")
                break

            data = resp.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            for tweet in tweets:
                metrics = tweet.get("public_metrics", {})
                author = users.get(tweet.get("author_id", ""), {})
                author_metrics = author.get("public_metrics", {})

                rows.append({
                    "keyword": keyword,
                    "tweet_id": tweet.get("id"),
                    "created_at": tweet.get("created_at"),
                    "text": (tweet.get("text") or "").replace("\n", " "),
                    "lang": tweet.get("lang"),
                    "like_count": metrics.get("like_count", 0) or 0,
                    "retweet_count": metrics.get("retweet_count", 0) or 0,
                    "reply_count": metrics.get("reply_count", 0) or 0,
                    "impression_count": metrics.get("impression_count", 0) or 0,
                    "user_name": author.get("username"),
                    "user_display_name": author.get("name"),
                    "user_followers": author_metrics.get("followers_count", 0) or 0,
                    "tweet_url": f"https://x.com/{author.get('username')}/status/{tweet.get('id')}",
                    "collected_at": datetime.utcnow().isoformat(),
                })

            collected += len(tweets)
            next_token = data.get("meta", {}).get("next_token")
            if not next_token or len(tweets) == 0:
                break

            time.sleep(1)

        except Exception as e:
            print(f"    ! 오류: {e}")
            break

    return rows


def main() -> None:
    if not BEARER_TOKEN:
        print("[오류] 환경변수 TWITTER_BEARER_TOKEN을 설정해주세요.")
        return

    target_keywords = KEYWORDS[:1] if TEST_MODE else KEYWORDS

    print("[X(트위터) 키워드 크롤링 시작]" + (" (테스트 모드)" if TEST_MODE else ""))
    print(f"[수집 기간] {START_DATE} ~ {END_DATE}")
    print(f"[대상 키워드] {len(target_keywords)}개\n")

    start = time.time()
    rows: list[dict] = []

    for keyword in target_keywords:
        print(f"  [검색] {keyword}")
        try:
            found = fetch_tweets(keyword, TWEETS_PER_KEYWORD)
            print(f"    -> {len(found)}건")
            rows.extend(found)
        except Exception as e:
            print(f"    ! [{keyword}] 오류: {e}")
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    if rows:
        rows = list({r["tweet_id"]: r for r in rows if r.get("tweet_id")}.values())
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[완료] {len(rows)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 트윗 없음")

    elapsed = time.time() - start
    print(f"소요 시간: {elapsed:.1f}초")


if __name__ == "__main__":
    main()
