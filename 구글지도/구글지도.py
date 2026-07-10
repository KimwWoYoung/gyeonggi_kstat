from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
import os

# =============================================
# 설정 - URL 직접 입력
# =============================================
PLACES = [
    {
        "장소명": "구름산 산림욕장",
        "지역": "경기도 광명시",
        "URL": "https://www.google.com/maps/place/%EA%B5%AC%EB%A6%84%EC%82%B0+%EC%82%B0%EB%A6%BC%EC%9A%95%EC%9E%A5/data=!3m2!1e3!4b1!4m6!3m5!1s0x357b618951b54019:0x705d71610a309f05!8m2!3d37.4549663!4d126.8772253!16s%2Fg%2F11j42ts73z?entry=ttu&g_ep=EgoyMDI2MDYyMi4wIKXMDSoASAFQAw%3D%3D"
    }
]

OUTPUT_FILE = "광명시_리뷰.xlsx"

# =============================================
# 브라우저 설정 - 새 크롬 창을 직접 실행
# =============================================
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
# 기존에 쓰는 크롬 프로필 대신, 자동화 전용 새 프로필 폴더 사용
# → 이미 열려있는 크롬과 충돌 없이 새 창이 뜹니다.
options.add_argument(r"--user-data-dir=C:\Users\kstat\selenium_profile")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option("useAutomationExtension", False)

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

all_restaurant_data = []
all_reviews_data = []

