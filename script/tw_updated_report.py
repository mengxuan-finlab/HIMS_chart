import json
import os
import time
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from google import genai
from supabase import create_client


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_MAIN") or os.getenv("GEMINI_API_KEY")
FINMIND_TOKEN = os.getenv("FINMIND_TOKEN")
REPORT_BASE_URL = os.getenv("TW_REPORT_BASE_URL", "https://hims-chart.vercel.app/tw_report.html")

client = genai.Client(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_tw_symbol(symbol):
    value = str(symbol or "").strip().upper()
    if value.endswith(".TW") or value.endswith(".TWO"):
        value = value.split(".")[0]
    return value


def is_tw_stock(symbol):
    value = normalize_tw_symbol(symbol)
    return value.isdigit() and len(value) == 4


def safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def finmind_fetch(dataset, stock_id, start_date):
    params = {
        "dataset": dataset,
        "data_id": stock_id,
        "start_date": start_date,
    }
    if FINMIND_TOKEN:
        params["token"] = FINMIND_TOKEN

    response = requests.get("https://api.finmindtrade.com/api/v4/data", params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()

    if payload.get("status") not in (200, "200"):
        raise RuntimeError(payload.get("msg") or f"{dataset} API 回傳異常")

    return payload.get("data") or []


def to_chart_rows(rows, date_key="date", value_key="value", limit=12):
    result = []
    for row in rows[-limit:]:
        value = safe_float(row.get(value_key))
        if value is None:
            continue
        result.append({
            "date": row.get(date_key),
            "value": value,
        })
    return result


def build_monthly_revenue(stock_id):
    start_date = (datetime.now() - timedelta(days=820)).strftime("%Y-%m-%d")
    rows = finmind_fetch("TaiwanStockMonthRevenue", stock_id, start_date)
    rows = [row for row in rows if str(row.get("stock_id")) == stock_id]
    rows.sort(key=lambda row: row.get("date", ""))
    rows = rows[-24:]

    enriched = []
    by_date = {row.get("date"): row for row in rows}
    for index, row in enumerate(rows):
        revenue = safe_float(row.get("revenue"))
        previous_revenue = safe_float(rows[index - 1].get("revenue")) if index > 0 else None

        try:
            current_date = datetime.strptime(row.get("date", ""), "%Y-%m-%d")
            last_year_date = current_date.replace(year=current_date.year - 1).strftime("%Y-%m-%d")
        except ValueError:
            last_year_date = ""

        last_year_revenue = safe_float(by_date.get(last_year_date, {}).get("revenue"))
        mom = ((revenue - previous_revenue) / previous_revenue * 100) if revenue and previous_revenue else None
        yoy = ((revenue - last_year_revenue) / last_year_revenue * 100) if revenue and last_year_revenue else None

        enriched.append({
            "date": row.get("date"),
            # FinMind 月營收 revenue 通常為仟元；換算成新台幣億元，方便閱讀。
            "value": round(revenue / 100000, 2) if revenue is not None else None,
            "yoy": round(yoy, 2) if yoy is not None else None,
            "mom": round(mom, 2) if mom is not None else None,
        })

    latest_12 = enriched[-12:]
    previous_12 = enriched[-24:-12]
    latest_12_sum = sum(row["value"] or 0 for row in latest_12)
    previous_12_sum = sum(row["value"] or 0 for row in previous_12)
    ttm_yoy = ((latest_12_sum - previous_12_sum) / previous_12_sum * 100) if previous_12_sum else None

    return {
        "monthly_revenue": [{"date": row["date"], "value": row["value"]} for row in enriched[-12:]],
        "monthly_revenue_yoy": [{"date": row["date"], "value": row["yoy"]} for row in enriched[-12:] if row["yoy"] is not None],
        "monthly_revenue_mom": [{"date": row["date"], "value": row["mom"]} for row in enriched[-12:] if row["mom"] is not None],
        "ttm_revenue_yoy": round(ttm_yoy, 2) if ttm_yoy is not None else None,
        "latest_month": enriched[-1] if enriched else None,
    }


FINANCIAL_ALIASES = {
    "revenue": ["Revenue", "營業收入", "營業收入合計"],
    "gross_profit": ["GrossProfit", "營業毛利", "營業毛利（毛損）"],
    "operating_income": ["OperatingIncome", "營業利益", "營業利益（損失）"],
    "net_income": ["NetIncome", "本期淨利", "本期淨利（淨損）", "本期稅後淨利"],
    "eps": ["EPS", "基本每股盈餘", "基本每股盈餘（元）"],
    "inventory": ["Inventories", "存貨"],
    "accounts_receivable": ["AccountsReceivable", "應收帳款", "應收款項"],
    "operating_cash_flow": ["CashFlowsFromOperatingActivities", "營業活動之淨現金流入（流出）"],
}


def build_financial_statement_data(stock_id):
    start_date = (datetime.now() - timedelta(days=1300)).strftime("%Y-%m-%d")
    rows = finmind_fetch("TaiwanStockFinancialStatements", stock_id, start_date)
    rows = [row for row in rows if str(row.get("stock_id")) == stock_id]
    rows.sort(key=lambda row: row.get("date", ""))

    by_metric = {}
    for metric_id, aliases in FINANCIAL_ALIASES.items():
        metric_rows = [
            {
                "date": row.get("date"),
                "type": row.get("type") or row.get("origin_name") or row.get("name"),
                "value": safe_float(row.get("value")),
            }
            for row in rows
            if (row.get("type") in aliases or row.get("origin_name") in aliases or row.get("name") in aliases)
        ]
        metric_rows = [row for row in metric_rows if row["date"] and row["value"] is not None]
        by_metric[metric_id] = to_chart_rows(metric_rows, limit=8)

    revenue_map = {row["date"]: row["value"] for row in by_metric["revenue"]}
    gross_profit_map = {row["date"]: row["value"] for row in by_metric["gross_profit"]}
    operating_income_map = {row["date"]: row["value"] for row in by_metric["operating_income"]}

    by_metric["gross_margin"] = [
        {"date": date, "value": round(gross_profit_map[date] / revenue * 100, 2)}
        for date, revenue in revenue_map.items()
        if revenue and date in gross_profit_map
    ][-8:]

    by_metric["operating_margin"] = [
        {"date": date, "value": round(operating_income_map[date] / revenue * 100, 2)}
        for date, revenue in revenue_map.items()
        if revenue and date in operating_income_map
    ][-8:]

    return by_metric


def get_tw_review_list():
    print("🔍 掃描台股 tw_review 任務...")
    try:
        response = supabase.table("tracked_stocks") \
            .select("symbol, user_id, summary") \
            .eq("status", "tw_review") \
            .execute()
        return [row for row in (response.data or []) if is_tw_stock(row.get("symbol"))]
    except Exception as error:
        print(f"❌ 抓取台股任務失敗: {error}")
        return []


def build_ai_analysis(symbol, data, summary):
    prompt = f"""
你是一位熟悉台股財報、月營收與產業循環的財務分析師。
請根據台股資料回傳純 JSON，不要使用 Markdown。

輸出格式：
{{
  "one_liner": "一句話總結目前台股財務觀察",
  "highlights": ["重點1", "重點2", "重點3"],
  "risks": ["風險1", "風險2", "風險3"],
  "by_metric": {{
    "monthly_revenue": {{"summary": "月營收趨勢解讀", "watch": "後續觀察重點"}},
    "monthly_revenue_yoy": {{"summary": "年增率解讀", "watch": "後續觀察重點"}},
    "gross_margin": {{"summary": "毛利率解讀", "watch": "後續觀察重點"}},
    "operating_margin": {{"summary": "營益率解讀", "watch": "後續觀察重點"}},
    "eps": {{"summary": "EPS 解讀", "watch": "後續觀察重點"}},
    "inventory": {{"summary": "存貨解讀", "watch": "後續觀察重點"}},
    "accounts_receivable": {{"summary": "應收帳款解讀", "watch": "後續觀察重點"}},
    "operating_cash_flow": {{"summary": "營業現金流解讀", "watch": "後續觀察重點"}}
  }}
}}

要求：
- 使用繁體中文
- 不提供買賣建議、目標價或投資評等
- 若某項資料不足，請在 summary 寫「目前資料不足以判斷」
- 請特別聚焦：月營收是否加速、毛利與營益率是否守住、存貨與應收帳款是否可能出現壓力

股票代號：{symbol}
先前月營收摘要：
{summary or "無"}

資料：
{json.dumps(data, ensure_ascii=False)}
"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)


def run_tw_update(task):
    raw_symbol = task["symbol"]
    symbol = normalize_tw_symbol(raw_symbol)
    user_id = task["user_id"]

    print(f"🚀 處理台股圖表資料：{raw_symbol}")

    try:
        monthly_data = build_monthly_revenue(symbol)
        financial_data = build_financial_statement_data(symbol)
        final_data = {**monthly_data, **financial_data}
        ai_analysis = build_ai_analysis(symbol, final_data, task.get("summary"))

        supabase.table("tracked_stocks").upsert({
            "user_id": user_id,
            "symbol": raw_symbol.upper(),
            "report_json": {
                "market": "TW",
                "symbol": symbol,
                "as_of": time.strftime("%Y-%m-%d"),
                "data": final_data,
                "ai": ai_analysis,
            },
            "status": "tw_ready",
            "report_url": f"{REPORT_BASE_URL}?symbol={raw_symbol.upper()}",
        }, on_conflict="user_id, symbol").execute()

        print(f"✅ 台股 {raw_symbol} 圖表資料更新成功。")

    except Exception as error:
        print(f"💥 處理台股 {raw_symbol} 時發生錯誤: {error}")


if __name__ == "__main__":
    task_list = get_tw_review_list()
    if not task_list:
        print("☕ 目前沒有待處理台股任務 (status='tw_review')。")
    else:
        for task in task_list:
            run_tw_update(task)
            time.sleep(1)
    print("✨ 台股圖表資料程序執行完畢。")
