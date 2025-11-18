import requests
import json
import pandas as pd
from pathlib import Path


# 你的 FMP API 連結（記得把 API key 填上）
url = "https://financialmodelingprep.com/stable/cash-flow-statement?symbol=HIMS&period=quarter&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
url2 = "https://financialmodelingprep.com/stable/balance-sheet-statement?symbol=HIMS&period=quarter&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)
response2 = requests.get(url2)


data = response.json()
data2 = response2.json()


# 將 API JSON 轉成 DataFrame
df = pd.DataFrame(data)
df2 = pd.DataFrame(data2)

# 移除缺值列
df = df.dropna(subset=["operatingCashFlow"])
df2 = df2.dropna(subset=["totalDebt"])

df_merged = pd.merge(df, df2, on="date", how="inner")

df_merged["ratio"] = df_merged["totalDebt"] / df_merged["operatingCashFlow"]

# 轉成 JSON-friendly 結構
records = [
    {
        "date": row["date"],
        "ratio": float(row["ratio"])
    }
    for _, row in df_merged.iterrows()
]

# 寫出 JSON
out_path = Path(__file__).parent / "hims_long_term_solvency.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")