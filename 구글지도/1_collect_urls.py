"""
1_collect_urls.py
Google Maps에서 장소 URL을 수집하여 CSV로 저장합니다.
config.py의 CITY / CITY_KR 만 바꾸면 다른 도시에도 적용됩니다.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import os

from config import CITY, CITY_KR, KEYWORDS, CSV_OUTPUT, SCROLL_PAUSE, MAX_SCROLL_NO_CHANGE, CHROME_USER_DATA_DIR, CHROME_PROFILE

# =============================================
# 브라우저 설정
# =============================================
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)


def get_scrollable_container():
    """검색 결과 스크롤 컨테이너를 찾습니다. 여러 방법 순차 시도."""
    # 방법 1: role="feed"
    try:
        el = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[role="feed"]')))
        print("  ✅ 스크롤 컨테이너 발견 (role=feed)")
        return el
    except Exception:
        pass

    # 방법 2: 검색 결과 패널 클래스
    for css in [
        'div.m6QErb.DxyBCb.kA9KIf.dS8AEf',
        'div.m6QErb',
        'div[aria-label*="결과"]',
        'div[aria-label*="Results"]',
    ]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, css)
            print(f"  ✅ 스크롤 컨테이너 발견 ({css})")
            return el
        except Exception:
            continue

    print("  [⚠️] 스크롤 컨테이너를 찾지 못했습니다. body로 대체.")
    return None


def scroll_to_load_all(scrollable_element):
    """
    스크롤을 끝까지 내려 모든 장소를 로드합니다.
    변화가 MAX_SCROLL_NO_CHANGE 회 연속으로 없으면 종료합니다.
    """
    no_change_count = 0
    prev_count = 0
    scroll_num = 0

    while True:
        # 현재 장소 카드 개수 확인
        cards = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
        curr_count = len(cards)

        if curr_count > prev_count:
            print(f"  [📜] 스크롤 {scroll_num+1}회 - 장소: {prev_count} → {curr_count}")
            prev_count = curr_count
            no_change_count = 0
        else:
            no_change_count += 1
            print(f"  [📜] 스크롤 {scroll_num+1}회 - 변화 없음 ({no_change_count}/{MAX_SCROLL_NO_CHANGE})")
            if no_change_count >= MAX_SCROLL_NO_CHANGE:
                print(f"  [✅] 더 이상 로드할 장소가 없습니다. 스크롤 종료.")
                break

        # 스크롤 실행 — 컨테이너 + body 둘 다 시도
        if scrollable_element:
            try:
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight", scrollable_element
                )
            except Exception:
                pass
        # body 스크롤도 같이 실행 (컨테이너 스크롤이 안 먹는 경우 대비)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")

        time.sleep(SCROLL_PAUSE)
        scroll_num += 1


def collect_places_from_keyword(keyword):
    """
    키워드로 Google Maps를 검색하고 장소 URL + 장소명을 수집합니다.
    """
    print(f"\n{'='*60}")
    print(f"🔍 키워드 검색: {keyword}")
    print(f"{'='*60}")

    # Google Maps 검색
    search_url = f"https://www.google.com/maps/search/{keyword.replace(' ', '+')}"
    driver.get(search_url)
    time.sleep(3)

    # 검색 결과 스크롤 컨테이너 찾기
    scrollable = get_scrollable_container()

    # 스크롤로 모든 결과 로드
    print("📜 스크롤 시작...")
    scroll_to_load_all(scrollable)

    # 장소 카드에서 URL + 장소명 추출
    place_data = []
    seen_urls = set()

    cards = driver.find_elements(By.CSS_SELECTOR, 'a[href*="/maps/place/"]')
    print(f"\n[📝] 총 {len(cards)}개의 장소 카드 발견")

    for card in cards:
        try:
            url = card.get_attribute("href")
            # URL 정규화 (쿼리 파라미터 제거하여 중복 판별)
            base_url = url.split("?")[0] if url else ""

            if not base_url or base_url in seen_urls:
                continue
            seen_urls.add(base_url)

            # 장소명 추출 시도
            place_name = ""
            try:
                # aria-label 속성 우선
                place_name = card.get_attribute("aria-label") or ""
            except Exception:
                pass

            if not place_name:
                try:
                    # 내부 텍스트에서 추출
                    place_name = card.find_element(
                        By.CSS_SELECTOR, "div.fontHeadlineSmall"
                    ).text.strip()
                except Exception:
                    pass

            place_data.append({
                "장소명": place_name,
                "지역": CITY_KR,
                "URL": url,
                "키워드": keyword
            })

        except Exception as e:
            continue

    print(f"[✅] 유효한 장소 {len(place_data)}개 수집 완료")
    return place_data


# =============================================
# 메인 실행
# =============================================
all_places = []

for keyword in KEYWORDS:
    places = collect_places_from_keyword(keyword)
    all_places.extend(places)

# 중복 제거 (URL 기준)
print(f"\n{'='*60}")
print(f"[🔄] 중복 제거 중...")
print(f"  - 중복 제거 전: {len(all_places)}개")

df = pd.DataFrame(all_places)

# URL에서 base_url 추출하여 중복 제거
df["_base_url"] = df["URL"].str.split("?").str[0]
df = df.drop_duplicates(subset="_base_url").drop(columns=["_base_url"])
df = df.reset_index(drop=True)

print(f"  - 중복 제거 후: {len(df)}개")

# CSV 저장
df.to_csv(CSV_OUTPUT, index=False, encoding="utf-8-sig")
print(f"\n[💾] {CSV_OUTPUT} 저장 완료 ({len(df)}개 장소)")

driver.quit()
print("\n[✅] URL 수집 완료!")