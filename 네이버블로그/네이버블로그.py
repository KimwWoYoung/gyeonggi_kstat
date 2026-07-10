import requests
import csv

headers = {
    "X-Naver-Client-Id": "***REMOVED***",
    "X-Naver-Client-Secret": "***REMOVED***"
}

params = {
    "query": "북한산국립공원",
    "display": 100,
    "start": 1,
    "sort": "date"
}

res = requests.get(
    "https://openapi.naver.com/v1/search/blog.json",
    headers=headers, params=params
)

data = res.json()
items = data['items']

# CSV 저장
with open("블로그_북한산국립공원.csv", "w", newline="", encoding="utf-8-sig") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "link", "description", "bloggername", "bloggerlink", "postdate"])
    writer.writeheader()
    writer.writerows(items)

print(f"저장 완료: {len(items)}건")