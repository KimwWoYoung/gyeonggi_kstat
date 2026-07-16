"""
test_single_url.py
장소 URL 1개로 리뷰 크롤링을 테스트/디버깅하기 위한 스크립트.
2_crawl_reviews.py는 건드리지 않고, 여기서 셀렉터/로직을 확인한 뒤
문제 없으면 2_crawl_reviews.py 쪽에 반영한다.

사용법:
    URL 변수를 원하는 장소 URL로 바꾸고 실행
    python test_single_url.py

주의:
    config.py의 CHROME_USER_DATA_DIR(~/selenium_profile_gyeonggi)을 다른
    스크립트/창이 이미 쓰고 있으면 크롬이 불안정해지다 죽을 수 있어서,
    이 테스트는 별도의 전용 프로필(~/selenium_profile_test_single)을 쓴다.
    실행 전에 다른 셀레니움 크롬 창이 떠 있으면 다 닫아두는 걸 권장.
"""

import os
import re
import time

import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

TARGET_REVIEWS = 50  # 테스트용으로 적당히. 실제 파이프라인은 200개.
OUTPUT_CSV = "test_single_url_reviews.csv"

URL = (
    "https://www.google.com/maps/place/%EA%B5%AC%EB%A6%84%EC%82%B0+%EC%82%B0%EB%A6%BC%EC%9A%95%EC%9E%A5/"
    "data=!3m1!1e3!4m8!3m7!1s0x357b618951b54019:0x705d71610a309f05!8m2!3d37.4549663!4d126.8772253"
    "!9m1!1b1!16s%2Fg%2F11j42ts73z?entry=ttu&g_ep=EgoyMDI2MDcxMy4wIKXMDSoASAFQAw%3D%3D"
)

# prefs로 로그인 차단해도 계속 2단계 인증이 뜨면(조직 정책이 강제 로그인일 경우)
# True로 바꿔서 --guest 모드로 시도해보세요. 게스트 모드는 아예 계정을 붙일 수
# 없는 프로필이라 강제 로그인 정책도 대부분 우회됨. 단, --user-data-dir과 같이
# 못 쓰기 때문에 이 경우 프로필 경로는 무시된다.
USE_GUEST_MODE = False

CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_test_single"))

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

# GPU 가속 관련 크래시("GPU state invalid after WaitForGetOffsetInRange") 방지.
# 원격데스크톱/가상머신 환경에서 크롬 GPU 프로세스가 죽으면서 창이 통째로
# 꺼지는 문제 대응.
options.add_argument("--disable-gpu")
options.add_argument("--disable-software-rasterizer")
options.add_argument("--disable-dev-shm-usage")

if USE_GUEST_MODE:
    options.add_argument("--guest")
else:
    options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    options.add_argument("--profile-directory=Default")

    # 이 프로필이 조직 계정 등으로 자동 로그인/동기화되는 것을 최대한 막는다.
    # (로그인된 상태에서 자동화 브라우저로 접속하면 구글이 "의심스러운 로그인"으로
    # 판단해 2단계 인증을 띄우는 경우가 있음 — 리뷰는 로그인 없이도 볼 수 있으므로
    # 애초에 로그인 자체가 안 일어나게 하는 게 목적)
    options.add_argument("--disable-sync")
    options.add_argument("--disable-features=SigninInterceptBubble,ChromeSigninInterceptWelcome")
    options.add_experimental_option(
        "prefs",
        {
            "credentials_enable_service": False,
            "signin.allowed_on_next_startup": False,
            "profile.password_manager_enabled": False,
        },
    )

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.set_page_load_timeout(30)
wait = WebDriverWait(driver, 15)

print(f"[GO] {URL}\n")

try:
    driver.get(URL)
except Exception as e:
    print(f"[⚠️] 페이지 로드 타임아웃/오류 (계속 진행): {e}")

time.sleep(3)
print("현재 URL:", driver.current_url)
print("타이틀:", driver.title)

try:
    name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))).text
    print("✅ 장소명:", name)
except Exception as e:
    print("[❌] 장소명(h1.DUwDvf) 못 찾음:", e)

try:
    address = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]').text
    print("✅ 주소:", address)
except Exception as e:
    print("[⚠️] 주소 못 찾음:", e)

