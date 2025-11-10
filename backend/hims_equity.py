import yfinance as yf
import pandas as pd 
import json
from pathlib import Path

#股票代號
TICKER = "HIMS"

ticker=yf.Ticker(TICKER)
q_fin = ticker.quarterly_balancesheet
  
equity = q_fin.loc["Total Equity Gross Minority Interest"]

#轉成 DataFrame 並整理日期格式
df = equity.to_frame(name="equity") #把 Series 轉成 DataFrame（欄名叫 revenue）
df.index = pd.to_datetime(df.index) #把索引轉成日期型態（方便之後畫圖或排序）
df = df.sort_index()  #按時間順序排列（早到晚）

# 移除 equity 欄位為 NaN 的列
df = df.dropna(subset=["equity"])
#轉成 JSON 格式方便輸出
records = []
for idx, row in df.iterrows():  #df.iterrows()是 pandas 的方法，會一筆一筆讀取 DataFrame 的資料
    records.append({
        "date": idx.strftime("%Y-%m-%d"),
        "equity":float(row["equity"])
        
    })

#寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_equity.json" 
#Path(__file__).parent	取得「這支程式所在的資料夾」
#/ "hims_equity.json"	在該資料夾下建立一個名叫 hims_revenue.json 的檔案路徑。
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"已輸出 {len(records)} 筆資料到 {out_path}")
