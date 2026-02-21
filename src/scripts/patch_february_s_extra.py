import os
import sys
import re
from bs4 import BeautifulSoup
import mysql.connector

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

def time_str_to_seconds(ts):
    """'1:34.4' のような文字列を秒数（float）に変換"""
    if not ts or ':' not in ts:
        return None
    try:
        parts = ts.split(':')
        mins = int(parts[0])
        secs = float(parts[1])
        return round(mins * 60 + secs, 1)
    except ValueError:
        return None

def extract_horse_weight(hw_str):
    """'510(+2)' のような文字列から '510' を抽出してintで返す"""
    m = re.match(r'^(\d+)', hw_str)
    if m:
        return int(m.group(1))
    return None

def patch_extra_columns(crawler, cursor):
    """過去5年(2021-2025)のフェブラリーSから未取得のカラムを抽出しUPDATEする"""
    print("=== Patching Extra Columns (2021-2025) ===")
    race_ids = ["202105010811", "202205010811", "202305010811", "202405010811", "202505010811"]
    
    for rid in race_ids:
        print(f"Reading cached HTML for Race_ID: {rid} ...")
        url = f"https://db.netkeiba.com/race/{rid}"
        html = crawler.fetch_html(url)
        if not html:
            continue
            
        soup = BeautifulSoup(html, 'html.parser')
        results_table = soup.find('table', class_='race_table_01')
        if not results_table:
            continue
            
        rows = results_table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            # 必要なカラムにアクセス可能かチェック（基本は21列ほどある）
            if len(cols) > 18:
                # horse_id
                horse_a = cols[3].find('a')
                if not horse_a or '/horse/' not in horse_a['href']: continue
                h_id = horse_a['href'].strip('/').split('/')[-1]
                
                # 1. frame (枠番)
                frame_str = cols[1].text.strip()
                frame = int(frame_str) if frame_str.isdigit() else None
                
                # 2. carried_weight (斤量)
                cw_str = cols[5].text.strip()
                cw = None
                try: cw = float(cw_str)
                except ValueError: pass
                
                # 3. jockey (騎手)
                jockey_text = cols[6].text.strip().replace('\n', '')
                
                # 4. time (タイム秒数換算)
                time_val = time_str_to_seconds(cols[7].text.strip())
                
                # 5. horse_weight (馬体重)
                hw_val = extract_horse_weight(cols[14].text.strip())
                
                # 6. trainer (調教師)
                trainer_text = cols[18].text.strip().replace('\n', '')
                
                cursor.execute("""
                    UPDATE race_result
                    SET frame=COALESCE(%s, frame),
                        carried_weight=COALESCE(%s, carried_weight),
                        horse_weight=COALESCE(%s, horse_weight),
                        time=COALESCE(%s, time),
                        jockey=COALESCE(%s, jockey),
                        trainer=COALESCE(%s, trainer)
                    WHERE race_event_id=%s AND horse_id=%s
                """, (frame, cw, hw_val, time_val, jockey_text, trainer_text, rid, h_id))
                
        print(f"  -> Merged extra columns for race {rid}")

def main():
    crawler = NetkeibaCrawler()
    conn = get_db_connection()
    cursor = conn.cursor()

    patch_extra_columns(crawler, cursor)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("=== Patch Completed ===")

if __name__ == "__main__":
    main()
