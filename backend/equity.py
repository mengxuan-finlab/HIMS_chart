import requests
import json
import pandas as pd
from pathlib import Path


# 你的 FMP API 連結（記得把 API key 填上）
url = "https://financialmodelingprep.com/stable/balance-sheet-statement?symbol=HIMS&period=quarter&apikey=PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
# 發出 GET 請求
response = requests.get(url)


data = response.json()


# 將 API JSON 轉成 DataFrame
df = pd.DataFrame(data)

# 移除缺值列
df = df.dropna(subset=["totalEquity"])

# 轉成 JSON-friendly 結構
records = [
    {
        "date": str(d),
        "totalEquity": float(RV),
        "totalEquity_million": float(RV) / 1_000_000  # 轉成百萬美元
    }
    for d, RV in zip(df["date"], df["totalEquity"],)
]

# 寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_totalEquity.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"✅ 已輸出 {len(records)} 筆資料到 {out_path}")