import os
import time
import json
import logging
from datetime import datetime, timedelta
import mysql.connector

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("data/processed/crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": "localhost", # コンテナ外の場合はlocalhost, コンテナ内なら 'db'
    "user": "root",
    "password": "root",
    "database": "horse_race_db",
    "charset": "utf8mb4"
}

QUEUE_FILE = "data/processed/missing_race_queue.json"

def get_db_connection():
    try:
        # コンテナ内実行を想定
        return mysql.connector.connect(**{**DB_CONFIG, "host": "db"})
    except:
        return mysql.connector.connect(**DB_CONFIG)

def sleep_until_midnight():
    """現在の時刻から翌日の深夜0時までの秒数を計算してスリープする"""
    now = datetime.now()
    # 翌日の0時0分0秒
    tomorrow = now + timedelta(days=1)
    midnight = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0)
    
    # テスト時など、既に深夜(0時〜1時)に起動している場合はそのまま進行
    if now.hour == 0:
        logger.info("It is already midnight, starting immediately...")
        return
        
    seconds_to_wait = (midnight - now).total_seconds()
    hours = int(seconds_to_wait // 3600)
    minutes = int((seconds_to_wait % 3600) // 60)
    
    logger.info(f"Waiting until midnight... sleeping for {hours} hours and {minutes} minutes.")
    time.sleep(seconds_to_wait)

STATE_FILE = "data/processed/crawler_state.json"

def _check_global_rate_limit():
    """100リクエストごとに30分待機するグローバル制限"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state = {"count": 0, "reset_time": 0.0}
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
        except Exception:
            pass
            
    now = time.time()
    
    # ウィンドウ（30分）が過ぎていればリセット
    if now > state.get("reset_time", 0):
        state["count"] = 0
        state["reset_time"] = now + 1800  # 30分後
        
    # 100回に達していたら、ウィンドウが明けるまで待機
    if state.get("count", 0) >= 100:
        sleep_time = state.get("reset_time", 0) - now
        if sleep_time > 0:
            logger.info(f"[RATE LIMIT] 100 requests reached. Sleeping for {int(sleep_time)} seconds (30 mins strict rule)...")
            time.sleep(sleep_time)
        # 待機明けにリセット
        state["count"] = 0
        state["reset_time"] = time.time() + 1800
        
    # カウントをインクリメントして保存
    state["count"] = state.get("count", 0) + 1
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def safe_scrape(func, *args, **kwargs):
    """
    100リクエスト/30分制限、3秒固定スリープ、指数的バックオフのラッパー
    """
    _check_global_rate_limit()

    max_retries = 3
    base_sleep = 3
    
    for attempt in range(max_retries):
        time.sleep(base_sleep) # 強制3秒スリープ
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Scraping error (attempt {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                backoff = base_sleep * (2 ** (attempt + 1)) # 6秒, 12秒...
                logger.info(f"Retrying after {backoff} seconds...")
                time.sleep(backoff)
            else:
                logger.error("Max retries reached. Skipping.")
                return None

# --- 各優先度のスクレイピング実処理モック ---

def scrape_february_s_2026():
    """優先度1: 2026年フェブラリーSの登録馬/出走馬の血統補完"""
    logger.info("Starting Priority 1: 2026 February S. horses profile retrieval")
    # 実際の実装:
    # 1. 出馬表URLからhorse_idを抽出
    # 2. 各horse_idに対して db に血統情報がなければ安全にスクレイピングしてUPDATE
    # ※ここではモックとしてのログ出力のみ
    safe_scrape(lambda: logger.info("  -> Fetched entry list for Feb S. ..."))
    safe_scrape(lambda: logger.info("  -> Fetched and updated pedigree for horse A ..."))
    safe_scrape(lambda: logger.info("  -> Fetched and updated pedigree for horse B ..."))
    logger.info("Priority 1 completed.")

def scrape_missing_races():
    """優先度2: 2021年8月以降の未取得レース収集"""
    logger.info("Starting Priority 2: Missing races retrieval (2021-08-01 to Present)")
    if not os.path.exists(QUEUE_FILE):
        logger.info("  -> No missing race queue found. generate_missing_list.py will run first.")
        # ここで generate_missing_list.main() を呼び出すことも可能
        return
        
    with open(QUEUE_FILE, 'r') as f:
        queue = json.load(f)
        
    if not queue:
        logger.info("  -> Missing race queue is empty.")
        return
        
    logger.info(f"  -> Found {len(queue)} races in queue. Starting processing...")
    
    # 実際の実装: queueの先頭からURLを叩き、結果をDBにINSERTしていく
    # チャンクごとにQUEUE_FILEを上書き保存し、中断に備える
    processed = 0
    while queue and processed < 100: # 1日の取得上限（安全装置。実際はもっと多くてもよい）
        r_id = queue.pop(0)
        safe_scrape(lambda: logger.info(f"  -> Scraping race {r_id} ..."))
        # scrape_race_logic(r_id) ... DB INSERT
        processed += 1
        
    # 残りを保存
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f)
        
    logger.info(f"Priority 2 completed. Processed {processed} races. Remaining in queue: {len(queue)}")

def scrape_recent_horses_pedigree():
    """優先度3: 直近5年以内に出走歴がある馬の血統補完"""
    logger.info("Starting Priority 3: Recent (last 5 years) horses pedigree retrieval")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 過去5年のレースに出走した馬のうち、sire(父)がNULLの馬を抽出
    # ※ LIMITを設けて1日あたりの負荷を制御
    query = """
        SELECT DISTINCT rr.horse_id
        FROM race_result rr
        JOIN race_event re ON rr.race_event_id = re.race_event_id
        JOIN horse h ON rr.horse_id = h.horse_id
        WHERE re.race_year >= (YEAR(CURDATE()) - 5)
          AND h.sire IS NULL
        LIMIT 50
    """
    cursor.execute(query)
    horses = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    
    if not horses:
        logger.info("  -> No horses need pedigree update.")
        return
        
    logger.info(f"  -> Found {len(horses)} horses to update.")
    for h_id in horses:
        safe_scrape(lambda: logger.info(f"  -> Scraping pedigree for horse {h_id} ..."))
        # update_horse_pedigree(h_id) ... DB UPDATE
        
    logger.info("Priority 3 completed.")

def main():
    logger.info("=== Midnight Crawler Service Initialized ===")
    
    # 深夜0時になるまでスリープして待機
    sleep_until_midnight()
    
    logger.info("=== Starting Daily Crawl Tasks ===")
    
    # 【優先度1】2026年フェブラリーSの血統・出馬表スクレイピング
    scrape_february_s_2026()
    
    # 【優先度2】未取得期間のレース結果の収集
    scrape_missing_races()
    
    # 【優先度3】直近5年出走馬の血統マスター補完
    scrape_recent_horses_pedigree()
    
    logger.info("=== All Daily Crawl Tasks Completed ===")

if __name__ == "__main__":
    main()
