import requests
import json
import pandas as pd
from pathlib import Path


# 你的 FMP API 連結（記得把 API key 填上）
url = "https://financialmodelingprep.com/stable/cash-flow-statement?symbol=HIMS&period=annual&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)


data = response.json()


# 將 API JSON 轉成 DataFrame
df = pd.DataFrame(data)

# 移除缺值列
df = df.dropna(subset=["freeCashFlow"])


# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "free_cash_flow": float(ocf)
    }
    for d, ocf in zip(df["date"], df["freeCashFlow"])
]

# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_free_cashflow.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")
