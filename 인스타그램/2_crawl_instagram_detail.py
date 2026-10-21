"""
인스타그램 게시물 본문/작성일/좋아요수/댓글수 크롤러 (Selenium 사용, 로그인 필요)

설치:
    pip install selenium webdriver-manager pandas openpyxl

로그인:
    아이디/비밀번호를 스크립트가 자동으로 입력하지 않는다. 대신 전용
    크롬 프로필(CHROME_USER_DATA_DIR, 1_collect_instagram_links.py와
    동일 경로)로 브라우저를 띄운 뒤, 사람이 직접 로그인(및 체크포인트/
    2단계 인증)을 끝낼 때까지 기다린다. 한 번 로그인해두면 다음
    실행부터는 세션이 유지돼 인증코드를 다시 받을 필요가 없다.

사용법:
    python 1_collect_instagram_links.py 를 먼저 실행해 INPUT_CSV 를 만든 뒤
    python 2_crawl_instagram_detail.py 실행

동작:
    INPUT_CSV(키워드/채널/URL)에 있는 각 게시물 URL을 열어 본문(caption),
    작성일, 좋아요수, 댓글수를 추출하고 START_DATE~END_DATE 기간에 작성된
    게시물만 OUTPUT_XLSX 에 저장한다.

중간저장 / 이어하기:
    게시물 하나를 처리할 때마다 결과를 CHECKPOINT_CSV(기본
    instagram_detail_checkpoint.csv)에 즉시 한 줄씩 append 한다. 중간에
    프로그램이 종료되어도 그때까지의 결과는 CHECKPOINT_CSV에 남아있다.
    스크립트를 다시 실행하면 CHECKPOINT_CSV에 이미 있는 URL은 건너뛰고
    남은 URL만 이어서 처리한다. 처음부터 다시 돌리려면 CHECKPOINT_CSV
    파일을 삭제하고 실행하면 된다. OUTPUT_XLSX는 매 실행 종료 시점의
    CHECKPOINT_CSV 전체 내용으로 다시 생성된다.

멈춤 감지 / 자동 종료 (watchdog):
    인스타그램이 요청을 차단하면(HTTP 429 "Please wait a few minutes"
    같은 페이지) Selenium의 driver.get()이 응답 없이 그대로 멈춰버릴 수
    있다. 이를 막기 위해 두 가지 안전장치를 둔다.
      1) driver에 페이지 로드 타임아웃(PAGE_LOAD_TIMEOUT_SEC)을 걸어
         두어, 그 시간 안에 로드가 끝나지 않으면 TimeoutException으로
         제어권을 돌려받아 해당 게시물만 실패 처리하고 다음으로 넘어간다.
      2) 그래도 어떤 이유로든 STUCK_TIMEOUT_SEC 동안 진행(하트비트)이
         전혀 없으면 별도 감시 스레드가 "멈춘 것"으로 판단해 프로세스를
         강제 종료한다. 지금까지의 결과는 CHECKPOINT_CSV에 이미 저장돼
         있으므로 스크립트를 다시 실행하면 멈췄던 지점부터 이어서 진행된다.
    또한 같은 세션에서 429(요청 제한) 응답이 연속으로
    MAX_CONSECUTIVE_RATE_LIMIT 번 감지되면, 더 시도해도 계속 막힐
    가능성이 높으므로 스스로 크롤링을 멈추고 종료한다(RATE_LIMIT_BACKOFF_SEC
    만큼 대기 후 몇 번 더 재시도한 다음 그래도 안 되면 중단).

주의 (선택자 관련):
    좋아요수/댓글수/본문은 우선 og:description 메타태그("123 likes, 4
    comments - ... : caption")를 파싱해서 얻고, 실패하면 페이지 DOM에서
    직접 찾는다. 인스타그램이 좋아요수를 비공개로 설정한 게시물은 값이
    비어 있을 수 있다.
"""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# 로그인 세션을 유지하기 위한 전용 크롬 프로필 (없으면 자동 생성됨).
# 1_collect_instagram_links.py와 같은 경로를 써서 로그인 상태를 공유한다.
CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_instagram"))

INPUT_CSV = "instagram_links.csv"
OUTPUT_XLSX = "instagram_detail_202607_202609.xlsx"
CHECKPOINT_CSV = Path("instagram_detail_checkpoint.csv")

# 수집 기간 (게시물 작성일 기준)
START_DATE = "2026-07-01"
END_DATE = "2026-09-30"

RESULT_COLUMNS = ["키워드", "채널", "본문", "작성일", "좋아요수", "댓글수", "URL"]

SLEEP_BETWEEN_POSTS_SEC = (2.5, 4.5)

