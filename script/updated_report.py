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
    # 封裝數據 (加入雙重命名檢查與更嚴格的空值保護)
    try:
        data = {
            "revenue": [{"date": x.get("date"), "value": x.get("revenue", 0)/1e6} for x in iq[:5]],
            "gross_profit": [{"date": x.get("date"), "value": x.get("grossProfit", 0)/1e6} for x in iq[:5]],
            "gross_margin": [{"date": x.get("date"), "value": (x.get("grossProfit", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
            "net_income": [{"date": x.get("date"), "value": x.get("netIncome", 0)/1e6} for x in iq[:5]],
            "net_margin": [{"date": x.get("date"), "value": (x.get("netIncome", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
            
            # 強化版 EPS 取值：同時嘗試小寫與駝峰式命名
            "eps_diluted": [{"date": x.get("date"), "value": x.get("epsdiluted") or x.get("epsDiluted") or 0} for x in ia[:5]],
            
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
        
        # 2. AI 分析
        print(f"🤖 正在請求 Gemini 生成分析報告...")
        
        # 修正後的精確 Prompt
        prompt = f"""
        你是一位專業的財務分析師。請分析以下 {symbol} 的財務數據，並嚴格以純 JSON 格式回傳。
        
        要求：
        1. 語言：必須使用『繁體中文』。
        2. 結構：
           - "one_liner": 對該公司的財務狀況做一句話總結。
           - "by_metric": 針對數據中提供的每一項指標（例如 revenue, gross_margin, net_income 等）建立一個物件，結構必須包含：
             - "summary": 一段 50-100 字的專業分析摘要。
             - "bullets": 3 個該指標的關鍵趨勢或觀察點（Array of strings）。
           - "risks": 條列至少兩項主要的財務風險（Array of strings）。
        
        數據內容：
        {json.dumps(final_data_dict)}
        """
        
        # 保持原有的 generate_content 設定
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        ai_analysis = json.loads(response.text)

        # 3. 組合 Payload (確保 Symbol 為大寫以匹配資料庫)
        # 注意：這裡我們只提供要更新的欄位，其餘欄位(如 userid) 會被保留
        final_payload = {
            "symbol": symbol.upper(),
            "as_of": time.strftime("%Y-%m-%d"),
            "data": final_data_dict,
            "ai": ai_analysis,
            "ai_generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        base_url = "https://hims-chart.vercel.app/" # 從你的 Vercel 部署紀錄取得
        # 2. 執行精準更新 (Upsert)
        # 只要設定了 on_conflict="symbol"，Supabase 就會去抓現有的 ID 41
        # 它只會覆蓋 report_json 和 status，原本的 uuid (userid) 會被原地保留！
        supabase.table("tracked_stocks").upsert(
            {
                "symbol": symbol.upper(),
                "report_json": final_payload, # 這裡現在有定義了
                "status": "ready",
                # --- 新增這行：自動拼湊網址存入 report_url 欄位 ---
                "report_url": f"{base_url}?symbol={symbol.upper()}"
            },
            on_conflict="symbol" 
        ).execute()
        
        print(f"✅ {symbol} 更新成功！UserID 已保留，數據已寫入。")
        
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