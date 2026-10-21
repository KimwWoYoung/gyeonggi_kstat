"""
2_crawl_reviews.py
1_collect_urls.py(또는 수작업으로 검증해둔 google_maps_urls_gyeonggi.csv)의
장소 URL을 하나씩 열어 장소정보 + 리뷰(별점/날짜/본문)를 수집한다.

리뷰 정렬:
    리뷰 탭을 연 뒤 정렬을 '관련성순'(기본값)에서 '최신순'으로 바꾸고
    나서 스크롤한다. 먼저 '최신순' 메뉴 항목을 선택자로 찾아 클릭을
    시도하고, 그게 실패하면 선택자 없이 키보드(아래 방향키 + Enter)로
    선택하는 방식으로 한 번 더 시도한다. 그래도 실패하면 기본 정렬로
    계속 진행한다 (디버깅용으로 정렬 버튼 클릭 직후 화면을
    sort_debug.png에 저장).

중간저장 / 이어하기:
    장소 1곳을 다 처리할 때마다 리뷰 결과를 CHECKPOINT_CSV에 즉시
    append한다. 재실행하면 이미 CHECKPOINT_CSV에 있는 장소(URL 기준)는
    건너뛰고 남은 곳부터 이어서 처리한다. 크롬이 크래시로 죽으면
    드라이버를 자동으로 새로 띄우고 계속 진행한다.

날짜 필터:
    구글 리뷰는 날짜가 "3개월 전" 같은 상대 날짜로만 나오므로, 오늘
    날짜 기준으로 역산해 절대 날짜로 근사 변환(parse_relative_date_kr)한
    뒤 START_DATE~END_DATE 안에 드는 것만 최종 결과에 포함한다. 최대
    수 주 정도 오차가 있을 수 있다. 필터링 전 원본은 CHECKPOINT_CSV에
    그대로 남아있다.

사용법:
    python 1_collect_urls.py 를 먼저 실행해 CSV를 만든 뒤
    python 2_crawl_reviews.py 실행
"""

import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import InvalidSessionIdException, WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from config import CSV_OUTPUT

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, CSV_OUTPUT)
CHECKPOINT_CSV = os.path.join(SCRIPT_DIR, "google_maps_reviews_checkpoint.csv")
OUTPUT_XLSX = os.path.join(SCRIPT_DIR, "gyeonggi_reviews_202607_202609.xlsx")

# 이미 다른 실행에서 앞쪽 몇 곳을 끝내둔 경우에만 0보다 크게 설정.
# (체크포인트로 이미 자동 이어하기가 되므로 보통은 0으로 둔다.)
SKIP_FIRST_N = 0

TARGET_REVIEWS = 200

# 수집 기간 (리뷰 작성일 기준)
START_DATE = "2026-07-01"
END_DATE = "2026-09-30"

RESULT_COLUMNS = ["키워드", "장소명", "지역", "URL", "ID", "별점", "기간", "리뷰"]
PLACE_COLUMNS = ["키워드", "지역", "장소명", "주소", "별점", "URL", "리뷰개수"]

# 게스트 모드(로그인 없음)에서는 '로그인하여 Google 지도를 최대한
# 활용하세요' 팝업이 계속 다시 떠서 정렬 메뉴를 가리는 문제가 있었다.
# True로 바꾸면 게스트 모드로 돌아간다(조직 정책 등으로 로그인 자체가
# 막히는 경우에만 사용).
USE_GUEST_MODE = False

# 전용 자동화 프로필을 쓴다 (크롬 기본 경로가 아니라서 자동화 접속 차단에
# 안 걸림). 이 프로필로 처음 한 번만 수동 로그인해두면, 로그인 쿠키가 이
# 폴더에 저장되므로 다음 실행부터는 로그인 상태가 유지된다. 로그인돼
# 있으면 '로그인하여 Google 지도를 최대한 활용하세요' 팝업도 안 뜬다.
CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_gmaps"))
CHROME_PROFILE = "Default"


