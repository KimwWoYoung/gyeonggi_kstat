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
    },
    {
        "장소명": "양평양떼목장",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%96%91%ED%8F%89+%EC%96%91%EB%96%BC%EB%AA%A9%EC%9E%A5/data=!3m1!1e3!4m8!3m7!1s0x35633f29dc9a571b:0x9bd56a4558680c0b!8m2!3d37.5150677!4d127.6283823!9m1!1b1!16s%2Fg%2F11t30kqlkm?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "바라산자연휴양림",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%9D%98%EC%99%95+%EB%B0%94%EB%9D%BC%EC%82%B0%EC%9E%90%EC%97%B0%ED%9C%B4%EC%96%91%EB%A6%BC/data=!3m1!1e3!4m8!3m7!1s0x357b5ebd0537b8e3:0x4a68c80fd0f9050d!8m2!3d37.3728728!4d127.0196199!9m1!1b1!16s%2Fg%2F11b90gvj3w?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "행주산성",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%96%89%EC%A3%BC%EC%82%B0%EC%84%B1/data=!3m1!1e3!4m8!3m7!1s0x357c9b09fc193cfd:0x39a4c1019b970dc0!8m2!3d37.5955733!4d126.8281509!9m1!1b1!16s%2Fg%2F12163_mv?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "남한산성행궁",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EB%82%A8%ED%95%9C%EC%82%B0%EC%84%B1+%ED%96%89%EA%B6%81/data=!3m1!1e3!4m8!3m7!1s0x357caef0b390e3df:0x45058294315870a3!8m2!3d37.4786977!4d127.1822003!9m1!1b1!16s%2Fg%2F11bwf3gz_y?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "포천아트밸리",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%8F%AC%EC%B2%9C%EC%95%84%ED%8A%B8%EB%B0%B8%EB%A6%AC/data=!3m1!1e3!4m8!3m7!1s0x357cd595c3388bc5:0x11a4e6805d112215!8m2!3d37.9231399!4d127.2371423!9m1!1b1!16s%2Fg%2F125n3s21f?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "헤이리예술마을",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%97%A4%EC%9D%B4%EB%A6%AC+%EC%98%88%EC%88%A0%EB%A7%88%EC%9D%84/data=!3m1!1e3!4m8!3m7!1s0x357c8b8a0a9d3671:0xd2b2c34c16b1778c!8m2!3d37.7888414!4d126.698722!9m1!1b1!16s%2Fg%2F123976rp?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "수원화성박물관",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%88%98%EC%9B%90%ED%99%94%EC%84%B1%EB%B0%95%EB%AC%BC%EA%B4%80/data=!3m1!1e3!4m8!3m7!1s0x357b434aa22bf7e9:0x91c4cb9e8e1d5d8!8m2!3d37.2825914!4d127.0193606!9m1!1b1!16s%2Fg%2F1q5hkp55r?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "융건릉",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%9C%B5%EB%A6%89%EA%B3%BC+%EA%B1%B4%EB%A6%89/data=!3m1!1e3!4m8!3m7!1s0x357b41848f6feda5:0x8349440211ac6b07!8m2!3d37.2119224!4d126.9906149!9m1!1b1!16s%2Fg%2F11bc6n8zwv?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "세종대왕 영릉",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%98%81%EB%A6%89(%E5%AF%A7%E9%99%B5)/data=!3m1!1e3!4m8!3m7!1s0x35635dba48c30817:0x373e9094ba1d184!8m2!3d37.3142424!4d127.6087146!9m1!1b1!16s%2Fg%2F120_4mb8?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "장릉",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EA%B9%80%ED%8F%AC%EC%9E%A5%EB%A6%89/data=!3m1!1e3!4m8!3m7!1s0x357c83f14cf860bd:0x89319df85e432197!8m2!3d37.6128776!4d126.7111674!9m1!1b1!16s%2Fm%2F0nbdxjk?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "동구릉",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EB%8F%99%EA%B5%AC%EB%A6%89/data=!3m1!1e3!4m8!3m7!1s0x357cb757ad3dbdf7:0xe84ca3c3a01a84a!8m2!3d37.6201143!4d127.1279811!9m1!1b1!16s%2Fm%2F0nbdkyh?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "통일전망대",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%98%A4%EB%91%90%EC%82%B0%ED%86%B5%EC%9D%BC%EC%A0%84%EB%A7%9D%EB%8C%80/data=!3m1!1e3!4m8!3m7!1s0x357c895e8d9d4c93:0xa9fe5d22c8be1a70!8m2!3d37.773117!4d126.6772249!9m1!1b1!16s%2Fm%2F0nbfzm2?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "신구대학교식물원",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%8B%A0%EA%B5%AC%EB%8C%80%ED%95%99%EA%B5%90+%EC%8B%9D%EB%AC%BC%EC%9B%90/data=!3m1!1e3!4m8!3m7!1s0x357ca709b5b5ac33:0x6f77387f3f04a3cc!8m2!3d37.4339552!4d127.080805!9m1!1b1!16s%2Fg%2F1tdbtq2r?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "세미원",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%84%B8%EB%AF%B8%EC%9B%90/data=!3m1!1e3!4m8!3m7!1s0x35634c9e5e533d9b:0xd41f9edb4e23375d!8m2!3d37.5401119!4d127.3241038!9m1!1b1!16s%2Fg%2F11bw1hklb_?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "시흥갯골생태공원",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%8B%9C%ED%9D%A5%EA%B0%AF%EA%B3%A8%EC%83%9D%ED%83%9C%EA%B3%B5%EC%9B%90/data=!3m1!1e3!4m8!3m7!1s0x357b7acb729205ff:0x8c477d5ed257cd14!8m2!3d37.3909839!4d126.780835!9m1!1b1!16s%2Fg%2F11csqs40wj?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "수리산입구",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%88%98%EB%A6%AC%EC%82%B0/data=!3m1!1e3!4m8!3m7!1s0x357b66542ed1e2f3:0x84649be1b22e1c28!8m2!3d37.3661968!4d126.9027047!9m1!1b1!16s%2Fg%2F1q6j8dhmy?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "잣향기푸른숲",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EA%B2%BD%EA%B8%B0%EB%8F%84+%EC%9E%A3%ED%96%A5%EA%B8%B0+%ED%91%B8%EB%A5%B8+%EC%88%B2/data=!3m1!1e3!4m8!3m7!1s0x35632db0a9a0da23:0x842891d344839a5d!8m2!3d37.7721391!4d127.3391224!9m1!1b1!16s%2Fg%2F11h4fjhk0k?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "비둘기낭폭포",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EB%B9%84%EB%91%98%EA%B8%B0%EB%82%AD+%ED%8F%AD%ED%8F%AC/data=!3m1!1e3!4m8!3m7!1s0x357d2de40555e0d7:0x145da909f862d98d!8m2!3d38.079913!4d127.2170958!9m1!1b1!16s%2Fg%2F11fx_1fqmw?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "두물머리",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EB%91%90%EB%AC%BC%EB%A8%B8%EB%A6%AC/data=!3m1!1e3!4m8!3m7!1s0x35634ca2b626387b:0x2572c4b44ed5c1b!8m2!3d37.5347371!4d127.3178912!9m1!1b1!16s%2Fg%2F1tcyppn1?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "마장호수",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EB%A7%88%EC%9E%A5%ED%98%B8%EC%88%98+%EC%B6%9C%EB%A0%81%EB%8B%A4%EB%A6%AC/data=!3m1!1e3!4m8!3m7!1s0x357ceac3d03a4179:0xb5e3206808587e07!8m2!3d37.7756518!4d126.9278262!9m1!1b1!16s%2Fg%2F11gdqsyx3k?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "포천한탄강하늘다리",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%8F%AC%EC%B2%9C+%ED%95%9C%ED%83%84%EA%B0%95+%ED%95%98%EB%8A%98%EB%8B%A4%EB%A6%AC/data=!3m1!1e3!4m8!3m7!1s0x357d2de169893fd9:0xc3e965901487d0e6!8m2!3d38.084388!4d127.2179088!9m1!1b1!16s%2Fg%2F11h1_09d0v?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "재인폭포",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%9E%AC%EC%9D%B8%ED%8F%AD%ED%8F%AC/data=!3m1!1e3!4m8!3m7!1s0x357d2f8e16bb2331:0x80d70e30b2b8ddef!8m2!3d38.0774088!4d127.1432776!9m1!1b1!16s%2Fg%2F11q4bqp8x_?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "화성행궁",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%99%94%EC%84%B1%ED%96%89%EA%B6%81/data=!3m1!1e3!4m8!3m7!1s0x357b43340a137667:0x692f2601c8996039!8m2!3d37.2819666!4d127.013727!9m1!1b1!16s%2Fg%2F121f8wz5?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "제3땅굴",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%A0%9C3%EB%95%85%EA%B5%B4/data=!3m1!1e3!4m8!3m7!1s0x357cf3f5e5ef704b:0x698d9c841047718f!8m2!3d37.916653!4d126.6982609!9m1!1b1!16s%2Fg%2F11rz2px_d2?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "송학김전시관",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%ED%95%B4%EC%B0%AC%EC%86%A1%ED%95%99%EA%B9%80/data=!3m1!1e3!4m8!3m7!1s0x357c9b16d13fb34f:0x6e85f225788e24e8!8m2!3d37.6026478!4d126.8228788!9m1!1b1!16s%2Fg%2F1wbrvqf9?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "가평레일파크",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EA%B0%80%ED%8F%89%EB%A0%88%EC%9D%BC%ED%8C%8C%ED%81%AC/data=!3m1!1e3!4m8!3m7!1s0x35632779fac61615:0x6e7609f2b9ff7975!8m2!3d37.8288388!4d127.5157265!9m1!1b1!16s%2Fg%2F11bytsy0bm?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "대장금파크",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%9A%A9%EC%9D%B8+%EB%8C%80%EC%9E%A5%EA%B8%88%ED%8C%8C%ED%81%AC/data=!3m1!1e3!4m8!3m7!1s0x3564b307d0934827:0x3ff637eaf7f693c3!8m2!3d37.1212087!4d127.3368503!9m1!1b1!16s%2Fm%2F0_82t74?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
    {
        "장소명": "스타필드수원",
        "지역": "",
        "URL": "https://www.google.com/maps/place/%EC%8A%A4%ED%83%80%ED%95%84%EB%93%9C+%EC%88%98%EC%9B%90/data=!3m1!1e3!4m8!3m7!1s0x357b4367be4ee657:0x8a8b001a29248155!8m2!3d37.2873665!4d126.9912075!9m1!1b1!16s%2Fg%2F11txcqsqx_?entry=ttu&g_ep=EgoyMDI2MDcxNS4wIKXMDSoASAFQAw%3D%3D"
    },
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