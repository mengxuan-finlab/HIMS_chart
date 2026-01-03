import requests, json, os, time
from google import genai
from supabase import create_client
from dotenv import load_dotenv

# --- 1. 配置區 ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_MAIN") 
FMP_API_KEY = os.getenv("FMP_API_KEY")

# 初始化
client = genai.Client(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_review_list():
    """從 Supabase 抓取所有狀態為 'review' 的股票"""
    print("🔍 正在掃描 Supabase 尋找待處理任務 (status='review')...")
    try:
        res = supabase.table("tracked_stocks").select("symbol").eq("status", "review").execute()
        return [item['symbol'] for item in res.data]
    except Exception as e:
        print(f"❌ 抓取任務清單失敗: {e}")
        return []

def safe_fetch(url, params):
    """安全抓取 API，確保回傳的是 List 而非錯誤字典"""
    try:
        resp = requests.get(url, params=params, timeout=10).json()
        if isinstance(resp, list):
            return resp
        return [] # 如果回傳的是 {"Error":...} 則回傳空陣列避免後續報錯
    except Exception as e:
        print(f"⚠️ API 請求異常: {e}")
        return []

def get_financial_data(symbol):
    """抓取 16 項核心財務指標"""
    print(f"📦 正在從 FMP 抓取 {symbol} 的數據...")
    base = "https://financialmodelingprep.com/stable"
    p = {"symbol": symbol, "apikey": FMP_API_KEY}
    
    # 執行所有 API 請求 (使用安全抓取)
    iq = safe_fetch(f"{base}/income-statement", {**p, "period": "quarter"})
    ia = safe_fetch(f"{base}/income-statement", {**p, "period": "annual"})
    bq = safe_fetch(f"{base}/balance-sheet-statement", {**p, "period": "quarter"})
    ca = safe_fetch(f"{base}/cash-flow-statement", {**p, "period": "annual"})
    mq = safe_fetch(f"{base}/key-metrics", p)
    mt = safe_fetch(f"{base}/key-metrics-ttm", p)
    rq = safe_fetch(f"{base}/ratios", p)
    rt = safe_fetch(f"{base}/ratios-ttm", p)

    # 封裝數據
    try:
        data = {
            "revenue": [{"date": x.get("date"), "value": x.get("revenue", 0)/1e6} for x in iq[:5]],
            "gross_profit": [{"date": x.get("date"), "value": x.get("grossProfit", 0)/1e6} for x in iq[:5]],
            "gross_margin": [{"date": x.get("date"), "value": (x.get("grossProfit", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
            "net_income": [{"date": x.get("date"), "value": x.get("netIncome", 0)/1e6} for x in iq[:5]],
            "net_margin": [{"date": x.get("date"), "value": (x.get("netIncome", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
            "eps_diluted": [{"date": x.get("date"), "value": x.get("epsdiluted", 0)} for x in ia[:5]],
            "total_equity": [{"date": x.get("date"), "value": x.get("totalEquity", 0)/1e6} for x in bq[:5]],
            "current_ratio": [{"date": x.get("date"), "value": x.get("totalCurrentAssets", 0)/x.get("totalCurrentLiabilities", 1) if x.get("totalCurrentLiabilities") else 0} for x in bq[:5]],
            "long_term_solvency": [{"date": x.get("date"), "value": x.get("totalDebt", 0)/x.get("netCashProvidedByOperatingActivities", 1) if x.get("netCashProvidedByOperatingActivities") else 0} for x in bq[:5]],
            "operating_cash_flow": [{"date": x.get("date"), "value": x.get("operatingCashFlow", 0)} for x in ca[:5]],
            "free_cash_flow": [{"date": x.get("date"), "value": x.get("freeCashFlow", 0)} for x in ca[:5]],
            "capEX_OCF": [{"date": x.get("date"), "value": x.get("capitalExpenditure", 0)/x.get("operatingCashFlow", 1) if x.get("operatingCashFlow") else 0} for x in ca[:5]],
            "ocf_netincome": [{"date": x.get("date"), "value": x.get("operatingCashFlow", 0)/x.get("netIncome", 1) if x.get("netIncome") else 0} for x in ca[:5]],
            "roe": [{"date": x.get("date"), "value": x.get("returnOnEquity", 0)} for x in mq[:5]],
            "roa": [{"date": x.get("date"), "value": x.get("returnOnAssets", 0)} for x in mq[:5]],
            "pe": [{"date": x.get("date"), "value": x.get("priceToEarningsRatio", 0)} for x in rq[:5]],
            "peg": [{"date": x.get("date"), "value": x.get("priceToEarningsGrowthRatio", 0)} for x in rq[:5]],
        }

        # 補充 TTM 數據 (空值檢查)
        if mt and isinstance(mt, list):
            data["roe"].append({"date": "TTM", "value": mt[0].get("returnOnEquityTTM", 0)})
            data["roa"].append({"date": "TTM", "value": mt[0].get("returnOnAssetsTTM", 0)})
        if rt and isinstance(rt, list):
            data["pe"].append({"date": "TTM", "value": rt[0].get("priceToEarningsRatioTTM", 0)})
            data["peg"].append({"date": "TTM", "value": rt[0].get("priceToEarningsGrowthRatioTTM", 0)})

        return data
    except Exception as e:
        print(f"❌ 封裝數據時出錯: {e}")
        return None

def run_full_update(symbol):
    print(f"🚀 開始處理 {symbol}...")
    try:
        # 1. 抓取數據
        final_data_dict = get_financial_data(symbol)
        if not final_data_dict: return

        # 2. AI 分析 (強化 Prompt 與 Response 格式控制)
        print(f"🤖 正在請求 Gemini 生成分析報告...")
        prompt = f"請分析以下 {symbol} 的財務數據，並以純 JSON 格式回傳。結構包含：one_liner (一句話評析), risks (Array, 3個風險點), by_metric (Object, 每個指標含 summary 與 bullets Array)。數據內容：{json.dumps(final_data_dict)}"
        
        # 使用 Gemini 1.5 Flash 的 JSON 模式
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        ai_analysis = json.loads(response.text)

        # 3. 組合最終 Payload
        final_payload = {
            "symbol": symbol,
            "as_of": time.strftime("%Y-%m-%d"),
            "data": final_data_dict,
            "ai": ai_analysis,
            "ai_generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }

        # 4. 上傳 Supabase
        supabase.table("tracked_stocks").upsert({
            "symbol": symbol,
            "report_json": final_payload,
            "status": "ready"
        }).execute()
        
        print(f"✅ {symbol} 同步成功！")
        
    except Exception as e:
        print(f"💥 處理 {symbol} 時發生錯誤: {e}")

if __name__ == "__main__":
    review_list = get_review_list()
    if not review_list:
        print("☕ 目前沒有待處理任務。")
    else:
        for s in review_list:
            run_full_update(s)
            time.sleep(1)
    print("✨ 程序執行完畢。")