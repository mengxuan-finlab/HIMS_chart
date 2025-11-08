import yfinance as yf
import pandas as pd 
import json
from pathlib import Path

#股票代號
TICKER = "HIMS"

ticker=yf.Ticker(TICKER)
q_fin = ticker.quarterly_financials
  
print("Available rows:", q_fin.index.tolist())  #把損益表裡所有項目名稱，整理成一個 list，方便查看或篩選
# 抓取 "Total Revenue" 這一列作為營收
revenue_series = q_fin.loc["Total Revenue"] #抓取Total revenue 那行

#轉成 DataFrame 並整理日期格式
df = revenue_series.to_frame(name="revenue") #把 Series 轉成 DataFrame（欄名叫 revenue）
df.index = pd.to_datetime(df.index) #把索引轉成日期型態（方便之後畫圖或排序）
df = df.sort_index()  #按時間順序排列（早到晚）

#新增「季度標籤」與「單位轉換」欄
df["label"] = df.index.to_period("Q").astype(str)  #to_period("Q")：把日期轉成季度，例如 2024Q3，astype(str)：轉成文字方便顯示
df["revenue_million"] = (df["revenue"] / 1_000_000).round(2) #除以 1_000_000：把金額從「美元」變成「百萬美元」，比較好看，.round(2)：四捨五入到小數點兩位
   
#轉成 JSON 格式方便輸出
records = []
for idx, row in df.iterrows():  #df.iterrows()是 pandas 的方法，會一筆一筆讀取 DataFrame 的資料
    records.append({
        "date": idx.strftime("%Y-%m-%d"),
        "label": row["label"],
        "revenue": float(row["revenue"]),
        "revenue_million": float(row["revenue_million"])
    })

#寫出到 JSON 檔案
out_path = Path(__file__).parent / "hims_revenue.json" 
#Path(__file__).parent	取得「這支程式所在的資料夾」
#/ "hims_revenue.json"	在該資料夾下建立一個名叫 hims_revenue.json 的檔案路徑。
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print(f"已輸出 {len(records)} 筆資料到 {out_path}")