def parse_relative_date_kr(text: str, reference: datetime) -> "datetime | None":
    """구글 리뷰의 상대적 날짜 텍스트("3개월 전" 등)를 절대 날짜로 근사 변환한다.
    일/주/개월/년 단위이므로 실제 작성일과 최대 수 주 정도 오차가 있을 수 있다."""
    text = (text or "").strip()
    if not text:
        return None
    if "방금" in text:
        return reference
    m = re.match(r"(\d+)\s*(초|분|시간|일|주|개월|달|년)\s*전", text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    if unit == "초":
        return reference - timedelta(seconds=n)
    if unit == "분":
        return reference - timedelta(minutes=n)
    if unit == "시간":
        return reference - timedelta(hours=n)
    if unit == "일":
        return reference - timedelta(days=n)
    if unit == "주":
        return reference - timedelta(weeks=n)
    if unit in ("개월", "달"):
        return reference - timedelta(days=n * 30)
    if unit == "년":
        return reference - timedelta(days=n * 365)
    return None


def build_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # GPU 가속 관련 크래시("GPU state invalid after WaitForGetOffsetInRange") 방지.
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-dev-shm-usage")

    if USE_GUEST_MODE:
        options.add_argument("--guest")
    else:
        # 평소 쓰는 크롬 프로필을 그대로 재사용 - 이미 로그인된 세션을 가져다
        # 쓰는 것이 목적이므로 로그인/동기화를 막는 옵션은 넣지 않는다.
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        options.add_argument(f"--profile-directory={CHROME_PROFILE}")

    drv = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    drv.set_page_load_timeout(30)
    return drv


def load_checkpoint() -> pd.DataFrame:
    if os.path.exists(CHECKPOINT_CSV):
        return pd.read_csv(CHECKPOINT_CSV, encoding="utf-8-sig", dtype=str)
    return pd.DataFrame(columns=RESULT_COLUMNS)


def append_checkpoint(rows: list[dict]) -> None:
    if not rows:
        return
    write_header = not os.path.exists(CHECKPOINT_CSV)
    pd.DataFrame(rows, columns=RESULT_COLUMNS).to_csv(
        CHECKPOINT_CSV, mode="a", index=False, header=write_header, encoding="utf-8-sig"
    )


def _reraise_if_session_dead(e: Exception) -> None:
    """크롬이 실제로 크래시/연결 끊김 상태인 예외는 숨기지 않고 다시 던진다.
    그래야 main()의 크래시 복구 로직(드라이버 재시작)이 작동한다. 그냥
    '요소를 못 찾음' 같은 정상적인 실패는 그대로 삼켜지고 넘어간다."""
    if isinstance(e, InvalidSessionIdException):
        raise e
    msg = str(e).lower()
    if "invalid session id" in msg or "chrome not reachable" in msg or "session deleted" in msg \
            or "disconnected" in msg or "target window already closed" in msg:
        raise e


def robust_click(drv, element) -> None:
    """먼저 실제 마우스 클릭(.click())을 시도한다. 구글의 일부 드롭다운/메뉴
    컴포넌트는 JS로 보내는 합성 click 이벤트만으로는 안 열리고 실제 포인터
    이벤트가 와야 반응하기 때문이다. 다른 요소에 가려서(intercept) 실패하면
    그때만 JS 강제 클릭으로 폴백한다."""
    try:
        element.click()
    except Exception:
        drv.execute_script("arguments[0].click();", element)


def close_login_promo_popup(drv) -> None:
    """게스트 모드에서 뜨는 '로그인하여 Google 지도를 최대한 활용하세요' 홍보 팝업을 닫는다.
    로그인 없이도 리뷰 조회에는 지장 없지만, 팝업이 떠있으면 뒤쪽 버튼 클릭이 막힌다."""
    try:
        close_button = WebDriverWait(drv, 3).until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(., "닫기")]'))
        )
        drv.execute_script("arguments[0].click();", close_button)
        print("✅ 로그인 홍보 팝업 닫기")
    except Exception:
        pass


# 정렬 버튼에 aria-label="정렬"이 없는 경우가 있어("정렬" 글자는 버튼 안
# <span> 텍스트로만 들어있음), aria-label 기준과 텍스트 기준을 순서대로 시도한다.
SORT_BUTTON_XPATHS = [
    '//button[contains(@aria-label, "정렬")]',
    '//button[.//span[contains(text(), "정렬")]]',
    '//button[contains(., "정렬")]',
]


