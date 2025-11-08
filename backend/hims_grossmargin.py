import yfinance as yf
import pandas as pd 
import json
from pathlib import Path
from math import isnan


Ticker = "HIMS"
ticker = yf.Ticker(Ticker)

q_fin = ticker.quarterly_financials

revenue = q_fin.loc["Total Revenue"]
gross_profit = q_fin.loc["Gross Profit"]

gross_margin = (gross_profit/revenue*100).round(2)


data = []
for date, rev, gm in zip(revenue.index, revenue.values, gross_margin.values):
    if isnan(gm):  # math.isnan() 檢查 gm 是否是 NaN
        continue  # 避免沒有資料的季

    quarter_label = f"{date.year}Q{((date.month - 1)//3) + 1}"  #自動生成季度標籤

    data.append({
        "date": date.strftime("%Y-%m-%d"),     # 2025-06-30
        "label": quarter_label,                # 2025Q2
        "revenue_million": round(rev / 1e6, 2),
        "gross_margin": float(gm)              # %
    })

# 5. 由舊到新排序（可選）
data = list(reversed(data))

# 6. 存成 JSON 檔
with open("hims_grossmargin.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("done: hims_grossmargin.json")