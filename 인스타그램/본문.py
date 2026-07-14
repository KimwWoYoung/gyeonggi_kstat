from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import random
import time

USERNAME = '***REMOVED***'
PASSWORD = '***REMOVED***'

# =============================================
# 크롤링할 URL 목록을 담은 CSV (url.py 실행 결과, 키워드/링크 컬럼 필요)
# =============================================
INPUT_CSV = "instagram_links_all.csv"
LINK_COLUMN = "링크"
KEYWORD_COLUMN = "키워드"
OUTPUT_FILE = "instagram_posts_202604_202606.xlsx"

# 수집 기간 (게시물 작성일 기준)
START_DATE = "2026-04-01"
END_DATE = "2026-06-30"


# =============================================
# 브라우저 설정
# =============================================
options = Options()
options.add_experimental_option("detach", True)
options.add_experimental_option("excludeSwitches", ["enable-logging"])
options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
})


# =============================================
# 로그인 관련 함수
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


def login(drv):
    drv.get('https://www.instagram.com/accounts/login/')
    time.sleep(3)

    username_input, password_input = find_login_fields(drv)
    if username_input is None:
        drv.save_screenshot("login_debug.png")
        raise Exception("❌ 로그인 필드를 찾지 못했습니다. login_debug.png 확인하세요.")

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


# =============================================
# 게시물 1개 크롤링
# =============================================
def crawl_post(drv, url):
    drv.get(url)
    time.sleep(3)

    try:
        content_div = WebDriverWait(drv, 10).until(
            EC.presence_of_element_located((By.XPATH, '//section/main/div/div[1]/div/div[2]'))
        )
        content = content_div.text
    except Exception as e:
        content = f"❌ 본문 추출 실패 → {e}"

    try:
        date = drv.find_element(By.TAG_NAME, 'time').get_attribute('datetime')
    except Exception:
        date = "날짜 추출 실패"

    return content, date


# =============================================
# 실행
# =============================================
login(driver)

df_links = pd.read_csv(INPUT_CSV)
df_links = df_links.dropna(subset=[LINK_COLUMN])
print(f"[📋] 크롤링할 URL {len(df_links)}개")
print(f"[수집 기간] {START_DATE} ~ {END_DATE} (게시물 작성일 기준, 범위 밖은 제외)")

results = []
in_range_count = 0
for idx, row in df_links.reset_index(drop=True).iterrows():
    url = row[LINK_COLUMN]
    keyword = row.get(KEYWORD_COLUMN, "")
    print(f"\n[{idx+1}/{len(df_links)}] 크롤링 중: {url}")
    try:
        content, date = crawl_post(driver, url)
    except Exception as e:
        content, date = f"❌ 크롤링 실패 → {e}", ""

    date_only = date[:10] if isinstance(date, str) and len(date) >= 10 else ""
    if not (START_DATE <= date_only <= END_DATE):
        print(f"  ⏭️ 기간 밖 (날짜: {date_only or '추출 실패'}) → 제외")
        time.sleep(random.uniform(2.5, 4.5))
        continue

    in_range_count += 1
    results.append({"키워드": keyword, "URL": url, "본문": content, "날짜": date_only})
    print(f"  본문 일부: {content[:30]}...")
    print(f"  날짜: {date_only}")

    time.sleep(random.uniform(2.5, 4.5))  # 요청 간격 랜덤화 (탐지 방지)

print(f"\n[✅] 기간 내 게시물 {in_range_count}/{len(df_links)}건")

# 저장
df_result = pd.DataFrame(results)
df_result.to_excel(OUTPUT_FILE, index=False)
print(f"\n[💾] {OUTPUT_FILE} 저장 완료")
print(f"[✅] 총 {len(results)}건 크롤링 완료")