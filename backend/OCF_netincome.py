import requests
import json
import pandas as pd
from pathlib import Path


# 你的 FMP API 連結（記得把 API key 填上）
url1 = "https://financialmodelingprep.com/stable/cash-flow-statement?symbol=HIMS&period=annual&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
url2 = "https://financialmodelingprep.com/stable/income-statement?symbol=HIMS&period=annual&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response1 = requests.get(url1)
response2 = requests.get(url2)

data1 = response1.json()
data2 = response2.json()


# 將 API JSON 轉成 DataFrame
df1 = pd.DataFrame(data1)
df2 = pd.DataFrame(data2)

# 移除缺值列
df1 = df1.dropna(subset=["operatingCashFlow"])
df2 = df2.dropna(subset=["netIncome"])

# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "ocf_netincome": float(ocf/nt)
    }
    for d, ocf, nt in zip(df1["date"], df1["operatingCashFlow"], df2["netIncome"])
]

# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_ocf_netincome.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")
