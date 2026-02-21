import os
import sys
import re
from bs4 import BeautifulSoup
import mysql.connector

# srcディレクトリへのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.scripts.crawl_netkeiba import NetkeibaCrawler

DB_CONFIG = {
    "host": "db",
    "user": "root",
    "password": "root",
    "database": "horse_race_db",
    "charset": "utf8mb4"
}

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except:
        return mysql.connector.connect(**{**DB_CONFIG, "host": "localhost"})

def main():
    crawler = NetkeibaCrawler()
    conn = get_db_connection()
    cursor = conn.cursor()

    race_ids = ["202105010811", "202205010811", "202305010811", "202405010811", "202505010811"]

    for rid in race_ids:
        print(f"Applying patch for Race_ID: {rid} ...")
        url = f"https://db.netkeiba.com/race/{rid}"
        # DB上のキャッシュHTMLを読み込む（force_refresh=Falseがデフォルト）
        html = crawler.fetch_html(url)
        if not html:
            print(f"  -> Failed to read HTML for {rid}")
            continue

        soup = BeautifulSoup(html, 'html.parser')
        
        # --- 日付とlap_timeの抽出 ---
        title = soup.find('title')
        title_text = title.text if title else ""
        date_str = None
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', title_text)
        if m:
            date_str = f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"
        else:
            date_str = f"{rid[:4]}-02-20"  # fallback
            
        lap_td = soup.find('td', class_='race_lap_cell')
        lap_time = lap_td.text.strip() if lap_td else None

        # race_eventをINSERT IGNOREで枠作成
        cursor.execute('''
            INSERT IGNORE INTO race_event (race_event_id, race_master_id, race_date, distance, lap_time) 
            VALUES (%s, %s, %s, %s, %s)
        ''', (rid, 'UNKNOWN', date_str, 1600, lap_time))

        # 既に存在する場合（2021年など）のため確実にUPDATE
        cursor.execute("UPDATE race_event SET lap_time=%s WHERE race_event_id=%s", (lap_time, rid))

        print(f"  -> Merged race_event: {rid}, date: {date_str}, lap: {lap_time}")

        # --- race_result の抽出 ---
        results_table = soup.find('table', class_='race_table_01')
        if results_table:
            rows = results_table.find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) > 11:
                    # 着順
                    rank_str = cols[0].text.strip()
                    rank = None
                    if rank_str.isdigit():
                        rank = int(rank_str)
                    
                    # horse_id
                    horse_a = cols[3].find('a')
                    if not horse_a or '/horse/' not in horse_a['href']:
                        continue
                    # "https://db.netkeiba.com/horse/2018105027/" -> strip('/') -> "horse/2018105027" -> split('/') -> ["horse", "2018105027"]
                    h_id = horse_a['href'].strip('/').split('/')[-1]


                    # passing_order
                    passing = cols[10].text.strip()

                    # last_3f
                    last_3f_str = cols[11].text.strip()
                    last_3f = None
                    try:
                        last_3f = float(last_3f_str)
                    except ValueError:
                        pass # 数値変換不可の場合はNULL

                    # horse への最低限の登録（外部キー制約回避用。名前も分かる範囲で入れる）
                    horse_name = horse_a.text.strip()
                    cursor.execute('''
                        INSERT IGNORE INTO horse (horse_id, name) VALUES (%s, %s)
                    ''', (h_id, horse_name))

                    # INSERT IGNORE INTO race_result
                    cursor.execute('''
                        INSERT IGNORE INTO race_result (race_event_id, horse_id, `rank`, passing_order, last_3f)
                        VALUES (%s, %s, %s, %s, %s)
                    ''', (rid, h_id, rank, passing, last_3f))
                    
                    # UPDATE (既に存在する場合は上書き)
                    cursor.execute('''
                        UPDATE race_result
                        SET `rank`=COALESCE(%s, `rank`),
                            passing_order=%s,
                            last_3f=COALESCE(%s, last_3f)
                        WHERE race_event_id=%s AND horse_id=%s
                    ''', (rank, passing, last_3f, rid, h_id))

    conn.commit()
    cursor.close()
    conn.close()
    print("=== Patch Completed ===")

if __name__ == "__main__":
    main()
