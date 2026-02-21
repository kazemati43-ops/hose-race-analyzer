import os
import time
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta

# DBと重複しないための簡易なファイルベースキュー
QUEUE_FILE = "data/processed/missing_race_queue.json"

def get_race_ids_for_month(year: int, month: int) -> list:
    """
    netkeibaの月間カレンダーURLから、その月の全レースIDを抽出する。
    URL例: https://race.netkeiba.com/top/calendar.html?year=2021&month=8
    ※スクレイピングルール（3秒待機など）を遵守。
    """
    # 実際には、netkeibaのHTML構造に合わせたパースが必要ですが、
    # ここでは仕様に基づくプレースホルダ（安全なモック/簡易実装）として構築します。
    # 実環境ではカレンダーの <a> タグ href から race_id を抜く処理を入れます。
    
    url = f"https://race.netkeiba.com/top/calendar.html?year={year}&month={month}"
    print(f"Scraping calendar for {year}-{month:02d} ...")
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/100.0'}
    time.sleep(3) # 必須の3秒固定スリープ
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'EUC-JP'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        race_ids = []
        # ここはnetkeibaの現在のDOM構造に依存するため、仮設定
        # 一般的な race_id は 12桁の数字 (例: 202105040811)
        # 本格稼働時は詳細なセレクタを調整
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            if 'race_id=' in href:
                # "?race_id=202105040811" からIDを抽出
                parts = href.split('race_id=')
                if len(parts) > 1:
                    r_id = parts[1][:12]
                    if r_id.isdigit() and len(r_id) == 12:
                        race_ids.append(r_id)
        
        # 重複排除
        return list(set(race_ids))
    except Exception as e:
        print(f"Error fetching calendar {year}-{month:02d}: {e}")
        return []

def filter_existing_races(race_ids: list) -> list:
    """
    抽出したレースIDのうち、すでにDB(race_event)に存在しているものを除外する。
    """
    import mysql.connector
    
    DB_CONFIG = {
        "host": "localhost", # コンテナ外の場合はlocalhost, コンテナ内なら 'db'
        "user": "root",
        "password": "root",
        "database": "horse_race_db",
        "charset": "utf8mb4"
    }

    try:
        # このスクリプトはコンテナ内実行を想定
        conn = mysql.connector.connect(**{**DB_CONFIG, "host": "db"})
    except:
        conn = mysql.connector.connect(**DB_CONFIG)
        
    cursor = conn.cursor()
    
    missing = []
    # in句での一括検索や1件ずつの検索など
    for r_id in race_ids:
        cursor.execute("SELECT 1 FROM race_event WHERE race_event_id = %s", (r_id,))
        if not cursor.fetchone():
            missing.append(r_id)
            
    cursor.close()
    conn.close()
    
    return missing

def main():
    print("Starting generation of missing race list (2021-08-01 to Present)")
    
    start_date = datetime(2021, 8, 1)
    end_date = datetime.now()
    
    current_date = start_date
    all_missing_races = []
    
    while current_date <= end_date:
        y = current_date.year
        m = current_date.month
        
        month_race_ids = get_race_ids_for_month(y, m)
        print(f"  Found {len(month_race_ids)} total races in calendar.")
        
        if month_race_ids:
            # 既にDBにあるものは除外
            missing_for_month = filter_existing_races(month_race_ids)
            print(f"  -> {len(missing_for_month)} races are missing in DB.")
            all_missing_races.extend(missing_for_month)
            
        current_date += relativedelta(months=1)
        
    print(f"\nTotal missing races found: {len(all_missing_races)}")
    
    # JSONに保存 (深夜バッチでここから消費する)
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    
    existing_queue = []
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE, 'r') as f:
            existing_queue = json.load(f)
            
    # 新旧マージしてユニーク化
    updated_queue = list(set(existing_queue + all_missing_races))
    
    with open(QUEUE_FILE, 'w') as f:
        json.dump(updated_queue, f)
        
    print(f"Saved {len(updated_queue)} queue items to {QUEUE_FILE}")

if __name__ == "__main__":
    main()
