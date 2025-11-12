import requests
import json
import pandas as pd
from pathlib import Path


#本益比
url = "https://financialmodelingprep.com/stable/ratios?symbol=HIMS&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
#本益比TTM
url2 = "https://financialmodelingprep.com/stable/ratios-ttm?symbol=HIMS&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)
response2 = requests.get(url2)


data = response.json()
data2 = response2.json()

# 將 API JSON 轉成 DataFrame
PE = pd.DataFrame(data)

pe_ttm = data2[0]["priceToEarningsRatioTTM"]

# 移除缺值列
PE = PE.dropna(subset=["priceToEarningsRatio"])


# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "priceToEarningsRatio": float(PE)
    }
    for d, PE in zip(PE["date"], PE["priceToEarningsRatio"])
]

#將TTM加入
if pe_ttm is not None:
    records.append({
        "date": "TTM",
        "priceToEarningsRatio": round(float(pe_ttm), 2)
    })
# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_PE.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")