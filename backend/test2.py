import requests
import json

# 你的 FMP API 連結（記得把 API key 填上）
url = "https://financialmodelingprep.com/stable/income-statement?symbol=HIMS&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)

print("status code:", response.status_code)  # 看有沒有 200
data = response.json()

# 用比較好看的方式印出來
print(json.dumps(data, indent=2, ensure_ascii=False))
