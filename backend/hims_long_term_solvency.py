import yfinance as yf
import pandas as pd 
import json
from pathlib import Path
from math import isnan


Ticker = "HIMS"
ticker = yf.Ticker(Ticker)

q_fin = ticker.quarterly_balancesheet
q_fin2 = ticker.quarterly_cashflow

operating_cash_flow = q_fin2.loc["Operating Cash Flow"]
long_term_debt = q_fin.loc["Long Term Debt And Capital Lease Obligation"]

long_term_solvency = (long_term_debt/operating_cash_flow).round(2)


data = []
for date, ocf, lts in zip(operating_cash_flow.index, operating_cash_flow.values, long_term_solvency.values):
    if isnan(ocf):  # math.isnan() 檢查 gm 是否是 NaN
        continue  # 避免沒有資料的季

    quarter_label = f"{date.year}Q{((date.month - 1)//3) + 1}"  #自動生成季度標籤

    data.append({
        "date": date.strftime("%Y-%m-%d"),     # 2025-06-30
        "long_term_solvency":float(lts)
    })

# 5. 由舊到新排序（可選）
data = list(reversed(data))

# 6. 存成 JSON 檔
with open("hims_long_term_solvency.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("done: hims_long_term_solvency.json")