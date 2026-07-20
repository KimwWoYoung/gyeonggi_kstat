"""
test_batch_urls.py
test_single_url.py에서 검증된 방식(로그인 자동 차단 옵션 + GPU 크래시
방지 + 리뷰 최신순 정렬)을 여러 장소에 대해 순회 실행한다.
2_crawl_reviews.py는 건드리지 않는다.

입력:
    google_maps_urls_gyeonggi.csv (장소명/지역/URL/키워드)
    맨 첫 번째 행(구름산산림욕장)은 test_single_url.py로 이미 확인했으므로
    기본적으로 건너뛴다 (SKIP_FIRST_N 으로 조절 가능).
    URL이 비어있는 행(구글지도에서 장소를 찾지 못한 경우)은 자동으로 건너뛴다.

중간저장 / 이어하기:
    장소 1곳을 다 처리할 때마다 리뷰 결과를 CHECKPOINT_CSV에 즉시
    append한다. 재실행하면 이미 CHECKPOINT_CSV에 있는 장소(URL 기준)는
    건너뛰고 남은 곳부터 이어서 처리한다. 크롬이 크래시로 죽으면
    드라이버를 자동으로 새로 띄우고 계속 진행한다.

사용법:
    python test_batch_urls.py
"""

import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "google_maps_urls_gyeonggi.csv")
CHECKPOINT_CSV = os.path.join(SCRIPT_DIR, "batch_test_reviews_checkpoint.csv")
OUTPUT_XLSX = os.path.join(SCRIPT_DIR, "gyeonggi_reviews_batch_test_202604_202606.xlsx")

# 구름산산림욕장은 test_single_url.py로 이미 확인해서 기본적으로 건너뜀.
SKIP_FIRST_N = 1

TARGET_REVIEWS = 200
START_DATE = "2026-04-01"
END_DATE = "2026-06-30"

RESULT_COLUMNS = ["키워드", "장소명", "지역", "URL", "ID", "별점", "기간", "리뷰"]
PLACE_COLUMNS = ["키워드", "지역", "장소명", "주소", "별점", "URL", "리뷰개수"]

# prefs로 로그인 차단해도 계속 2단계 인증이 뜨면(조직 정책이 강제 로그인일 경우)
# True로 바꿔서 --guest 모드로 시도해보세요.
USE_GUEST_MODE = False
CHROME_USER_DATA_DIR = os.path.expanduser(os.path.join("~", "selenium_profile_test_single"))


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
        options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
        options.add_argument("--profile-directory=Default")
        # 이 프로필이 조직 계정 등으로 자동 로그인/동기화되는 것을 최대한 막는다.
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


def crawl_place(drv, wait: WebDriverWait, keyword: str, place_name: str, region: str, url: str):
    """장소 1곳을 크롤링해서 (장소정보 dict, 리뷰 dict 리스트)를 반환한다."""
    print(f"\n{'=' * 60}")
    print(f"[{keyword}] {place_name}\n{url}")
    print(f"{'=' * 60}")

    try:
        drv.get(url)
    except Exception as e:
        print(f"[⚠️] 페이지 로드 타임아웃/오류 (계속 진행): {e}")
    time.sleep(3)

    try:
        name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "h1.DUwDvf"))).text
    except Exception:
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
        drv.execute_script("arguments[0].click();", review_button)
        review_button_clicked = True
        print("✅ 리뷰 버튼 클릭 성공")
    except Exception as e:
        print("[❌] 리뷰 버튼 클릭 실패:", e)

    time.sleep(3)

    reviews_data: list[dict] = []
    if review_button_clicked:
        try:
            sort_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "정렬")]'))
            )
            drv.execute_script("arguments[0].click();", sort_button)
            time.sleep(1)
            recent_option = WebDriverWait(drv, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//div[@role="menuitemradio"][contains(., "최신순")]'))
            )
            drv.execute_script("arguments[0].click();", recent_option)
            time.sleep(2)
            print("✅ 정렬: 최신순으로 변경 성공")
        except Exception as e:
            print("[⚠️] 정렬(최신순) 변경 실패, 기본 정렬로 진행:", e)

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
        return

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig", keep_default_na=False)

    no_url_count = (df["URL"].str.strip() == "").sum()
    if no_url_count:
        print(f"[ℹ️] URL이 없는 {no_url_count}곳은 건너뜁니다: "
              f"{df.loc[df['URL'].str.strip() == '', '장소명'].tolist()}")
        df = df[df["URL"].str.strip() != ""].reset_index(drop=True)

    if SKIP_FIRST_N:
        print(f"[ℹ️] 앞의 {SKIP_FIRST_N}개는 건너뜁니다: {df['장소명'].head(SKIP_FIRST_N).tolist()}")
        df = df.iloc[SKIP_FIRST_N:].reset_index(drop=True)

    checkpoint_df = load_checkpoint()
    done_urls = set(checkpoint_df["URL"]) if not checkpoint_df.empty else set()
    remaining = df[~df["URL"].isin(done_urls)]

    print(f"[📋] 전체 {len(df)}곳 중 처리 완료 {df['URL'].isin(done_urls).sum()}곳, 남은 {len(remaining)}곳")

    drv = build_driver()
    wait = WebDriverWait(drv, 15)

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
        final_reviews_df["추정날짜"] = estimated.apply(lambda d: d.strftime("%Y-%m-%d") if d else "")
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
