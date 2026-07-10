from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time

USERNAME = '***REMOVED***'
PASSWORD = '***REMOVED***'

# 브라우저 설정
options = Options()
options.add_experimental_option("detach", True)
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})


# =============================================
# 아이디/비번 입력 관련 함수 (견고한 방식)
# =============================================
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
                    print(f"✅ 로그인 필드 탐색 성공: {u_by}={u_val}")
                    return u, p
            except Exception:
                continue
        return None, None

    u, p = try_locators()
    if u is not None:
        return u, p

    print("ℹ️ 기본 화면에서 못 찾음 → iframe 확인")
    iframes = drv.find_elements(By.TAG_NAME, "iframe")
    for idx, frame in enumerate(iframes):
        try:
            drv.switch_to.frame(frame)
            u, p = try_locators()
            if u is not None:
                print(f"✅ iframe[{idx}] 안에서 발견")
                return u, p
            drv.switch_to.default_content()
        except Exception:
            drv.switch_to.default_content()
            continue

    return None, None


def type_like_human(drv, element, text, field_label=""):
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
        print(f"⚠️ {field_label} send_keys로 값이 정상 입력 안 됨 (현재: '{actual}') → JS 방식으로 재시도")
        drv.execute_script("""
            const el = arguments[0];
            const val = arguments[1];
            const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            nativeSetter.call(el, val);
            el.dispatchEvent(new Event('input', { bubbles: true }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        """, element, text)
        time.sleep(0.3)
        actual = element.get_attribute("value")

    print(f"{'✅' if actual == text else '❌'} {field_label} 입력 확인: '{actual}'")
    return actual == text


# 1. 로그인
driver.get('https://www.instagram.com/accounts/login/')
time.sleep(3)

username_input, password_input = find_login_fields(driver)
if username_input is None:
    driver.save_screenshot("login_debug.png")
    raise Exception("❌ 로그인 필드를 찾지 못했습니다. login_debug.png 확인하세요.")

type_like_human(driver, username_input, USERNAME, "아이디")
type_like_human(driver, password_input, PASSWORD, "비밀번호")
time.sleep(0.5)
password_input.send_keys(Keys.ENTER)
print("✅ 로그인 시도 완료")

# 2. 팝업 닫기
time.sleep(5)
try:
    WebDriverWait(driver, 5).until(
        EC.element_to_be_clickable((By.XPATH, "//button[text()='나중에 하기']"))
    ).click()
    print("✅ 팝업 닫기 완료")
except:
    print("ℹ️ 팝업 없음")

# 3. 해시태그 페이지 이동
driver.get('https://www.instagram.com/explore/tags/구름산산림욕장/')
time.sleep(3)

try:
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/p/")]'))
    )
    print("🏷️ 해시태그 페이지 접속 완료")
except:
    print("❌ 게시물 로딩 실패")

# 4. 링크 수집 함수 (연속 3회 변화 없으면 자동 종료)
def get_post_links(driver, max_count=40000, delay=2, max_scroll=500, stop_after_no_change=3):
    links = set()
    scroll = 0
    prev_count = 0
    no_change_count = 0

    while len(links) < max_count and scroll < max_scroll:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(delay)

        elements = driver.find_elements(By.XPATH, '//a[contains(@href, "/p/")]')
        for elem in elements:
            href = elem.get_attribute("href")
            if href:
                links.add(href)

        scroll += 1
        curr_count = len(links)
        print(f"🔄 스크롤 {scroll}회 | 현재 수집 링크 수: {curr_count}")

        if curr_count == prev_count:
            no_change_count += 1
            print(f"  ⏸️ 변화 없음 ({no_change_count}/{stop_after_no_change})")
            if no_change_count >= stop_after_no_change:
                print(f"✅ 연속 {stop_after_no_change}회 링크 수 변화 없음 → 마지막으로 판단하고 종료")
                break
        else:
            no_change_count = 0

        prev_count = curr_count

    return list(links)

# 5. 링크 수집 실행
links = get_post_links(driver, max_count=40000, delay=2, max_scroll=500, stop_after_no_change=3)

# 6. 저장
df = pd.DataFrame({"링크": links})
df.to_csv("구름산산림욕장.csv", index=False, encoding="utf-8-sig")
print("✅ 총 수집된 링크 수:", len(links))
print("📁 '구름산산림욕장.csv' 저장 완료!")