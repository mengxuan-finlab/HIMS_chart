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

print(data)
print(data2)

# 將 API JSON 轉成 DataFrame
PEG = pd.DataFrame(data)

peg_ttm = data2[0]["priceToEarningsGrowthRatioTTM"]

# 移除缺值列
PEG = PEG.dropna(subset=["priceToEarningsGrowthRatio"])


# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "priceToEarningsGrowthRatio": float(PEG)
    }
    for d, PEG in zip(PEG["date"], PEG["priceToEarningsGrowthRatio"])
]

#將TTM加入
if peg_ttm is not None:
    records.append({
        "date": "TTM",
        "priceToEarningsGrowthRatio": round(float(peg_ttm), 2)
    })
# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_PEG.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")