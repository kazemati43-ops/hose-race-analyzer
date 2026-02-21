import os
import pandas as pd
import mysql.connector

# DB接続設定
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "horse_race_db",
    "charset": "utf8mb4"
}

def parse_time(time_str):
    if pd.isna(time_str) or not isinstance(time_str, str):
        return None
    time_str = str(time_str).strip()
    if ':' in time_str:
        try:
            m, s = time_str.split(':')
            return float(m) * 60 + float(s)
        except:
            return None
    return parse_numeric(time_str)

def parse_numeric(val):
    try:
        if pd.isna(val) or val == '':
            return None
        return float(val)
    except:
        return None

def parse_int(val):
    try:
        if pd.isna(val) or val == '':
            return None
        return int(float(val))
    except:
        return None

def import_kaggle_data():
    csv_path = "data/raw/19860105-20210731_race_result.csv"
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    print("Connecting to database...")
    # docker-compose内のapiサービスから実行されることを想定 (host="db")
    # ローカルから直接実行している場合は"localhost"
    try:
        conn = mysql.connector.connect(**{**DB_CONFIG, "host": "db"})
    except:
        conn = mysql.connector.connect(**DB_CONFIG)
        
    cursor = conn.cursor()
    
    chunksize = 100000
    total_processed = 0
    first_race_date = None
    last_race_date = None
    
    # 読み込みの最適化とエラー無視のため、主要なカラムのみ抽出してパース
    print(f"Start processing {csv_path} with chunksize={chunksize}...")
    for chunk in pd.read_csv(csv_path, chunksize=chunksize, dtype=str):
        # 1. 2001年1月1日以降のフィルタ（直近25年・満年齢表記統一）
        chunk['レース日付'] = pd.to_datetime(chunk['レース日付'], errors='coerce')
        # 2000年以前のデータはスキップ
        chunk = chunk[chunk['レース日付'] >= pd.Timestamp('2001-01-01')].copy()
        
        if chunk.empty:
            continue
            
        c_min = chunk['レース日付'].min()
        c_max = chunk['レース日付'].max()
        if first_race_date is None or c_min < first_race_date:
            first_race_date = c_min
        if last_race_date is None or c_max > last_race_date:
            last_race_date = c_max
            
        chunk['race_year'] = chunk['レース日付'].dt.year
        chunk = chunk.where(pd.notnull(chunk), None)
        
        # --- 2. horseテーブルへのインポート ---
        horse_records = set() # 重複排除のためsetを使用
        for _, row in chunk.iterrows():
            name = row.get('馬名')
            if not name:
                continue
            age = parse_int(row.get('馬齢'))
            year = row.get('race_year')
            birth_year = (year - age) if age is not None and year is not None else None
            horse_records.add((name, name, row.get('性別'), birth_year))
            
        if horse_records:
            cursor.executemany('''
                INSERT INTO horse (horse_id, name, sex, birth_year)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                sex=VALUES(sex),
                birth_year=COALESCE(horse.birth_year, VALUES(birth_year))
            ''', list(horse_records))
            
        # --- 3. race_eventテーブルへのインポート ---
        race_events = set()
        for _, row in chunk.iterrows():
            race_id = str(row.get('レースID')) if row.get('レースID') else None
            if not race_id:
                continue
            race_events.add((
                race_id,
                "UNKNOWN_MASTER", # 仕様上必須だが今回特定困難なためダミー
                row.get('レース日付').strftime('%Y-%m-%d') if row.get('レース日付') else None,
                row.get('race_year'),
                row.get('競馬場名'),
                parse_int(row.get('距離(m)')),
                row.get('芝・ダート区分'),
                row.get('馬場状態1')
            ))
            
        if race_events:
            cursor.executemany('''
                INSERT INTO race_event (race_event_id, race_master_id, race_date, race_year, course_id, distance, surface, track_condition)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                race_date=VALUES(race_date), race_year=VALUES(race_year), course_id=VALUES(course_id),
                distance=VALUES(distance), surface=VALUES(surface), track_condition=VALUES(track_condition)
            ''', list(race_events))
            
        # --- 4. race_resultテーブルへのインポート ---
        race_results = []
        for _, row in chunk.iterrows():
            race_id = str(row.get('レースID')) if row.get('レースID') else None
            horse_name = row.get('馬名')
            if not race_id or not horse_name:
                continue
                
            race_results.append((
                race_id,
                horse_name, # horse_idは馬名
                parse_int(row.get('着順')),
                parse_int(row.get('枠番')),
                parse_numeric(row.get('単勝')),
                parse_int(row.get('人気')),
                parse_numeric(row.get('斤量')),
                parse_int(row.get('馬体重')),
                None, # last_3fはスキーマがINTだがCSVが秒数(float)のためNULLとする
                parse_time(row.get('タイム')),
                row.get('騎手'),
                row.get('調教師')
            ))
            
        if race_results:
            cursor.executemany('''
                INSERT INTO race_result (
                    race_event_id, horse_id, `rank`, frame, odds, popularity, 
                    carried_weight, horse_weight, last_3f, time, jockey, trainer
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    `rank`=VALUES(`rank`), frame=VALUES(frame), odds=VALUES(odds),
                    popularity=VALUES(popularity), carried_weight=VALUES(carried_weight),
                    horse_weight=VALUES(horse_weight), last_3f=VALUES(last_3f),
                    time=VALUES(time), jockey=VALUES(jockey), trainer=VALUES(trainer)
            ''', race_results)
            
        conn.commit()
        total_processed += len(chunk)
        print(f"Processed valid rows: {total_processed} (skipped < 2001-01-01)")
        
    cursor.close()
    conn.close()
    
    print("\n--- IMPORT FINISHED ---")
    if first_race_date and last_race_date:
        print(f"登録された最初のレースの日付: {first_race_date.strftime('%Y-%m-%d')}")
        print(f"登録された最後のレースの日付: {last_race_date.strftime('%Y-%m-%d')}")
    else:
        print("> 2001-01-01以降のデータが見つかりませんでした。")

if __name__ == "__main__":
    import_kaggle_data()
