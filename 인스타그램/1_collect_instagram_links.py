"""
인스타그램 명소명 해시태그 게시물 링크 수집기 (Selenium 사용, 로그인 필요)

설치:
    pip install selenium webdriver-manager pandas

환경변수:
    INSTAGRAM_USERNAME
    INSTAGRAM_PASSWORD

사용법:
    export INSTAGRAM_USERNAME="..."
    export INSTAGRAM_PASSWORD="..."
    python 1_collect_instagram_links.py

동작:
    KEYWORDS 의 각 명소명 해시태그(#명소명) 페이지에 접속해 게시물 링크를
    최대 LINKS_PER_KEYWORD개까지 스크롤로 수집, OUTPUT_CSV 에 저장한다.
    본문/날짜/좋아요수/댓글수는 2_crawl_instagram_detail.py 에서 실제
    게시물 페이지를 열어 수집한다.

    57개 키워드를 전부 도는 데 시간이 걸리므로, 키워드 하나가 끝날
    때마다 CHECKPOINT_CSV 에 바로 append해 중간에 중단돼도 그동안 모은
    데이터는 보존된다. 스크립트를 다시 실행하면 CHECKPOINT_CSV 에 이미
    있는 키워드는 건너뛰고 이어서 진행한다. Ctrl+C로 중단해도 그때까지
    저장된 내용으로 OUTPUT_CSV 를 만든다.

주의:
    - 인스타그램은 로그인 자동화에 대한 탐지(체크포인트/2단계 인증 요구)가
      강해서, 특히 새로운 IP(서버/클라우드 환경)에서는 로그인 자체가
      막힐 수 있다. 그 경우 로컬 PC의 일반 브라우저로 먼저 로그인해본
      뒤 재시도하거나, 세션 쿠키를 재사용하는 방식으로 바꿔야 한다.
    - 해시태그 피드는 "인기 게시물"과 "최근 게시물"이 섞여 있어 완벽한
      최신순 정렬이 보장되지 않는다. 기간 필터링은 2번 스크립트에서
      게시물 작성일을 확인한 뒤에 적용한다.
    - 요청이 많으면 계정이 일시적으로 차단(액션 블록)될 수 있으니
      SLEEP_BETWEEN_KEYWORDS_SEC 값을 늘려서 재시도할 것.
"""

from __future__ import annotations

import csv
import os
import time
from pathlib import Path

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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

USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()

LINKS_PER_KEYWORD = 150
SCROLL_PAUSE_SEC = 2.0
MAX_SCROLL_PER_KEYWORD = 60
STOP_AFTER_NO_CHANGE = 3
SLEEP_BETWEEN_KEYWORDS_SEC = 3.0
CHECKPOINT_CSV = Path("instagram_links_checkpoint.csv")
OUTPUT_CSV = Path("instagram_links.csv")

FIELDNAMES = ["키워드", "채널", "URL"]


def build_driver() -> webdriver.Chrome:
    options = Options()
    options.add_experimental_option("detach", True)
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
    )
    return driver


def find_login_fields(drv):
    """여러 방식으로 아이디/비번 입력창을 순서대로 시도. iframe도 확인."""
    locator_sets = [
        (By.NAME, "username", By.NAME, "password"),
        (By.CSS_SELECTOR, 'input[type="text"]', By.CSS_SELECTOR, 'input[type="password"]'),
        (By.CSS_SELECTOR, 'input[aria-label*="이메일"]', By.CSS_SELECTOR, 'input[aria-label*="비밀번호"]'),
        (By.XPATH, '//input[@autocomplete="username"]', By.XPATH, '//input[@autocomplete="current-password"]'),
    ]

    def try_locators():
        for u_by, u_val, p_by, p_val in locator_sets:
            try:
                u = WebDriverWait(drv, 4).until(EC.presence_of_element_located((u_by, u_val)))
                p = drv.find_element(p_by, p_val)
                if u.is_displayed():
                    return u, p
            except Exception:
                continue
        return None, None

    u, p = try_locators()
    if u is not None:
        return u, p

    for frame in drv.find_elements(By.TAG_NAME, "iframe"):
        try:
            drv.switch_to.frame(frame)
            u, p = try_locators()
            if u is not None:
                return u, p
            drv.switch_to.default_content()
        except Exception:
            drv.switch_to.default_content()
            continue

    return None, None


