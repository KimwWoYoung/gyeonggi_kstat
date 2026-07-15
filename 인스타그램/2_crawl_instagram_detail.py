"""
인스타그램 게시물 본문/작성일/좋아요수/댓글수 크롤러 (Selenium 사용, 로그인 필요)

설치:
    pip install selenium webdriver-manager pandas openpyxl

환경변수:
    INSTAGRAM_USERNAME
    INSTAGRAM_PASSWORD

사용법:
    python 1_collect_instagram_links.py 를 먼저 실행해 INPUT_CSV 를 만든 뒤
    python 2_crawl_instagram_detail.py 실행

동작:
    INPUT_CSV(키워드/채널/URL)에 있는 각 게시물 URL을 열어 본문(caption),
    작성일, 좋아요수, 댓글수를 추출하고 START_DATE~END_DATE 기간에 작성된
    게시물만 OUTPUT_XLSX 에 저장한다.

주의 (선택자 관련):
    좋아요수/댓글수/본문은 우선 og:description 메타태그("123 likes, 4
    comments - ... : caption")를 파싱해서 얻고, 실패하면 페이지 DOM에서
    직접 찾는다. 인스타그램이 좋아요수를 비공개로 설정한 게시물은 값이
    비어 있을 수 있다.
"""

from __future__ import annotations

import os
import re
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

USERNAME = os.getenv("INSTAGRAM_USERNAME", "").strip()
PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "").strip()

INPUT_CSV = "instagram_links.csv"
OUTPUT_XLSX = "instagram_detail_202604_202606.xlsx"

# 수집 기간 (게시물 작성일 기준)
START_DATE = "2026-04-01"
END_DATE = "2026-06-30"

SLEEP_BETWEEN_POSTS_SEC = (2.5, 4.5)

OG_DESC_RE = re.compile(
    r"^([\d,]+)\s+likes?,\s+([\d,]+)\s+comments?\s+-\s+.+?:\s*(.*)$",
    re.IGNORECASE | re.DOTALL,
)


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


def crawl_post(drv, url: str) -> dict:
    drv.get(url)
    time.sleep(3)

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
    if not USERNAME or not PASSWORD:
        print("[오류] 환경변수 INSTAGRAM_USERNAME / INSTAGRAM_PASSWORD 을 설정해주세요.")
        return

    input_path = Path(INPUT_CSV)
    if not input_path.exists():
        print(f"[오류] {INPUT_CSV} 파일이 없습니다. 1_collect_instagram_links.py 를 먼저 실행하세요.")
        return

    df = pd.read_csv(input_path, encoding="utf-8-sig")
    print(f"[📋] 크롤링할 URL {len(df)}개")

    driver = build_driver()
    login(driver)

    results = []
    for idx, row in df.iterrows():
        url = row["URL"]
        print(f"\n[{idx + 1}/{len(df)}] {url}")
        try:
            detail = crawl_post(driver, url)
        except Exception as e:
            print(f"  ! 크롤링 실패: {e}")
            detail = {"본문": f"크롤링 실패: {e}", "작성일": "", "좋아요수": "", "댓글수": ""}

        results.append({
            "키워드": row.get("키워드", ""),
            "채널": row.get("채널", "인스타그램"),
            "본문": detail["본문"],
            "작성일": detail["작성일"],
            "좋아요수": detail["좋아요수"],
            "댓글수": detail["댓글수"],
            "URL": url,
        })
        time.sleep(random_sleep())

    driver.quit()

    out_df = pd.DataFrame(results, columns=["키워드", "채널", "본문", "작성일", "좋아요수", "댓글수", "URL"])

    # 기간 필터링 (날짜를 추출하지 못한 행은 값 확인이 필요하므로 남겨둔다)
    dates = out_df["작성일"].str.slice(0, 10)
    in_range = dates.between(START_DATE, END_DATE)
    no_date = out_df["작성일"] == ""
    filtered_df = out_df[in_range | no_date]

    filtered_df.to_excel(OUTPUT_XLSX, index=False)
    print(f"\n[완료] {len(filtered_df)}건 저장 -> {Path(OUTPUT_XLSX).resolve()}")
    print(f"  (기간 밖 {len(out_df) - len(filtered_df)}건 제외, 날짜 미확인 행은 포함됨)")


def random_sleep() -> float:
    import random

    lo, hi = SLEEP_BETWEEN_POSTS_SEC
    return random.uniform(lo, hi)


if __name__ == "__main__":
    main()