def find_sort_button(drv):
    for xpath in SORT_BUTTON_XPATHS:
        try:
            return WebDriverWait(drv, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        except Exception:
            continue
    raise TimeoutError("정렬 버튼을 찾지 못함 (시도한 선택자 전부 실패)")


# "최신순" 메뉴 항목도 role이 예상과 다를 수 있으니 여러 선택자를 순서대로 시도한다.
RECENT_SORT_OPTION_XPATHS = [
    '//div[@role="menuitemradio"][contains(., "최신순")]',
    '//*[@role="menuitemradio"][contains(., "최신순")]',
    '//*[@role="menuitem"][contains(., "최신순")]',
    '//*[@role="option"][contains(., "최신순")]',
    '//*[contains(text(), "최신순")]',
]


def find_recent_sort_option(drv):
    for xpath in RECENT_SORT_OPTION_XPATHS:
        try:
            return WebDriverWait(drv, 3).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        except Exception:
            continue
    raise TimeoutError("최신순 옵션을 찾지 못함 (시도한 선택자 전부 실패)")


def select_recent_sort_via_keyboard(drv) -> None:
    """정렬 메뉴가 열려 있다고 가정하고 선택자 없이 키보드로 '최신순'을 고른다.
    메뉴 항목 순서는 보통 관련성순(기본 선택) -> 최신순 -> 높은 평점순 -> 낮은
    평점순이므로, 아래 방향키로 한 칸 이동한 뒤 Enter로 선택한다. DOM 구조가
    달라져도 동작하는 선택자 기반 방법의 폴백이다."""
    actions = ActionChains(drv)
    actions.send_keys(Keys.ARROW_DOWN).pause(0.4).send_keys(Keys.ENTER).perform()


def crawl_place(drv, wait: WebDriverWait, keyword: str, place_name: str, region: str, url: str):
    """장소 1곳을 크롤링해서 (장소정보 dict, 리뷰 dict 리스트)를 반환한다."""
    print(f"\n{'=' * 60}")
    print(f"[{keyword}] {place_name}\n{url}")
    print(f"{'=' * 60}")

    try:
        drv.get(url)
    except Exception as e:
        _reraise_if_session_dead(e)
        print(f"[⚠️] 페이지 로드 타임아웃/오류 (계속 진행): {e}")
    time.sleep(3)

    close_login_promo_popup(drv)

    try:
        name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))).text
    except Exception as e:
        _reraise_if_session_dead(e)
        name = place_name

    try:
        address = drv.find_element(By.CSS_SELECTOR, 'button[data-item-id="address"]').text
    except Exception:
        address = ""

    try:
        rating = drv.find_element(By.CSS_SELECTOR, "div.F7nice span:nth-child(1)").text
    except Exception:
        rating = ""

    review_button_clicked = False
    try:
        review_button = wait.until(
            EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "리뷰")]'))
        )
        robust_click(drv, review_button)
        review_button_clicked = True
        print("✅ 리뷰 버튼 클릭 성공")
    except Exception as e:
        _reraise_if_session_dead(e)
        print("[❌] 리뷰 버튼 클릭 실패:", e)

    time.sleep(3)

    # 리뷰 탭을 연 뒤에 로그인 홍보 팝업이 다시 뜨는 경우가 있어, 정렬 버튼을
    # 누르기 전에 한 번 더 닫는다(열려있으면 뒤쪽 정렬 메뉴 자체가 안 열림).
    close_login_promo_popup(drv)

    reviews_data: list[dict] = []
    if review_button_clicked:
        try:
            sort_button = find_sort_button(drv)
            robust_click(drv, sort_button)
            time.sleep(1)
            try:
                drv.save_screenshot(os.path.join(SCRIPT_DIR, "sort_debug.png"))
            except Exception:
                pass
            try:
                recent_option = find_recent_sort_option(drv)
                robust_click(drv, recent_option)
                print("✅ 정렬: 최신순으로 변경 성공 (선택자)")
            except Exception as e:
                _reraise_if_session_dead(e)
                print("[⚠️] 선택자로 '최신순' 못 찾음, 키보드 방식으로 재시도:", e)
                select_recent_sort_via_keyboard(drv)
                print("✅ 정렬: 최신순으로 변경 시도 (키보드)")
            time.sleep(2)
        except Exception as e:
            _reraise_if_session_dead(e)
            print("[⚠️] 정렬(최신순) 변경 실패, 기본 정렬로 진행:", e)
            print(f"    (sort_debug.png에 정렬 버튼 클릭 직후 화면이 저장됐습니다: {os.path.join(SCRIPT_DIR, 'sort_debug.png')})")

        try:
            review_container = drv.find_element(By.CSS_SELECTOR, "div.m6QErb.DxyBCb.kA9KIf.dS8AEf")

            prev_count = len(review_container.find_elements(By.XPATH, ".//div/div/div[4]"))
            print(f"[📜] 초기 리뷰 개수: {prev_count}")
            no_change_count = 0
            for i in range(20):
                if prev_count >= TARGET_REVIEWS:
                    break
                drv.execute_script(
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
                        "키워드": keyword,
                        "장소명": name,
                        "지역": region,
                        "URL": url,
                        "ID": i + 1,
                        "별점": review_rating,
                        "기간": review_date,
                        "리뷰": review_text,
                    })

            print(f"[✅] 본문/별점/날짜 추출 완료: {len(reviews_data)}건")
        except Exception as e:
            _reraise_if_session_dead(e)
            print("[❌] 리뷰 컨테이너/추출 실패:", e)

    place_row = {
        "키워드": keyword,
        "지역": region,
        "장소명": name,
        "주소": address,
        "별점": rating,
        "URL": url,
        "리뷰개수": len(reviews_data),
    }
    return place_row, reviews_data


