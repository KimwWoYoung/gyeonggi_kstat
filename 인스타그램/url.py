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

# 관광지점 57곳 검색어 (경기관광 SNS 분석 키워드 엑셀의 '2. 관광지점' 시트와 동일)
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

OUTPUT_CSV = "instagram_links_all.csv"

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

# 3. 링크 수집 함수 (연속 3회 변화 없으면 자동 종료)
# 57개 키워드를 전부 훑어야 하므로 키워드당 스크롤 상한을 적당히 낮춰둔다.
# (인기 명소는 MAX_SCROLL_PER_KEYWORD 를 늘려 더 깊이 수집할 수 있다.)
MAX_SCROLL_PER_KEYWORD = 150


def get_post_links(driver, max_count=40000, delay=2, max_scroll=MAX_SCROLL_PER_KEYWORD, stop_after_no_change=3):
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


# 4. 키워드 57개 전체 순회하며 해시태그 페이지에서 링크 수집
# (인스타그램 해시태그는 공백을 허용하지 않으므로 태그 자체는 공백 제거,
#  결과 테이블의 '키워드' 컬럼에는 원래 관광지점명을 그대로 남긴다)
all_rows = []

for idx, keyword in enumerate(KEYWORDS, start=1):
    tag = keyword.replace(" ", "")
    print(f"\n{'='*60}")
    print(f"[{idx}/{len(KEYWORDS)}] 키워드: {keyword} (태그: #{tag})")
    print(f"{'='*60}")

    driver.get(f'https://www.instagram.com/explore/tags/{tag}/')
    time.sleep(3)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "/p/")]'))
        )
        print("🏷️ 해시태그 페이지 접속 완료")
    except Exception:
        print("❌ 게시물 로딩 실패 (게시물이 없거나 페이지 구조 변경) → 건너뜀")
        continue

    links = get_post_links(driver)
    print(f"✅ '{keyword}' 수집된 링크 수: {len(links)}")

    for link in links:
        all_rows.append({"키워드": keyword, "링크": link})

    # 키워드 하나 끝날 때마다 누적 저장 (중간에 중단돼도 그동안 수집한 결과는 보존)
    pd.DataFrame(all_rows).to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

print(f"\n✅ 전체 수집 완료. 총 {len(all_rows)}건")
print(f"📁 '{OUTPUT_CSV}' 저장 완료!")