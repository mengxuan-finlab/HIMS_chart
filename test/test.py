import requests
import json
import pandas as pd
from pathlib import Path
from google import genai

client = genai.Client(api_key="AIzaSyDbb3R97kBvW7ngntK5XmIWICxMW8f9qs4")

response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents="Hello"
)

print(response.text)
import time

# --- 設定區 ---
API_KEY = "PHTJpjhhPVzIdzjMEP84WKq5JiNRYxA6"
GEMINI_API_KEY = "AIzaSyDbb3R97kBvW7ngntK5XmIWICxMW8f9qs4" # ⬅️ 請在此處填入你的 Gemini API Key
SYMBOL = "HIMS"
BASE_PATH = Path(__file__).parent / "data"

# 初始化新版 Gemini 客戶端
client = genai.Client(api_key=GEMINI_API_KEY)

def get_gemini_analysis(metric_name, data_summary):
    """呼叫新版 Gemini API 根據數據生成分析原因"""
    prompt = f"""
    你是一位專業的財務分析師。請分析股票代號 {SYMBOL} 的 {metric_name} 指標。
    近期數據趨勢如下（由舊到新）：{data_summary}。
    請根據數據給出 4 個專業且具體的財報變動原因（每個原因約 20-30 字，繁體中文）。
    請直接以 JSON 陣列格式回傳內容，不要包含 Markdown 標籤或 ```json 字樣。
    範例格式：["原因1", "原因2", "原因3", "原因4"]
    """
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        # 清洗並解析 JSON
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        return json.loads(clean_text)
    except Exception as e:
        print(f"⚠️ Gemini 分析 {metric_name} 失敗: {e}")
        return ["市場需求波動", "營運成本控制調整", "產業競爭壓力優化", "宏觀經濟環境影響"]

def fetch_data(url):
    """修正過的抓取函數，確保傳入的是純字串 URL"""
    try:
        # 移除 URL 中可能存在的隱藏字元
        clean_url = str(url).strip()
        response = requests.get(clean_url)
        response.raise_for_status() # 如果狀態碼不是 200 會報錯
        return response.json()
    except Exception as e:
        print(f"❌ 抓取數據失敗: {e} | URL: {url}")
        return []

def save_combined_json(filename, records, metric_name):
    if not records:
        print(f"⚠️ {metric_name} 沒有數據，跳過輸出。")
        return

    recent_data = records[-4:]
    print(f"🤖 正在為 {metric_name} 產生 AI 分析...")
    ai_reasons = get_gemini_analysis(metric_name, recent_data)
    
    output = {
        "chartData": records,
        "aiReasons": ai_reasons
    }
    
    with open(BASE_PATH / filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ 已輸出至 {filename}")
    time.sleep(1) # 避免 API 頻率過快

def main():
    print(f"🌟 開始執行 {SYMBOL} 全自動化財報分析 (數據 + AI)...")

    # --- 1. 定義純淨的 URL ---
    base_url = "[https://financialmodelingprep.com/stable](https://financialmodelingprep.com/stable)"
    urls = {
        "iq": f"{base_url}/income-statement?symbol={SYMBOL}&period=quarter&apikey={API_KEY}",
        "ia": f"{base_url}/income-statement?symbol={SYMBOL}&period=annual&apikey={API_KEY}",
        "bq": f"{base_url}/balance-sheet-statement?symbol={SYMBOL}&period=quarter&apikey={API_KEY}",
        "cq": f"{base_url}/cash-flow-statement?symbol={SYMBOL}&period=quarter&apikey={API_KEY}",
        "ca": f"{base_url}/cash-flow-statement?symbol={SYMBOL}&period=annual&apikey={API_KEY}",
        "mq": f"{base_url}/key-metrics?symbol={SYMBOL}&apikey={API_KEY}",
        "mt": f"{base_url}/key-metrics-ttm?symbol={SYMBOL}&apikey={API_KEY}",
        "rq": f"{base_url}/ratios?symbol={SYMBOL}&apikey={API_KEY}",
        "rt": f"{base_url}/ratios-ttm?symbol={SYMBOL}&apikey={API_KEY}"
    }

    # 抓取數據
    data = {k: fetch_data(v) for k, v in urls.items()}

    # 轉換 DataFrame 並防呆 (避免 KeyError)
    df_iq = pd.DataFrame(data["iq"])
    df_ia = pd.DataFrame(data["ia"])
    df_bq = pd.DataFrame(data["bq"])
    df_cq = pd.DataFrame(data["cq"])
    df_ca = pd.DataFrame(data["ca"])
    df_mq = pd.DataFrame(data["mq"])
    df_rq = pd.DataFrame(data["rq"])

    # --- 2. 處理指標 ---
    if not df_iq.empty and "revenue" in df_iq.columns:
        df_iq_c = df_iq.dropna(subset=["revenue", "grossProfit", "netIncome"])
        save_combined_json("hims_revenue.json", [{"date": str(d), "revenue_million": float(v)/1e6} for d, v in zip(df_iq_c["date"], df_iq_c["revenue"])], "總營收")
        save_combined_json("hims_grossmargin.json", [{"date": str(row["date"]), "grossMargin": round(float(row["grossProfit"]/row["revenue"]*100), 2)} for _, row in df_iq_c.iterrows()], "毛利率")
    
    # ... 其餘指標依此類推 ...
    # 範例：ROE
    if not df_mq.empty and "returnOnEquity" in df_mq.columns:
        roe_recs = [{"date": str(d), "returnOnEquity": float(v)} for d, v in zip(df_mq["date"], df_mq["returnOnEquity"])]
        if data["mt"] and "returnOnEquityTTM" in data["mt"][0]:
            roe_recs.append({"date": "TTM", "returnOnEquity": float(data["mt"][0]["returnOnEquityTTM"])})
        save_combined_json("hims_ROE.json", roe_recs, "股東權益報酬率")

    print("\n✨ 更新完成！")

if __name__ == "__main__":
    main()