def main():
    if not os.path.exists(INPUT_CSV):
        print(f"[❌] {INPUT_CSV} 없음")
        print("     1_collect_urls.py 를 먼저 실행하세요.")
        return

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", keep_default_na=False)

    # 먼저 SKIP_FIRST_N으로 원본 순서 기준 앞부분을 자르고, 그다음 URL 없는
    # 행을 걸러낸다. 순서를 바꾸면 앞쪽에 섞여있는 빈 URL 행 때문에
    # SKIP_FIRST_N이 어긋난다.
    if SKIP_FIRST_N:
        print(f"[ℹ️] 앞의 {SKIP_FIRST_N}개는 건너뜁니다: {df['장소명'].head(SKIP_FIRST_N).tolist()}")
        df = df.iloc[SKIP_FIRST_N:].reset_index(drop=True)

    has_url = df["URL"].str.strip().str.startswith("http")
    no_url_count = (~has_url).sum()
    if no_url_count:
        print(f"[ℹ️] URL이 없는(\"없음\" 등) {no_url_count}곳은 건너뜁니다: "
              f"{df.loc[~has_url, '장소명'].tolist()}")
        df = df[has_url].reset_index(drop=True)

    checkpoint_df = load_checkpoint()
    done_urls = set(checkpoint_df["URL"]) if not checkpoint_df.empty else set()
    remaining = df[~df["URL"].isin(done_urls)]

    print(f"[📋] 전체 {len(df)}곳 중 처리 완료 {df['URL'].isin(done_urls).sum()}곳, 남은 {len(remaining)}곳")
    print(f"[수집 기간] {START_DATE} ~ {END_DATE} (리뷰 작성일 기준, 상대 날짜를 오늘 기준으로 근사 변환)\n")

    drv = build_driver()
    wait = WebDriverWait(drv, 15)

    if not USE_GUEST_MODE:
        try:
            drv.get("https://www.google.com/maps")
        except Exception as e:
            print(f"[⚠️] 초기 페이지 로드 실패 (계속 진행): {e}")

        print("\n[⏸️] 브라우저가 열렸습니다. 로그인/본인확인(인증코드 등)이 필요하면 지금 처리해주세요.")
        input("    다 되셨으면 Enter를 눌러 크롤링을 시작합니다... ")

    all_place_rows = []

    for _, row in remaining.iterrows():
        keyword = row.get("키워드", row.get("장소명", ""))
        place_name = row["장소명"]
        region = row.get("지역", "경기도")
        url = row["URL"]

        try:
            place_row, reviews = crawl_place(drv, wait, keyword, place_name, region, url)
        except WebDriverException as e:
            print(f"[⚠️] 드라이버 오류(브라우저 크래시 의심), 재시작 후 다음 장소로: {e}")
            try:
                drv.quit()
            except Exception:
                pass
            drv = build_driver()
            wait = WebDriverWait(drv, 15)
            continue
        except Exception as e:
            print(f"[❌] {place_name} 처리 중 알 수 없는 오류: {e}")
            continue

        all_place_rows.append(place_row)
        append_checkpoint(reviews)

    try:
        drv.quit()
    except Exception:
        pass

    # 최종 xlsx는 체크포인트(이번 실행 + 이전 실행 누적) 전체로 만든다.
    final_reviews_df = load_checkpoint()

    if not final_reviews_df.empty:
        reference_now = datetime.now()
        estimated = final_reviews_df["기간"].apply(lambda t: parse_relative_date_kr(t, reference_now))
        final_reviews_df = final_reviews_df.copy()
        final_reviews_df["추정날짜"] = estimated.apply(lambda d: d.strftime("%Y-%m-%d") if pd.notna(d) else "")
        in_range = final_reviews_df["추정날짜"].between(START_DATE, END_DATE)
        no_date = final_reviews_df["추정날짜"] == ""
        filtered_reviews_df = final_reviews_df[in_range | no_date]
    else:
        filtered_reviews_df = final_reviews_df

    with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl") as writer:
        pd.DataFrame(all_place_rows, columns=PLACE_COLUMNS).to_excel(writer, sheet_name="장소정보", index=False)
        filtered_reviews_df.to_excel(writer, sheet_name="리뷰", index=False)

    print(f"\n[💾] {OUTPUT_XLSX} 저장 완료")
    print(f"[📊] 이번 실행 장소: {len(all_place_rows)}곳")
    print(f"[📊] 체크포인트 누적 리뷰: {len(final_reviews_df)}건 -> 기간({START_DATE}~{END_DATE}) 필터링 후: {len(filtered_reviews_df)}건")
    print(f"[ℹ️] 필터링 전 전체 리뷰 원본은 {CHECKPOINT_CSV} 에 그대로 남아있습니다.")


if __name__ == "__main__":
    main()