# --- 멈춤 감지(watchdog) 관련 설정 ---
PAGE_LOAD_TIMEOUT_SEC = 30          # drv.get() 이 이 시간 안에 안 끝나면 TimeoutException 발생
STUCK_TIMEOUT_SEC = 300             # 이 시간 동안 진행(하트비트)이 없으면 프로세스 강제 종료
WATCHDOG_CHECK_INTERVAL_SEC = 15
MAX_CONSECUTIVE_RATE_LIMIT = 3      # 429(요청 제한)가 연속으로 이만큼 감지되면 크롤링 중단
RATE_LIMIT_BACKOFF_SEC = 60         # 429 감지 시 다음 시도 전 대기 시간

OG_DESC_RE = re.compile(
    r"^([\d,]+)\s+likes?,\s+([\d,]+)\s+comments?\s+-\s+.+?:\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


class RateLimitedError(Exception):
    """인스타그램이 요청을 제한(HTTP 429 등)했을 때 발생시키는 예외."""


_last_heartbeat = time.time()
_heartbeat_lock = threading.Lock()


def touch_heartbeat() -> None:
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.time()


def start_watchdog() -> None:
    """STUCK_TIMEOUT_SEC 동안 진행이 없으면 프로세스를 강제 종료하는 감시 스레드 시작."""

    def _watch():
        while True:
            time.sleep(WATCHDOG_CHECK_INTERVAL_SEC)
            with _heartbeat_lock:
                elapsed = time.time() - _last_heartbeat
            if elapsed > STUCK_TIMEOUT_SEC:
                print(
                    f"\n[⛔ watchdog] {int(elapsed)}초 동안 진행이 없어 멈춘 것으로 "
                    "판단, 프로세스를 강제 종료합니다. (CHECKPOINT_CSV에 저장된 "
                    "내용은 남아있으니 다시 실행하면 이어서 진행됩니다)"
                )
                os._exit(1)

    t = threading.Thread(target=_watch, daemon=True)
    t.start()


def is_rate_limited(drv) -> bool:
    try:
        title = (drv.title or "").lower()
        source = drv.page_source or ""
    except Exception:
        return False
    if "429" in title:
        return True
    markers = ["http error 429", "please wait a few minutes", "너무 많은 요청", "요청이 너무 많습니다"]
    lower_source = source.lower()
    return any(marker in lower_source for marker in markers)


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("detach", True)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    options.add_argument("--profile-directory=Default")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT_SEC)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def safe_get(drv, url: str) -> None:
    """페이지 로드가 PAGE_LOAD_TIMEOUT_SEC 안에 끝나지 않으면 로딩을 멈추고 넘어간다."""
    try:
        drv.get(url)
    except TimeoutException:
        try:
            drv.execute_script("window.stop();")
        except Exception:
            pass


def login(drv) -> None:
    """로그인은 자동 입력하지 않고 사람이 직접 한다 (아래 설명 참고)."""
    safe_get(drv, "https://www.instagram.com/")

    print("\n[⏸️] 브라우저가 열렸습니다. 이미 로그인돼 있으면 그대로 두시고,"
          " 아니라면 아이디/비밀번호 입력과 로그인, 이후 체크포인트/2단계 인증까지 직접 처리해주세요.")
    print("    (이 브라우저는 전용 프로필을 재사용하므로, 한 번 로그인해두면"
          " 다음 실행부터는 다시 로그인하지 않아도 됩니다)")
    input("    로그인 상태 확인/완료되면 Enter를 눌러 수집을 시작합니다... ")

    try:
        WebDriverWait(drv, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='나중에 하기']"))
        ).click()
        print("✅ 팝업 닫기 완료")
    except Exception:
        print("ℹ️ 팝업 없음")


def load_checkpoint() -> pd.DataFrame:
    if CHECKPOINT_CSV.exists():
        return pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig", dtype=str)
    return pd.DataFrame(columns=RESULT_COLUMNS)


def append_checkpoint(row: dict) -> None:
    write_header = not CHECKPOINT_CSV.exists()
    pd.DataFrame([row], columns=RESULT_COLUMNS).to_csv(
        CHECKPOINT_CSV, mode="a", index=False, header=write_header, encoding="utf-8-sig"
    )


def save_filtered_xlsx(all_df: pd.DataFrame) -> None:
    dates = all_df["작성일"].fillna("").str.slice(0, 10)
    in_range = dates.between(START_DATE, END_DATE)
    no_date = all_df["작성일"].fillna("") == ""
    filtered_df = all_df[in_range | no_date]

    filtered_df.to_excel(OUTPUT_XLSX, index=False)
    print(f"\n[저장] {len(filtered_df)}건 -> {Path(OUTPUT_XLSX).resolve()}")
    print(f"  (기간 밖 {len(all_df) - len(filtered_df)}건 제외, 날짜 미확인 행은 포함됨)")


