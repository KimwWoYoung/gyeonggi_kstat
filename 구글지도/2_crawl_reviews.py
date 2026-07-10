from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
import os

# 브라우저 설정
options = webdriver.ChromeOptions()
options.add_argument("--start-maximized")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
wait = WebDriverWait(driver, 15)

# CSV 파일 읽기
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(script_dir, 'Seoul_ThingsToDo.csv')

if not os.path.exists(csv_file):
    print(f"[❌] CSV 파일을 찾을 수 없습니다: {csv_file}")
    exit(1)

df = pd.read_csv(csv_file, encoding='utf-8-sig')

# 전체 URL 처리 (리밋 없음)
print(f"[📊] 총 {len(df)}개의 URL을 처리합니다.\n")

all_restaurant_data = []
all_reviews_data = []

for idx, row in df.iterrows():
    url = row['URL']
    place_name = row['장소명']
    region = row['지역']
    
    print(f"\n{'='*60}")
    print(f"[{idx+1}/{len(df)}] 처리 중: {place_name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        driver.get(url)
        time.sleep(5)
        
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf')))
            print("✅ 페이지 로드 완료")
        except:
            print("[⚠️] 페이지 로드 확인 실패, 계속 진행...")
            time.sleep(3)
        
        try:
            name = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'h1.DUwDvf'))).text
        except:
            name = place_name
        
        try:
            address = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'button[data-item-id="address"]'))).text
        except:
            address = ""
        
        try:
            rating = driver.find_element(By.CSS_SELECTOR, 'div.F7nice span:nth-child(1)').text
        except:
            rating = ""
        
        reviews_data = []
        review_button_clicked = False
        try:
            try:
                try:
                    review_button = wait.until(EC.element_to_be_clickable((By.XPATH, '//button[contains(@aria-label, "리뷰")]')))
                    driver.execute_script("arguments[0].click();", review_button)
                    print("✅ 리뷰 버튼 클릭 성공 (aria-label 방법)")
                    review_button_clicked = True
                except:
                    try:
                        button_container_xpath = '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[3]/div/div'
                        button_container = wait.until(EC.presence_of_element_located((By.XPATH, button_container_xpath)))
                        buttons = button_container.find_elements(By.XPATH, './button')
                        button_count = len(buttons)
                        print(f"[📝] 발견된 버튼 개수: {button_count}")
                        
                        for i, btn in enumerate(buttons, 1):
                            try:
                                aria_label = btn.get_attribute("aria-label")
                                print(f"  버튼 {i}: {aria_label}")
                            except:
                                print(f"  버튼 {i}: aria-label 없음")
                        
                        if button_count == 4:
                            review_button_index = 3
                        elif button_count == 3:
                            review_button_index = 2
                        else:
                            review_button_index = button_count - 1
                        
                        if review_button_index <= button_count:
                            review_button = buttons[review_button_index - 1]
                            driver.execute_script("arguments[0].click();", review_button)
                            print(f"✅ 리뷰 버튼 클릭 성공 (버튼 {review_button_index}/{button_count})")
                            review_button_clicked = True
                        else:
                            raise Exception("리뷰 버튼 인덱스가 버튼 개수를 초과함")
                    except Exception as e:
                        print(f"[⚠️] 동적 버튼 찾기 실패: {e}")
                        try:
                            review_button_xpath = '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[3]/div/div/button[2]'
                            review_button = wait.until(EC.element_to_be_clickable((By.XPATH, review_button_xpath)))
                            driver.execute_script("arguments[0].click();", review_button)
                            print("✅ 리뷰 버튼 클릭 성공 (고정 XPath 방법)")
                            review_button_clicked = True
                        except Exception as e2:
                            print(f"[⚠️] 리뷰 버튼 클릭 실패: {e2}")
                
                if review_button_clicked:
                    time.sleep(3)
                    try:
                        driver.execute_script("window.scrollBy(0, 500);")
                        time.sleep(1)
                    except:
                        pass
                else:
                    print("[⚠️] 리뷰 버튼 클릭 실패")
                    time.sleep(2)
            except Exception as e:
                print(f"[⚠️] 리뷰 버튼 클릭 전체 실패: {e}")
            
            try:
                review_container = None
                try:
                    review_container_xpath = '//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[9]'
                    wait_time = WebDriverWait(driver, 10 if review_button_clicked else 5)
                    review_container = wait_time.until(EC.presence_of_element_located((By.XPATH, review_container_xpath)))
                    print("✅ 리뷰 컨테이너 찾기 성공 (방법1)")
                except Exception as e1:
                    print(f"[⚠️] 방법1 실패: {e1}")
                    try:
                        for div_index in [8, 9, 10, 11]:
                            try:
                                alt_xpath = f'//*[@id="QA0Szd"]/div/div/div[1]/div[2]/div/div[1]/div/div/div[2]/div[{div_index}]'
                                review_container = driver.find_element(By.XPATH, alt_xpath)
                                test_items = review_container.find_elements(By.XPATH, './/div/div/div[4]')
                                if len(test_items) > 0:
                                    print(f"✅ 리뷰 컨테이너 찾기 성공 (방법2 - div[{div_index}])")
                                    break
                            except:
                                continue
                    except Exception as e2:
                        print(f"[⚠️] 방법2 실패: {e2}")
                        try:
                            review_container = driver.find_element(By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf')
                            test_items = review_container.find_elements(By.XPATH, './/div/div/div[4]')
                            if len(test_items) > 0:
                                print("✅ 리뷰 컨테이너 찾기 성공 (방법3 - CSS 선택자)")
                            else:
                                raise Exception("리뷰 항목이 없음")
                        except Exception as e3:
                            print(f"[⚠️] 방법3 실패: {e3}")
                            review_container = None
                
                if review_container is None:
                    print("[⚠️] 리뷰 컨테이너를 찾지 못해 리뷰 추출을 건너뜁니다.")
                    reviews_data = []
                else:
                    try:
                        time.sleep(2)
                        target_reviews = 200
                        print(f"[📜] 리뷰 로드 중... (최대 {target_reviews}개)")
                        
                        try:
                            scrollable_div = driver.find_element(By.CSS_SELECTOR, 'div.m6QErb.DxyBCb.kA9KIf.dS8AEf')
                            print("✅ 스크롤 가능한 div 찾기 성공")
                        except Exception as e:
                            print(f"[⚠️] 스크롤 가능한 div 찾기 실패: {e}")
                            scrollable_div = review_container
                        
                        max_scrolls = 20
                        no_change_count = 0
                        max_no_change = 3
                        previous_review_count = len(review_container.find_elements(By.XPATH, './/div/div/div[4]'))
                        print(f"[📝] 초기 리뷰 개수: {previous_review_count}")
                        
                        if previous_review_count >= target_reviews:
                            print(f"[📜] 이미 목표 리뷰 개수({target_reviews}개) 이상입니다.")
                        else:
                            for i in range(max_scrolls):
                                if previous_review_count >= target_reviews:
                                    break
                                driver.execute_script('arguments[0].scrollTop = arguments[0].scrollHeight', scrollable_div)
                                time.sleep(2)
                                current_review_count = len(review_container.find_elements(By.XPATH, './/div/div/div[4]'))
                                if current_review_count > previous_review_count:
                                    print(f"[📜] 스크롤 {i+1}회 - 리뷰: {previous_review_count} → {current_review_count}")
                                    previous_review_count = current_review_count
                                    no_change_count = 0
                                else:
                                    no_change_count += 1
                                    if no_change_count >= max_no_change:
                                        print(f"[📜] 연속 {max_no_change}회 변화 없음. 스크롤 중단.")
                                        break
                        
                        time.sleep(2)
                        final_review_count = len(review_container.find_elements(By.XPATH, './/div/div/div[4]'))
                        print(f"[📜] 최종 리뷰 개수: {final_review_count}")
                        
                        review_items = review_container.find_elements(By.XPATH, './/div/div/div[4]')
                        print(f"[📝] 방법1 - {len(review_items)}개")
                        
                        if len(review_items) == 0:
                            review_items_with_id = review_container.find_elements(By.XPATH, './/div[@data-review-id]')
                            for item_with_id in review_items_with_id:
                                try:
                                    parent = item_with_id.find_element(By.XPATH, './ancestor::div[1]')
                                    div4 = parent.find_element(By.XPATH, './/div/div/div[4]')
                                    if div4 not in review_items:
                                        review_items.append(div4)
                                except:
                                    pass
                        
                        if len(review_items) == 0:
                            review_items_css = review_container.find_elements(By.CSS_SELECTOR, 'div.jftiEf')
                            for item_css in review_items_css:
                                try:
                                    div4 = item_css.find_element(By.XPATH, './/div/div/div[4]')
                                    if div4 not in review_items:
                                        review_items.append(div4)
                                except:
                                    pass
                        
                        review_items = list(dict.fromkeys(review_items))
                        print(f"[📝] 최종 리뷰 개수 (중복 제거 후): {len(review_items)}")
                        
                        review_text_elements = driver.find_elements(By.CSS_SELECTOR, 'div.MyEned span.wi17pd')
                        
                        if len(review_items) > 0:
                            for i in range(len(review_items)):
                                try:
                                    review_item = review_items[i]
                                    
                                    review_rating = ""
                                    try:
                                        try:
                                            rating_elem = review_item.find_element(By.CSS_SELECTOR, 'span.kvMYJc')
                                            review_rating = rating_elem.get_attribute("aria-label") or rating_elem.text.strip()
                                        except:
                                            try:
                                                du9pgb = review_item.find_element(By.CSS_SELECTOR, 'div.DU9Pgb')
                                                rating_elem = du9pgb.find_element(By.CSS_SELECTOR, 'span.kvMYJc')
                                                review_rating = rating_elem.get_attribute("aria-label") or rating_elem.text.strip()
                                            except:
                                                try:
                                                    rating_elem = review_item.find_element(By.XPATH, './div[1]/span[1]')
                                                    review_rating = rating_elem.get_attribute("aria-label") or rating_elem.text.strip()
                                                except:
                                                    pass
                                        
                                        if review_rating:
                                            if "별표" in review_rating and "개" in review_rating:
                                                numbers = re.findall(r'\d+', review_rating)
                                                if numbers:
                                                    review_rating = numbers[0]
                                            elif "점" in review_rating:
                                                review_rating = review_rating.split("점")[0].strip()
                                            elif "out of" in review_rating:
                                                review_rating = review_rating.split("out of")[0].strip()
                                            else:
                                                numbers = re.findall(r'\d+', review_rating)
                                                if numbers:
                                                    review_rating = numbers[0]
                                    except Exception as e:
                                        print(f"[⚠️] 리뷰 {i+1} 별점 추출 실패: {e}")
                                    
                                    review_date = ""
                                    try:
                                        date_elem = review_item.find_element(By.XPATH, './div[1]/span[2]')
                                        review_date = date_elem.text.strip()
                                    except:
                                        pass
                                    
                                    review_text = ""
                                    try:
                                        try:
                                            review_text_elem = review_item.find_element(By.XPATH, './div[2]/div/span[1]')
                                            review_text = review_text_elem.text.strip()
                                        except:
                                            try:
                                                div2 = review_item.find_element(By.XPATH, './div[2]')
                                                review_text_elem = div2.find_element(By.CSS_SELECTOR, 'span.wi17pd')
                                                review_text = review_text_elem.text.strip()
                                            except:
                                                try:
                                                    div2 = review_item.find_element(By.XPATH, './div[2]')
                                                    review_text = div2.find_element(By.CSS_SELECTOR, 'span').text.strip()
                                                except:
                                                    pass
                                        
                                        if not review_text:
                                            review_id = None
                                            try:
                                                parent_with_id = review_item.find_element(By.XPATH, './ancestor::div[@data-review-id][1]')
                                                review_id = parent_with_id.get_attribute("data-review-id")
                                            except:
                                                pass
                                            
                                            if review_id:
                                                try:
                                                    review_text_elem = driver.find_element(By.XPATH, f'//div[@data-review-id="{review_id}"]//div[@class="MyEned"]//span[@class="wi17pd"]')
                                                    review_text = review_text_elem.text.strip()
                                                except:
                                                    pass
                                        
                                        if not review_text and i < len(review_text_elements):
                                            try:
                                                review_text = review_text_elements[i].text.strip()
                                            except:
                                                pass
                                        
                                        if not review_text:
                                            try:
                                                myened = review_item.find_element(By.CSS_SELECTOR, 'div.MyEned')
                                                review_text = myened.find_element(By.CSS_SELECTOR, 'span.wi17pd').text.strip()
                                            except:
                                                try:
                                                    parent = review_item.find_element(By.XPATH, './ancestor::div[@data-review-id][1]')
                                                    myened = parent.find_element(By.CSS_SELECTOR, 'div.MyEned')
                                                    review_text = myened.find_element(By.CSS_SELECTOR, 'span.wi17pd').text.strip()
                                                except:
                                                    pass
                                    except Exception as e:
                                        print(f"[⚠️] 리뷰 {i+1} 텍스트 추출 오류: {e}")
                                    
                                    if review_rating or review_text:
                                        reviews_data.append({
                                            "장소명": name,
                                            "URL": url,
                                            "ID": i+1,
                                            "별점": review_rating,
                                            "기간": review_date,
                                            "리뷰": review_text
                                        })
                                except Exception as e:
                                    print(f"[⚠️] 리뷰 {i+1} 추출 오류: {e}")
                                    continue
                        else:
                            print("[❌] 리뷰 항목을 찾지 못했습니다.")
                        
                        print(f"[✅] {len(reviews_data)}개의 리뷰 추출 완료")
                    except Exception as e:
                        print(f"[❌] 리뷰 컨테이너 처리 오류: {e}")
                        reviews_data = []
            
            except Exception as e:
                print(f"[❌] 리뷰 추출 실패: {e}")
                reviews_data = []
        
        except Exception as e:
            print(f"[❌] 리뷰 크롤링 전체 실패: {e}")
            reviews_data = []
        
        restaurant_data = {
            "지역": region,
            "장소명": name,
            "주소": address,
            "별점": rating,
            "URL": url,
            "리뷰개수": len(reviews_data)
        }
        all_restaurant_data.append(restaurant_data)
        all_reviews_data.extend(reviews_data)
        
        print(f"[✅] {place_name} 처리 완료 - 리뷰 {len(reviews_data)}개 추출")
        
    except Exception as e:
        print(f"[❌] {place_name} 처리 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        continue

# Excel 저장
print(f"\n{'='*60}")
print("[💾] 데이터 저장 중...")

output_file = os.path.join(script_dir, 'Seoul_Reviews.xlsx')

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    pd.DataFrame(all_restaurant_data).to_excel(writer, sheet_name='장소정보', index=False)
    pd.DataFrame(all_reviews_data).to_excel(writer, sheet_name='리뷰', index=False)

print(f"[💾] {output_file} 저장 완료")
print(f"[📊] 장소정보: {len(all_restaurant_data)}개")
print(f"[📊] 리뷰: {len(all_reviews_data)}개")

driver.quit()
print("\n[✅] 크롤링 완료!")