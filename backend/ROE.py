import requests
import json
import pandas as pd
from pathlib import Path


#ROE
url = "https://financialmodelingprep.com/stable/key-metrics?symbol=HIMS&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
#ROE TTM
url2 = "https://financialmodelingprep.com/stable/key-metrics-ttm?symbol=HIMS&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)
response2 = requests.get(url2)


data = response.json()
data2 = response2.json()

# 將 API JSON 轉成 DataFrame
ROE = pd.DataFrame(data)

ROE_ttm = data2[0]["returnOnEquityTTM"]

# 移除缺值列
ROE = ROE.dropna(subset=["returnOnEquity"])


# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "returnOnEquity": float(ROE)
    }
    for d, ROE in zip(ROE["date"], ROE["returnOnEquity"])
]

#將TTM加入
if ROE_ttm is not None:
    records.append({
        "date": "TTM",
        "returnOnEquity": round(float(ROE_ttm), 2)
    })
# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_ROE.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")