def crawl_post(drv, url: str) -> dict:
    safe_get(drv, url)
    time.sleep(3)

    if is_rate_limited(drv):
        raise RateLimitedError(f"HTTP 429(요청 제한) 감지: {url}")

    caption, like_count, comment_count = "", "", ""
    try:
        meta = drv.find_element(By.CSS_SELECTOR, 'meta[property="og:description"]')
        og_desc = meta.get_attribute("content") or ""
        m = OG_DESC_RE.match(og_desc)
        if m:
            like_count = m.group(1).replace(",", "")
            comment_count = m.group(2).replace(",", "")
            caption = m.group(3).strip()
    except Exception:
        pass

    if not caption:
        try:
            content_div = WebDriverWait(drv, 10).until(
                EC.presence_of_element_located((By.XPATH, "//section/main/div/div[1]/div/div[2]"))
            )
            caption = content_div.text
        except Exception as e:
            caption = f"본문 추출 실패: {e}"

    try:
        date = drv.find_element(By.TAG_NAME, "time").get_attribute("datetime")
    except Exception:
        date = ""

    return {
        "본문": caption,
        "작성일": date,
        "좋아요수": like_count,
        "댓글수": comment_count,
    }


def main() -> None:
    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        print(f"[오류] {INPUT_CSV} 파일이 없습니다. 1_collect_instagram_links.py 를 먼저 실행하세요.")
        return

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    checkpoint_df = load_checkpoint()
    done_urls = set(checkpoint_df["URL"]) if not checkpoint_df.empty else set()
    remaining = df[~df["URL"].isin(done_urls)]

    print(f"[📋] 전체 {len(df)}개 중 처리 완료 {len(done_urls)}개, 남은 {len(remaining)}개")
    if CHECKPOINT_CSV.exists():
        print(f"  (이어하기: {CHECKPOINT_CSV.resolve()} 에서 이어서 처리합니다)")

    if remaining.empty:
        print("[완료] 남은 URL이 없습니다. 체크포인트로 최종 파일만 다시 생성합니다.")
    else:
        driver = build_driver()
        login(driver)

        # watchdog은 사람이 수동으로 로그인/인증을 처리하는 동안 '멈춤'으로
        # 오판하지 않도록, login()의 대기가 끝난 뒤부터 가동한다.
        start_watchdog()
        touch_heartbeat()

        consecutive_rate_limit = 0
        try:
            for i, (idx, row) in enumerate(remaining.iterrows()):
                url = row["URL"]
                print(f"\n[{len(done_urls) + i + 1}/{len(df)}] {url}")
                touch_heartbeat()

                try:
                    detail = crawl_post(driver, url)
                except RateLimitedError as e:
                    consecutive_rate_limit += 1
                    print(f"  ⚠️ {e} ({consecutive_rate_limit}/{MAX_CONSECUTIVE_RATE_LIMIT})")
                    touch_heartbeat()
                    if consecutive_rate_limit >= MAX_CONSECUTIVE_RATE_LIMIT:
                        print(
                            "\n[⛔] 요청 제한(429)이 반복돼 크롤링을 중단합니다. "
                            "잠시 후(예: 30분~1시간 뒤) 다시 실행하면 이어서 진행됩니다."
                        )
                        break
                    time.sleep(RATE_LIMIT_BACKOFF_SEC)
                    touch_heartbeat()
                    continue
                except Exception as e:
                    print(f"  ! 크롤링 실패: {e}")
                    detail = {"본문": f"크롤링 실패: {e}", "작성일": "", "좋아요수": "", "댓글수": ""}

                consecutive_rate_limit = 0
                result_row = {
                    "키워드": row.get("키워드", ""),
                    "채널": row.get("채널", "인스타그램"),
                    "본문": detail["본문"],
                    "작성일": detail["작성일"],
                    "좋아요수": detail["좋아요수"],
                    "댓글수": detail["댓글수"],
                    "URL": url,
                }
                append_checkpoint(result_row)
                touch_heartbeat()
                time.sleep(random_sleep())
        finally:
            driver.quit()

    # 체크포인트(지금까지 처리된 전체 결과, 이번 실행분 포함)를 기준으로 최종 파일 생성
    all_df = load_checkpoint()
    save_filtered_xlsx(all_df)


def random_sleep() -> float:
    import random

    lo, hi = SLEEP_BETWEEN_POSTS_SEC
    return random.uniform(lo, hi)


if __name__ == "__main__":
    main()
