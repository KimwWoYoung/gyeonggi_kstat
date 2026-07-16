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
import time

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

URL = (
    "https://www.google.com/maps/place/%EA%B5%AC%EB%A6%84%EC%82%B0+%EC%82%B0%EB%A6%BC%EC%9A%95%EC%9E%A5/"
    "data=!3m1!1e3!4m8!3m7!1s0x357b618951b54019:0x705d71610a309f05!8m2!3d37.4549663!4d126.8772253"
    "!9m1!1b1!16s%2Fg%2F11j42ts73z?entry=ttu&g_ep=EgoyMDI2MDcxMy4wIKXMDSoASAFQAw%3D%3D"
)

CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_test_single"))

options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
options.add_argument("--profile-directory=Default")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

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

    try:
        review_container = driver.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb.kA9KIf.dS8AEf")
        items = review_container.find_elements(By.XPATH, ".//div/div/div[4]")
        print(f"✅ 리뷰 컨테이너 찾음, 현재 로드된 리뷰 항목 수: {len(items)}")
    except Exception as e:
        print("[❌] 리뷰 컨테이너 못 찾음:", e)

print("\n[안내] 지금 뜬 크롬 창을 직접 보면서 실제 화면 상태(리뷰 패널 열렸는지, 정렬 메뉴 모양 등)를 확인해보세요.")
input("확인 다 했으면 Enter 키를 눌러 브라우저를 종료합니다...")
driver.quit()
print("[종료]")