for idx, place in enumerate(PLACES):
    url = place['URL']
    place_name = place['장소명']
    region = place['지역']

    print(f"\n{'='*60}")
    print(f"[{idx+1}/{len(PLACES)}] 처리 중: {place_name}")
    print(f"{'='*60}")

    try:
        driver.get(url)
        time.sleep(3)

        # 로그인 팝업 ESC로 닫기
        try:
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1)
            print("✅ 팝업 닫기")
        except:
            pass

        time.sleep(2)

        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf')))
            print("✅ 페이지 로드 완료")
        except:
            print("[⚠️] 페이지 로드 확인 실패, 계속 진행...")
            time.sleep(3)

        try:
            name = driver.find_element(By.CSS_SELECTOR, 'h1.DUwDvf').text
        except:
            name = place_name

        try:
            address = driver.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]').text
        except:
            address = ""

        try:
            rating = driver.find_element(By.CSS_SELECTOR, 'div.F7nice span:nth-child(1)').text
        except:
            rating = ""

        print(f"  장소명: {name}")
        print(f"  주소: {address}")
        print(f"  별점: {rating}")

        reviews_data = []
        review_button_clicked = False

        # 리뷰 버튼 클릭
        try:
            review_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "리뷰")]')))
            driver.execute_script("arguments[0].click();", review_button)
            print("✅ 리뷰 버튼 클릭 성공 (aria-label)")
            review_button_clicked = True
        except:
            try:
                button_container = wait.until(EC.presence_of_element_located((
                    By.XPATH, '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[3]/div/div'
                )))
                buttons = button_container.find_elements(By.XPATH, './button')
                button_count = len(buttons)
                review_button_index = 3 if button_count == 4 else 2
                driver.execute_script("arguments[0].click();", buttons[review_button_index - 1])
                print(f"✅ 리뷰 버튼 클릭 성공 (버튼 {review_button_index}/{button_count})")
                review_button_clicked = True
            except Exception as e:
                print(f"[⚠️] 리뷰 버튼 클릭 실패: {e}")

        if review_button_clicked:
            time.sleep(3)

        # 리뷰 컨테이너 찾기
        review_container = None
        for div_index in [9, 8, 10, 11]:
            try:
                xpath = f'//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[{div_index}]'
                review_container = WebDriverWait(driver, 8).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )
                test_items = review_container.find_elements(By.XPATH, './/div/div/div[4]')
                if len(test_items) > 0:
                    print(f"✅ 리뷰 컨테이너 찾기 성공 (div[{div_index}])")
                    break
                review_container = None
            except:
                continue

        if review_container is None:
            try:
                review_container = driver.find_element(By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf')
                print("✅ 리뷰 컨테이너 찾기 성공 (CSS)")
            except:
                print("[⚠️] 리뷰 컨테이너를 찾지 못했습니다.")

        if review_container:
            try:
                scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf')
            except:
                scrollable_div = review_container

            target_reviews = 200
            max_no_change = 3
            no_change_count = 0
            prev_count = len(review_container.find_elements(By.XPATH, './/div/div/div[4]'))
            print(f"[📜] 리뷰 스크롤 시작 (초기: {prev_count}개)")

            for i in range(20):
                if prev_count >= target_reviews:
                    break
                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                time.sleep(2)
                curr_count = len(review_container.find_elements(By.XPATH, './/div/div/div[4]'))
                if curr_count > prev_count:
                    print(f"  스크롤 {i+1}회 - {prev_count} → {curr_count}")
                    prev_count = curr_count
                    no_change_count = 0
                else:
                    no_change_count += 1
                    if no_change_count >= max_no_change:
                        print(f"  연속 {max_no_change}회 변화 없음. 스크롤 종료.")
                        break

            time.sleep(2)
            review_items = review_container.find_elements(By.XPATH, './/div/div/div[4]')
            review_items = list(dict.fromkeys(review_items))
            print(f"[📝] 최종 리뷰: {len(review_items)}개")

            review_text_elements = driver.find_elements(By.CSS_SELECTOR, 'div.MyEned span.wi17pd')

            for i, review_item in enumerate(review_items):
                try:
                    review_rating = ""
                    try:
                        rating_elem = review_item.find_element(By.CSS_SELECTOR, 'span.kvMYJc')
                        review_rating = rating_elem.get_attribute("aria-label") or ""
                        numbers = re.findall(r'\d+', review_rating)
                        if numbers:
                            review_rating = numbers[0]
                    except:
                        pass

                    review_date = ""
                    try:
                        review_date = review_item.find_element(By.XPATH, './div[1]/span[2]').text.strip()
                    except:
                        pass

                    review_text = ""
                    for selector in [
                        lambda: review_item.find_element(By.XPATH, './div[2]/div/span[1]').text.strip(),
                        lambda: review_item.find_element(By.CSS_SELECTOR, 'span.wi17pd').text.strip(),
                        lambda: review_text_elements[i].text.strip() if i < len(review_text_elements) else "",
                    ]:
                        try:
                            review_text = selector()
                            if review_text:
                                break
                        except:
                            continue

                    if review_rating or review_text:
                        reviews_data.append({
                            "장소명": name,
                            "URL": url,
                            "ID": i + 1,
                            "별점": review_rating,
                            "기간": review_date,
                            "리뷰": review_text
                        })
                except Exception as e:
                    print(f"[⚠️] 리뷰 {i+1} 추출 오류: {e}")
                    continue

            print(f"[✅] 리뷰 {len(reviews_data)}개 추출 완료")

        all_restaurant_data.append({
            "지역": region,
            "장소명": name,
            "주소": address,
            "별점": rating,
            "URL": url,
            "리뷰개수": len(reviews_data)
        })
        all_reviews_data.extend(reviews_data)

    except Exception as e:
        print(f"[❌] 오류 발생: {e}")
        import traceback
        traceback.print_exc()

# 저장
script_dir = os.path.dirname(os.path.abspath(__file__))
output_path = os.path.join(script_dir, OUTPUT_FILE)

with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
    pd.DataFrame(all_restaurant_data).to_excel(writer, sheet_name='장소정보', index=False)
    pd.DataFrame(all_reviews_data).to_excel(writer, sheet_name='리뷰', index=False)

print(f"\n[💾] {output_path} 저장 완료")
print(f"[📊] 장소정보: {len(all_restaurant_data)}개 / 리뷰: {len(all_reviews_data)}개")

driver.quit()
print("\n[✅] 완료!")