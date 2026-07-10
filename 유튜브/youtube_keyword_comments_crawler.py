"""
유튜브 명소명 키워드 댓글 크롤러 (공식 API 키 불필요, yt-dlp 사용)

설치:
    pip install yt-dlp

사용법:
    python youtube_keyword_comments_crawler.py

동작:
    KEYWORDS 의 각 명소명으로 유튜브를 검색해 상위 VIDEOS_PER_KEYWORD개 영상을 찾고,
    각 영상의 댓글을 MAX_COMMENTS_PER_VIDEO개까지 수집해 OUTPUT_CSV 에 저장한다.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import yt_dlp

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

VIDEOS_PER_KEYWORD = 5
MAX_COMMENTS_PER_VIDEO = 100
SLEEP_BETWEEN_CALLS_SEC = 1.0
OUTPUT_CSV = Path("youtube_comments.csv")

SEARCH_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": True,
    "skip_download": True,
}

COMMENT_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "getcomments": True,
    "extractor_args": {"youtube": {"max_comments": [str(MAX_COMMENTS_PER_VIDEO)]}},
}


def search_videos(keyword: str, limit: int) -> list[dict]:
    query = f"ytsearch{limit}:{keyword}"
    with yt_dlp.YoutubeDL(SEARCH_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        return info.get("entries", []) or []


def fetch_comments(video_id: str) -> list[dict]:
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(COMMENT_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
        return info.get("comments", []) or []


def main() -> None:
    rows: list[dict] = []

    for keyword in KEYWORDS:
        print(f"[검색] {keyword}")
        try:
            videos = search_videos(keyword, VIDEOS_PER_KEYWORD)
        except Exception as e:
            print(f"  ! 검색 실패: {e}")
            continue

        for video in videos:
            video_id = video.get("id")
            title = video.get("title", "")
            if not video_id:
                continue

            print(f"  [댓글 수집] {title[:40]!r} ({video_id})")
            try:
                comments = fetch_comments(video_id)
            except Exception as e:
                print(f"    ! 댓글 수집 실패: {e}")
                continue

            for c in comments:
                rows.append({
                    "keyword": keyword,
                    "video_id": video_id,
                    "video_title": title,
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "comment_id": c.get("id"),
                    "author": c.get("author"),
                    "comment_text": (c.get("text") or "").replace("\n", " "),
                    "like_count": c.get("like_count"),
                    "published_time": c.get("timestamp"),
                    "is_reply": c.get("parent") != "root",
                })
            time.sleep(SLEEP_BETWEEN_CALLS_SEC)
        time.sleep(SLEEP_BETWEEN_CALLS_SEC)

    if rows:
        with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n[완료] {len(rows)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 댓글 없음")


if __name__ == "__main__":
    main()