def type_like_human(drv, element, text: str, field_label: str = "") -> bool:
    """React 컨트롤 입력창 대응: 클릭 후 한 글자씩 입력하고, 값이 실제로 들어갔는지 검증."""
    element.click()
    time.sleep(0.3)
    element.clear()
    time.sleep(0.2)

    for ch in text:
        element.send_keys(ch)
        time.sleep(0.07)

    time.sleep(0.3)
    actual = element.get_attribute("value")

    if actual != text:
        drv.execute_script(
            """
            const el = arguments[0];
            const val = arguments[1];
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            element,
            text,
        )
        time.sleep(0.3)
        actual = element.get_attribute("value")

    print(f"{'✅' if actual == text else '❌'} {field_label} 입력 확인")
    return actual == text


def login(drv) -> None:
    drv.get("https://www.instagram.com/accounts/login/")
    time.sleep(3)

    username_input, password_input = find_login_fields(drv)
    if username_input is None:
        drv.save_screenshot("login_debug.png")
        raise RuntimeError("로그인 필드를 찾지 못했습니다. login_debug.png 확인하세요.")

    type_like_human(drv, username_input, USERNAME, "아이디")
    type_like_human(drv, password_input, PASSWORD, "비밀번호")
    time.sleep(0.5)
    password_input.send_keys(Keys.ENTER)
    print("✅ 로그인 시도 완료")

    time.sleep(5)
    try:
        WebDriverWait(drv, 5).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='나중에 하기']"))
        ).click()
        print("✅ 팝업 닫기 완료")
    except Exception:
        print("ℹ️ 팝업 없음")


def collect_links_for_keyword(drv, keyword: str) -> list[str]:
    # 인스타그램 해시태그는 공백을 허용하지 않으므로 태그에서는 공백을 제거한다
    # (결과 CSV의 '키워드' 컬럼에는 원래 관광지점명을 그대로 남긴다)
    tag = keyword.replace(" ", "")
    drv.get(f"https://www.instagram.com/explore/tags/{tag}/")
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

        for elem in drv.find_elements(By.XPATH, '//a[contains(@href, "/p/")]'):
            href = elem.get_attribute("href")
            if href:
                links.add(href)

        curr_count = len(links)
        if curr_count == prev_count:
            no_change_count += 1
            if no_change_count >= STOP_AFTER_NO_CHANGE:
                break
        else:
            no_change_count = 0
        prev_count = curr_count

    return list(links)[:LINKS_PER_KEYWORD]


def main() -> None:
    if not USERNAME or not PASSWORD:
        print("[오류] 환경변수 INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD 을 설정해주세요.")
        return

    done_keywords: set[str] = set()
    if CHECKPOINT_CSV.exists():
        prev = pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig")
        done_keywords = set(prev["키워드"].dropna())
        print(f"[⏩] 이전에 완료된 {len(done_keywords)}개 키워드는 건너뜀 (이어서 진행)")
    else:
        with CHECKPOINT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    todo_keywords = [k for k in KEYWORDS if k not in done_keywords]
    print(f"[대상 키워드] 전체 {len(KEYWORDS)}개 중 이번에 {len(todo_keywords)}개\n")

    driver = build_driver()
    login(driver)

    try:
        with CHECKPOINT_CSV.open("a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)

            for keyword in todo_keywords:
                print(f"[검색] {keyword}")
                try:
                    links = collect_links_for_keyword(driver, keyword)
                except Exception as e:
                    print(f"  ! 검색 실패: {e}")
                    time.sleep(SLEEP_BETWEEN_KEYWORDS_SEC)
                    continue

                print(f"  -> {len(links)}건")
                for url in links:
                    writer.writerow({"키워드": keyword, "채널": "인스타그램", "URL": url})
                f.flush()  # 중단돼도 방금 쓴 키워드까지는 파일에 남도록 즉시 반영
                time.sleep(SLEEP_BETWEEN_KEYWORDS_SEC)
    except KeyboardInterrupt:
        print("\n[⏸️] 사용자 중단 감지. 지금까지 저장된 내용으로 마무리합니다.")
    finally:
        driver.quit()

    if CHECKPOINT_CSV.exists():
        df = pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig").drop_duplicates(subset="URL")
        df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
        print(f"\n[완료] {len(df)}건 저장 -> {OUTPUT_CSV.resolve()}")
    else:
        print("\n[완료] 수집된 링크 없음")


if __name__ == "__main__":
    main()
