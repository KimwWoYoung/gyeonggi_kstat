"""
인스타그램 명소명 해시태그 게시물 링크 수집기 (Selenium 사용, 로그인 필요)

설치:
    pip install selenium webdriver-manager pandas

로그인:
    아이디/비밀번호를 스크립트가 자동으로 입력하지 않는다. 대신 전용
    크롬 프로필(CHROME_USER_DATA_DIR)로 브라우저를 띄운 뒤, 사람이
    직접 로그인(및 체크포인트/2단계 인증)을 끝낼 때까지 기다린다. 이
    프로필은 디스크에 남아있으므로, 한 번 로그인해두면 다음 실행부터는
    로그인 세션이 유지돼 인증코드를 다시 받을 필요가 없다. (자동화
    로그인을 매번 새로 시도하면 인스타그램이 매번 새 기기로 인식해
    인증코드를 반복 요구하는 문제가 있었다.)

사용법:
    python 1_collect_instagram_links.py

동작:
    KEYWORDS 의 각 명소명 해시태그(#명소명) 페이지에 접속해 게시물 링크를
    최대 LINKS_PER_KEYWORD개까지 스크롤로 수집, OUTPUT_CSV 에 저장한다.
    본문/날짜/좋아요수/댓글수는 2_crawl_instagram_detail.py 에서 실제
    게시물 페이지를 열어 수집한다.

중간저장 / 이어하기:
    키워드 하나를 다 처리할 때마다 그 결과를 CHECKPOINT_CSV에 즉시
    append하고, 처리한 키워드 이름을 DONE_KEYWORDS_FILE에 한 줄씩
    기록한다. 중간에 중단돼도 그때까지 모은 키워드별 결과는 남아있다.
    스크립트를 다시 실행하면 DONE_KEYWORDS_FILE에 이미 있는 키워드는
    건너뛰고 남은 키워드만 이어서 처리한다. 처음부터 다시 돌리려면
    CHECKPOINT_CSV와 DONE_KEYWORDS_FILE을 삭제하고 실행하면 된다.
    OUTPUT_CSV는 매 실행 종료 시점의 CHECKPOINT_CSV 전체 내용으로
    다시 생성된다.

멈춤 감지 / 자동 종료 (watchdog):
    인스타그램이 요청을 차단하면 페이지 로드가 응답 없이 그대로
    멈춰버릴 수 있다. 이를 막기 위해:
      1) driver에 페이지 로드 타임아웃(PAGE_LOAD_TIMEOUT_SEC)을 걸어
         두어, 그 시간 안에 로드가 끝나지 않으면 TimeoutException으로
         제어권을 돌려받아 해당 키워드만 실패 처리하고 다음으로 넘어간다.
      2) 그래도 어떤 이유로든 STUCK_TIMEOUT_SEC 동안 진행(하트비트)이
         전혀 없으면 별도 감시 스레드가 "멈춘 것"으로 판단해 프로세스를
         강제 종료한다. 지금까지의 결과는 CHECKPOINT_CSV에 이미 저장돼
         있으므로 스크립트를 다시 실행하면 멈췄던 지점부터 이어서 진행된다.
    watchdog은 사람이 로그인을 직접 처리하는 대기 시간은 '멈춤'으로
    오판하지 않도록, 그 대기가 끝난 뒤부터 가동한다.

주의:
    - 인스타그램은 로그인 자동화에 대한 탐지(체크포인트/2단계 인증 요구)가
      강해서, 특히 새로운 IP(서버/클라우드 환경)에서는 로그인 자체가
      막힐 수 있다. 그 경우 로컬 PC의 일반 브라우저로 먼저 로그인해본
      뒤 재시도하거나, 세션 쿠키를 재사용하는 방식으로 바꿔야 한다.
    - 해시태그 피드는 "인기 게시물"과 "최근 게시물"이 섞여 있다. 페이지에서
      "최근 게시물"/"Recent posts" 헤더를 찾을 수 있으면 그 이후에 나오는
      링크만 수집해 인기 게시물 그리드를 최대한 배제하지만(collect_post_links),
      헤더를 못 찾으면 페이지 전체 링크 수집으로 폴백하며, 이 방식도 완벽한
      최신순 정렬을 보장하진 않는다. 정확한 기간 필터링은 2번 스크립트에서
      게시물 작성일을 확인한 뒤에 적용한다.
    - 요청이 많으면 계정이 일시적으로 차단(액션 블록)될 수 있으니
      SLEEP_BETWEEN_KEYWORDS_SEC 값을 늘려서 재시도할 것.
"""

from __future__ import annotations

import os
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

# 로그인 세션을 유지하기 위한 전용 크롬 프로필 (없으면 자동 생성됨).
# 인스타그램/2_crawl_instagram_detail.py와 같은 경로를 써서 로그인 상태를 공유한다.
CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_instagram"))

LINKS_PER_KEYWORD = 300
SCROLL_PAUSE_SEC = 2.0
MAX_SCROLL_PER_KEYWORD = 80
STOP_AFTER_NO_CHANGE = 5
SLEEP_BETWEEN_KEYWORDS_SEC = 3.0
OUTPUT_CSV = Path("instagram_links.csv")
CHECKPOINT_CSV = Path("instagram_links_checkpoint.csv")
DONE_KEYWORDS_FILE = Path("instagram_links_done_keywords.txt")

FIELDNAMES = ["키워드", "채널", "URL"]

