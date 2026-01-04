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
    """從 Supabase 抓取所有狀態為 'review' 的任務"""
    print("🔍 正在掃描 Supabase 尋找待處理任務 (status='review')...")
    try:
        # 必須抓取 user_id，否則後續 upsert 會因為缺少複合鍵而失敗
        res = supabase.table("tracked_stocks") \
            .select("symbol, user_id") \
            .eq("status", "review") \
            .execute()
        return res.data 
    except Exception as e:
        print(f"❌ 抓取任務清單失敗: {e}")
        return []

def get_financial_data(symbol):
    """抓取財務數據 (保持原本邏輯)"""
    print(f"📦 正在從 FMP 抓取 {symbol} 的數據...")
    # ... (此處省略 safe_fetch 等獲取數據的過程，保持你原本的 get_financial_data 內容)
    # 確保回傳 final_data_dict
    pass 

def run_full_update(task):
    symbol = task['symbol']
    user_id = task['user_id']
    print(f"🚀 開始處理 {symbol} (User: {user_id})...")
    
    try:
        # 1. 抓取數據
        final_data_dict = get_financial_data(symbol)
        if not final_data_dict: return
        
        # 2. AI 分析
        print(f"🤖 正在請求 Gemini 生成分析報告...")
        prompt = f"""
        你是一位專業的財務分析師。請分析以下 {symbol} 的財務數據，並嚴格以純 JSON 格式回傳。
        
        要求：
        1. 語言：必須使用『繁體中文』。
        2. 結構：
           - "one_liner": 對該公司的財務狀況做一句話總結。
           - "by_metric": 針對數據中提供的指標建立物件，結構包含：
             - "summary": 50-100 字的專業分析摘要。
             - "bullets": 3 個該指標的關鍵趨勢或觀察點 (Array)。
           - "risks": 條列至少兩項主要財務風險 (Array)。
        
        數據內容：
        {json.dumps(final_data_dict)}
        """
        
        response = client.models.generate_content(
            model="gemini-2.5-flash", 
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        ai_analysis = json.loads(response.text)

        # 3. 組合 Payload
        final_payload = {
            "symbol": symbol.upper(),
            "as_of": time.strftime("%Y-%m-%d"),
            "data": final_data_dict,
            "ai": ai_analysis,
            "ai_generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        }
        
        base_url = "https://hims-chart.vercel.app/"
        
        # 4. 執行精準更新 (對應 user_id + symbol 的複合索引)
        supabase.table("tracked_stocks").upsert(
            {
                "user_id": user_id, 
                "symbol": symbol.upper(),
                "report_json": final_payload,
                "status": "ready",
                "report_url": f"{base_url}?symbol={symbol.upper()}"
            },
            on_conflict="user_id, symbol" 
        ).execute()
        
        print(f"✅ {symbol} 更新成功！狀態已轉為 ready。")
        
    except Exception as e:
        print(f"💥 處理 {symbol} 時發生錯誤: {e}")

if __name__ == "__main__":
    task_list = get_review_list()
    if not task_list:
        print("☕ 目前沒有待處理任務。")
    else:
        for task in task_list:
            run_full_update(task)
            time.sleep(1) # 避免 API 頻率過快
    print("✨ 程序執行完畢。")