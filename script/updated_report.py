import requests, json, os, time
from google import genai
from supabase import create_client
from dotenv import load_dotenv
from serpapi import GoogleSearch 

# --- 1. 配置區 ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_MAIN") 
FMP_API_KEY = os.getenv("FMP_API_KEY")
SERPAPI_KEY = os.getenv("SERPAPI_KEY") 

# 初始化
client = genai.Client(api_key=GEMINI_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 輔助功能函式 ---

def get_review_list():
    print("🔍 掃描待處理任務...")
    try:
        # 1. 先抓出 status='review' 的股票
        res = supabase.table("tracked_stocks").select("symbol, user_id").eq("status", "review").execute()
        stocks = res.data
        
        # 2. 為每筆資料手動補上方案等級
        for stock in stocks:
            user_id = stock['user_id']
            # 去 profiles 表查該使用者的 plan
            user_res = supabase.table("profiles").select("plan").eq("id", user_id).single().execute()
            print(f"DEBUG - 使用者 {user_id} 查詢結果: {user_res.data}")
            # 存入 stock 物件中，方便後面讀取
            stock['user_plan'] = user_res.data.get('plan', 'free') if user_res.data else 'free'
            
        return stocks
    except Exception as e:
        print(f"❌ 抓取失敗: {e}")
        return []

def get_market_news(symbol):
    """Pro 專屬：抓取即時市場成因"""
    print(f"🌐 Pro 功能：搜尋 {symbol} 的市場背景...")
    params = {
        "engine": "google",
        "q": f"{symbol} stock earnings reasons analysis",
        "api_key": SERPAPI_KEY
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        # 抓取搜尋結果的前 5 條摘要作為 AI 背景
        snippets = [item.get("snippet", "") for item in results.get("organic_results", [])[:5]]
        return "\n".join(snippets)
    except Exception as e:
        print(f"⚠️ SerpApi 異常: {e}")
        return ""

def safe_fetch(url, params):
    """安全抓取 API 資料"""
    try:
        resp = requests.get(url, params=params, timeout=10).json()
        return resp if isinstance(resp, list) else []
    except Exception as e:
        print(f"⚠️ API 請求異常: {e}")
        return []

def get_financial_data(symbol):
    """抓取 16 項核心財務指標"""
    print(f"📦 正在從 FMP 抓取 {symbol} 的數據...")
    base = "https://financialmodelingprep.com/stable"
    p = {"symbol": symbol, "apikey": FMP_API_KEY}
    
    # 抓取各類報表
    iq = safe_fetch(f"{base}/income-statement", {**p, "period": "quarter"})
    ia = safe_fetch(f"{base}/income-statement", {**p, "period": "annual"})
    bq = safe_fetch(f"{base}/balance-sheet-statement", {**p, "period": "quarter"})
    ca = safe_fetch(f"{base}/cash-flow-statement", {**p, "period": "annual"})
    mq = safe_fetch(f"{base}/key-metrics", p)
    mt = safe_fetch(f"{base}/key-metrics-ttm", p)
    rq = safe_fetch(f"{base}/ratios", p)
    rt = safe_fetch(f"{base}/ratios-ttm", p)

    try:
        data = {
            "revenue": [{"date": x.get("date"), "value": x.get("revenue", 0)/1e6} for x in iq[:5]],
            "gross_profit": [{"date": x.get("date"), "value": x.get("grossProfit", 0)/1e6} for x in iq[:5]],
            "gross_margin": [{"date": x.get("date"), "value": (x.get("grossProfit", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
            "net_income": [{"date": x.get("date"), "value": x.get("netIncome", 0)/1e6} for x in iq[:5]],
            "net_margin": [{"date": x.get("date"), "value": (x.get("netIncome", 0)/x.get("revenue", 1))*100 if x.get("revenue") else 0} for x in iq[:5]],
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
        # 加入 TTM 數據
        if mt:
            data["roe"].append({"date": "TTM", "value": mt[0].get("returnOnEquityTTM", 0)})
            data["roa"].append({"date": "TTM", "value": mt[0].get("returnOnAssetsTTM", 0)})
        if rt:
            data["pe"].append({"date": "TTM", "value": rt[0].get("priceToEarningsRatioTTM", 0)})
            data["peg"].append({"date": "TTM", "value": rt[0].get("priceToEarningsGrowthRatioTTM", 0)})
        return data
    except Exception as e:
        print(f"❌ 數據封裝出錯: {e}")
        return None

# --- 3. 核心處理邏輯 ---

def run_full_update(task):
    symbol = task['symbol']
    user_id = task['user_id']
    # ✅ 只留下這一行，讀取你在 get_review_list 裡面手動塞入的欄位
    user_plan = task.get('user_plan', 'free')
    
    print(f"🚀 處理中: {symbol} (等級: {user_plan})")
    
    try:
        # 1. 抓取財務數據
        final_data_dict = get_financial_data(symbol)
        if not final_data_dict: return
        
        # 2. 判斷是否使用 SerpApi (Pro 專屬)
        market_context = ""
        if user_plan == "pro":
            market_context = get_market_news(symbol)
            
        # 3. 組合分級 Prompt 指令
        reasoning_req = ""
        if user_plan == "pro":
            reasoning_req = f"請結合以下市場動態背景，深入分析指標變動的『商業成因』：{market_context}"
        else:
            reasoning_req = "請在 related_reasons 欄位固定回傳 ['升級 Pro 解鎖深度成因分析']。"

        prompt = f"""
        你是一位專業財務分析師。請分析 {symbol} 的財務數據並回傳純 JSON。

        ⚠️ 重要要求：請務必針對以下指定的 ID 分別提供分析，不得合併、更名或遺漏：
        1. 損益類：revenue, gross_profit, net_income, eps_diluted
        2. 負債類：total_equity, current_ratio, long_term_solvency
        3. 現金流：operating_cash_flow, free_cash_flow, capEX_OCF, ocf_netincome
        4. 估值類：roe, roa, pe, peg

        格式要求：
        - "one_liner": 財務狀況一句話總結
        - "by_metric": {{
            "每個指定的 ID": {{
                "summary": "數據解讀摘要",
                "bullets": ["趨勢觀察1", "趨勢觀察2", "趨勢觀察3"],
                "related_reasons": ["成因分析1", "成因分析2", "成因分析3"]
            }}
        }}
        - "risks": ["主要的財務風險清單"]
        
        分析要求：必須使用繁體中文。即便數據為 0 或變動極小，也請針對該指標提供簡短解讀。
        {reasoning_req}
        數據內容：{json.dumps(final_data_dict)}
        """
        
        # 4. 呼叫 Gemini 2.5
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        ai_analysis = json.loads(response.text)

        # 5. 回寫 Supabase 並更新狀態
        supabase.table("tracked_stocks").upsert({
            "user_id": user_id, 
            "symbol": symbol.upper(),
            "report_json": {
                "symbol": symbol.upper(),
                "as_of": time.strftime("%Y-%m-%d"),
                "data": final_data_dict,
                "ai": ai_analysis,
                "user_plan": user_plan
            },
            "status": "ready",
            "report_url": f"https://hims-chart.vercel.app/?symbol={symbol.upper()}"
        }, on_conflict="user_id, symbol").execute()
        
        print(f"✅ {symbol} 更新成功。")
        
    except Exception as e:
        print(f"💥 處理 {symbol} 時發生錯誤: {e}")

if __name__ == "__main__":
    task_list = get_review_list()
    if not task_list:
        print("☕ 目前沒有待處理任務 (status='review')。")
    else:
        for task in task_list:
            run_full_update(task)
            time.sleep(1) # 避免 API 頻率限制
    print("✨ 程序執行完畢。")