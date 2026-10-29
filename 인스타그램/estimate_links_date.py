"""
estimate_links_date.py
인스타그램 게시물 URL의 짧은 코드(shortcode)만으로 작성일을 "추정"한다.
페이지를 직접 열지 않고도 대략적인 날짜를 알 수 있다는 비공식 역공학
정보(media_id 상위 비트에 생성 시각이 인코딩돼 있음)를 이용한다.

⚠️ 주의: 이건 인스타그램 공식 기능이 아니라 커뮤니티에서 역공학한 방식이라
        100% 정확하다는 보장이 없다. 반드시 --validate 로 먼저 검증할 것.

사용법:
    1) 검증 (이미 실제 작성일을 아는 instagram_detail_checkpoint.csv로 정확도 확인)
       python estimate_links_date.py --validate

    2) 필터링 (검증 결과가 믿을만하면, instagram_links.csv를 기간으로 미리 걸러서
       instagram_links_filtered.csv 생성 -> 2_crawl_instagram_detail.py의
       INPUT_CSV를 이 파일로 바꿔서 돌리면 안 봐도 될 링크를 건너뛸 수 있다)
       python estimate_links_date.py --filter
"""

from __future__ import annotations

import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

LINKS_CSV = Path("instagram_links.csv")
CHECKPOINT_CSV = Path("instagram_detail_checkpoint.csv")
FILTERED_OUTPUT_CSV = Path("instagram_links_filtered.csv")

# 실제 수집 기간보다 여유를 둬서, 추정 오차로 진짜 기간 안 게시물을 놓치지
# 않도록 한다. 검증 결과(541건 기준) 오차 7일 이내가 97.0%였다. 즉 7일
# 버퍼를 쓰면 통계적으로 약 3%는 놓칠 위험이 있다는 뜻 — 시간 단축을
# 우선해 이 값을 쓰기로 함(더 안전하게 하려면 숫자를 늘릴 것).
#
# 10월로 추정되는(= 수집 기간보다 최신인) 게시물이 너무 많아서, 뒤쪽
# 버퍼는 없애고(END_BUFFER_DAYS=0, 9월 30일에서 끊음) 앞쪽(6월 방향)도
# 돌릴 시간이 부족해 0으로 없앰 — 정확히 7/1~9/30만 남긴다.
START_BUFFER_DAYS = 0
END_BUFFER_DAYS = 0
START_DATE = datetime(2026, 7, 1, tzinfo=timezone.utc) - timedelta(days=START_BUFFER_DAYS)
END_DATE = datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc) + timedelta(days=END_BUFFER_DAYS)

# 인스타그램 media_id 인코딩에 쓰이는 커스텀 base64 알파벳
ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
ALPHABET_INDEX = {ch: i for i, ch in enumerate(ALPHABET)}

# 인스타그램 자체 epoch(기준 시각), 밀리초 단위 (2011-08-24 경)
INSTAGRAM_EPOCH_MS = 1314220021721

SHORTCODE_RE = re.compile(r"/(?:p|reel)/([A-Za-z0-9_-]+)")


def extract_shortcode(url: str) -> str | None:
    m = SHORTCODE_RE.search(url or "")
    return m.group(1) if m else None


def shortcode_to_media_id(shortcode: str) -> int | None:
    media_id = 0
    for ch in shortcode:
        if ch not in ALPHABET_INDEX:
            return None
        media_id = media_id * 64 + ALPHABET_INDEX[ch]
    return media_id


def estimate_datetime(url: str) -> datetime | None:
    shortcode = extract_shortcode(url)
    if not shortcode:
        return None
    media_id = shortcode_to_media_id(shortcode)
    if media_id is None:
        return None
    # 하위 23비트(서버ID 13비트 + 시퀀스 10비트)를 제외하면 생성 시각(ms)이 남는다.
    timestamp_ms = (media_id >> 23) + INSTAGRAM_EPOCH_MS
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None


def run_validate() -> None:
    if not CHECKPOINT_CSV.exists():
        print(f"[오류] {CHECKPOINT_CSV} 가 없습니다. 2_crawl_instagram_detail.py를 어느 정도 돌려서 실제 날짜 데이터가 있어야 검증할 수 있습니다.")
        return

    df = pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig", dtype=str)
    df = df[df["작성일"].notna() & (df["작성일"].str.strip() != "")]
    if df.empty:
        print("[오류] 체크포인트에 실제 작성일이 확인된 행이 없습니다.")
        return

    errors_days = []
    rows = []
    for _, row in df.iterrows():
        actual = pd.to_datetime(row["작성일"], utc=True, errors="coerce")
        if pd.isna(actual):
            continue
        estimated = estimate_datetime(row["URL"])
        if estimated is None:
            continue
        diff_days = (estimated - actual.to_pydatetime()).total_seconds() / 86400
        errors_days.append(abs(diff_days))
        rows.append((row["URL"], actual, estimated, diff_days))

    if not errors_days:
        print("[오류] 추정 가능한 URL이 없습니다 (shortcode 파싱 실패).")
        return

    errors_series = pd.Series(errors_days)
    print(f"[검증 대상] {len(errors_days)}건")
    print(f"[오차(일), 절댓값] 평균={errors_series.mean():.1f} / 중앙값={errors_series.median():.1f} / 최대={errors_series.max():.1f}")
    for threshold in (1, 3, 7, 14, 30):
        within = (errors_series <= threshold).mean() * 100
        print(f"  오차 {threshold}일 이내: {within:.1f}%")

    print("\n[샘플 5건] URL / 실제 작성일 / 추정 작성일 / 오차(일)")
    for url, actual, estimated, diff in rows[:5]:
        print(f"  {url}\n    실제: {actual}  추정: {estimated}  오차: {diff:+.1f}일")


def run_filter() -> None:
    if not LINKS_CSV.exists():
        print(f"[오류] {LINKS_CSV} 가 없습니다. 1_collect_instagram_links.py를 먼저 실행하세요.")
        return

    df = pd.read_csv(LINKS_CSV, encoding="utf-8-sig", dtype=str)
    estimated = df["URL"].apply(estimate_datetime)

    in_range = estimated.apply(lambda d: d is not None and START_DATE <= d <= END_DATE)
    unknown = estimated.isna()

    kept = df[in_range | unknown]
    kept.to_csv(FILTERED_OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"[전체] {len(df)}건")
    print(f"[기간 추정 범위 안({START_DATE.date()}~{END_DATE.date()}, 앞쪽 여유 {START_BUFFER_DAYS}일/뒤쪽 여유 {END_BUFFER_DAYS}일)] {int(in_range.sum())}건")
    print(f"[추정 실패(안전하게 포함)] {int(unknown.sum())}건")
    print(f"[제외] {len(df) - len(kept)}건")
    print(f"\n[저장] {len(kept)}건 -> {FILTERED_OUTPUT_CSV.resolve()}")
    print("  2_crawl_instagram_detail.py의 INPUT_CSV를 이 파일명으로 바꾸면 이 목록만 방문합니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", action="store_true", help="체크포인트의 실제 날짜와 추정 날짜를 비교해 정확도 확인")
    group.add_argument("--filter", action="store_true", help="instagram_links.csv를 추정 날짜로 걸러서 저장")
    args = parser.parse_args()

    if args.validate:
        run_validate()
    else:
        run_filter()
