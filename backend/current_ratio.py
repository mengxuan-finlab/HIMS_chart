import yfinance as yf
import pandas as pd 
import json
from pathlib import Path
from math import isnan


Ticker = "HIMS"
ticker = yf.Ticker(Ticker)

q_fin = ticker.quarterly_balancesheet

current_assets = q_fin.loc["Current Assets"]
current_liabilities = q_fin.loc["Current Liabilities"]

current_ratio = (current_assets/current_liabilities).round(2)


data = []
for date, ass, rat in zip(current_assets.index, current_assets.values, current_ratio.values):
    if isnan(ass):  # math.isnan() 檢查 gm 是否是 NaN
        continue  # 避免沒有資料的季

    quarter_label = f"{date.year}Q{((date.month - 1)//3) + 1}"  #自動生成季度標籤

    data.append({
        "date": date.strftime("%Y-%m-%d"),     # 2025-06-30
        "current_ratio":float(rat)
    })

# 5. 由舊到新排序（可選）
data = list(reversed(data))

# 6. 存成 JSON 檔
with open("hims_current_ratio.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("done: hims_current_ratio.json")