try:
    rating = driver.find_element(By.CSS_SELECTOR, "div.F7nice span:nth-child(1)").text
    print("✅ 별점:", rating)
except Exception as e:
    print("[⚠️] 별점 못 찾음:", e)

review_button_clicked = False
try:
    review_button = wait.until(
        EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "리뷰")]'))
    )
    driver.execute_script("arguments[0].click();", review_button)
    review_button_clicked = True
    print("✅ 리뷰 버튼 클릭 성공")
except Exception as e:
    print("[❌] 리뷰 버튼 클릭 실패:", e)

time.sleep(3)

if review_button_clicked:
    try:
        sort_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "정렬")]'))
        )
        driver.execute_script("arguments[0].click();", sort_button)
        time.sleep(1)
        recent_option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//div[@role="menuitemradio"][contains(., "최신순")]'))
        )
        driver.execute_script("arguments[0].click();", recent_option)
        time.sleep(2)
        print("✅ 정렬: 최신순으로 변경 성공")
    except Exception as e:
        print("[⚠️] 정렬(최신순) 변경 실패:", e)

    reviews_data = []
    try:
        review_container = driver.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb.kA9KIf.dS8AEf")
        print("✅ 리뷰 컨테이너 찾음")

        # 스크롤해서 리뷰 더 로드
        prev_count = len(review_container.find_elements(By.XPATH, ".//div/div/div[4]"))
        print(f"[📜] 초기 리뷰 개수: {prev_count}")
        no_change_count = 0
        for i in range(15):
            if prev_count >= TARGET_REVIEWS:
                break
            driver.execute_script(
                "arguments[0].scrollTop = arguments[0].scrollHeight", review_container
            )
            time.sleep(2)
            curr_count = len(review_container.find_elements(By.XPATH, ".//div/div/div[4]"))
            if curr_count > prev_count:
                print(f"  스크롤 {i + 1}회 - {prev_count} → {curr_count}")
                prev_count = curr_count
                no_change_count = 0
            else:
                no_change_count += 1
                if no_change_count >= 3:
                    print("  연속 3회 변화 없음. 스크롤 종료.")
                    break

        review_items = review_container.find_elements(By.XPATH, ".//div/div/div[4]")
        review_items = list(dict.fromkeys(review_items))
        print(f"[📝] 최종 리뷰 항목 수: {len(review_items)}")

        for i, review_item in enumerate(review_items):
            review_rating = ""
            try:
                rating_elem = review_item.find_element(By.CSS_SELECTOR, "span.kvMYJc")
                review_rating = rating_elem.get_attribute("aria-label") or ""
                numbers = re.findall(r"\d+", review_rating)
                if numbers:
                    review_rating = numbers[0]
            except Exception:
                pass

            review_date = ""
            try:
                review_date = review_item.find_element(By.XPATH, "./div[1]/span[2]").text.strip()
            except Exception:
                pass

            review_text = ""
            for selector in [
                lambda: review_item.find_element(By.XPATH, "./div[2]/div/span[1]").text.strip(),
                lambda: review_item.find_element(By.CSS_SELECTOR, "span.wi17pd").text.strip(),
            ]:
                try:
                    review_text = selector()
                    if review_text:
                        break
                except Exception:
                    continue

            if review_rating or review_text:
                reviews_data.append({
                    "ID": i + 1,
                    "별점": review_rating,
                    "기간": review_date,
                    "리뷰": review_text,
                })

        print(f"[✅] 본문/별점/날짜 추출 완료: {len(reviews_data)}건")
    except Exception as e:
        print("[❌] 리뷰 컨테이너/추출 실패:", e)

    if reviews_data:
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUTPUT_CSV)
        pd.DataFrame(reviews_data).to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"[💾] {out_path} 저장 완료")
        for r in reviews_data[:5]:
            print(f"  - [{r['별점']}점/{r['기간']}] {r['리뷰'][:40]}")

try:
    input("\n확인 다 했으면 Enter 키를 눌러 브라우저를 종료합니다 (크롬이 이미 꺼졌다면 그냥 Enter)...")
except Exception:
    pass
finally:
    try:
        driver.quit()
    except Exception:
        pass
print("[종료]")