# --- 멈춤 감지(watchdog) 관련 설정 ---
PAGE_LOAD_TIMEOUT_SEC = 30          # drv.get() 이 이 시간 안에 안 끝나면 TimeoutException 발생
STUCK_TIMEOUT_SEC = 300             # 이 시간 동안 진행(하트비트)이 없으면 프로세스 강제 종료
WATCHDOG_CHECK_INTERVAL_SEC = 15


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


# 해시태그 페이지의 '인기 게시물' 그리드를 건너뛰고 '최근 게시물' 섹션 이후의
# 게시물만 모으기 위한 헤더 탐색용 XPath (한국어/영어 UI 모두 대응)
RECENT_HEADING_XPATH = (
    '//*[self::h2 or self::span or self::div]'
    '[contains(text(), "최근 게시물") or contains(text(), "Recent posts")]'
)


def collect_post_links(drv) -> set[str]:
    """'최근 게시물' 헤더를 찾으면 그 이후 링크만, 못 찾으면 페이지 전체 링크를 수집한다."""
    try:
        heading = drv.find_element(By.XPATH, RECENT_HEADING_XPATH)
        if heading:
            recent_links = drv.find_elements(
                By.XPATH,
                RECENT_HEADING_XPATH + '/following::a[contains(@href, "/p/")]',
            )
            if recent_links:
                return {href for a in recent_links if (href := a.get_attribute("href"))}
    except Exception:
        pass

    return {
        href
        for a in drv.find_elements(By.XPATH, '//a[contains(@href, "/p/")]')
        if (href := a.get_attribute("href"))
    }


def collect_links_for_keyword(drv, keyword: str) -> list[str]:
    # 인스타그램 해시태그는 공백을 허용하지 않으므로 태그에서는 공백을 제거한다
    # (결과 CSV의 '키워드' 컬럼에는 원래 관광지점명을 그대로 남긴다)
    tag = keyword.replace(" ", "")
    safe_get(drv, f"https://www.instagram.com/explore/tags/{tag}/")
    time.sleep(3)

    try:
        WebDriverWait(drv, 15).until(
            EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/p/")]'))
        )
    except Exception:
        print("  ! 게시물 로딩 실패 (해당 해시태그 게시물이 없을 수 있음)")
        return []

    links: set[str] = set()
    prev_count = 0
    no_change_count = 0

    for scroll in range(MAX_SCROLL_PER_KEYWORD):
        if len(links) >= LINKS_PER_KEYWORD:
            break

        drv.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_SEC)

        links.update(collect_post_links(drv))

        curr_count = len(links)
        if curr_count == prev_count:
            no_change_count += 1
            if no_change_count >= STOP_AFTER_NO_CHANGE:
                break
        else:
            no_change_count = 0
        prev_count = curr_count

    return list(links)[:LINKS_PER_KEYWORD]


def load_done_keywords() -> set[str]:
    if DONE_KEYWORDS_FILE.exists():
        return {
            line.strip()
            for line in DONE_KEYWORDS_FILE.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        }
    return set()


def mark_keyword_done(keyword: str) -> None:
    with DONE_KEYWORDS_FILE.open("a", encoding="utf-8-sig") as f:
        f.write(keyword + "\n")


def append_checkpoint(rows: list[dict]) -> None:
    if not rows:
        return
    write_header = not CHECKPOINT_CSV.exists()
    pd.DataFrame(rows, columns=FIELDNAMES).to_csv(
        CHECKPOINT_CSV, mode="a", index=False, header=write_header, encoding="utf-8-sig"
    )


def save_final_output() -> None:
    if not CHECKPOINT_CSV.exists():
        print("\n[완료] 수집된 링크 없음")
        return
    df = pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig", dtype=str)
    df = df.drop_duplicates(subset="URL")
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n[완료] {len(df)}건 저장 -> {OUTPUT_CSV.resolve()}")


def main() -> None:
    done_keywords = load_done_keywords()
    remaining_keywords = [k for k in KEYWORDS if k not in done_keywords]

    print(f"[📋] 전체 키워드 {len(KEYWORDS)}개 중 처리 완료 {len(done_keywords)}개, 남은 {len(remaining_keywords)}개")
    if DONE_KEYWORDS_FILE.exists():
        print(f"  (이어하기: {DONE_KEYWORDS_FILE.resolve()} 에서 이어서 처리합니다)")

    if remaining_keywords:
        driver = build_driver()
        login(driver)

        # watchdog은 사람이 수동으로 로그인/인증을 처리하는 동안 '멈춤'으로
        # 오판하지 않도록, login()의 대기가 끝난 뒤부터 가동한다.
        start_watchdog()
        touch_heartbeat()

        try:
            for keyword in remaining_keywords:
                print(f"[검색] {keyword}")
                touch_heartbeat()
                try:
                    links = collect_links_for_keyword(driver, keyword)
                except Exception as e:
                    print(f"  ! 검색 실패: {e}")
                    links = []

                print(f"  -> {len(links)}건")
                rows = [{"키워드": keyword, "채널": "인스타그램", "URL": url} for url in links]
                append_checkpoint(rows)
                mark_keyword_done(keyword)
                touch_heartbeat()
                time.sleep(SLEEP_BETWEEN_KEYWORDS_SEC)
        finally:
            driver.quit()

    save_final_output()


if __name__ == "__main__":
    main()
