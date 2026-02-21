import os
import sys
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

# ユーザー指定の16頭のデータ
TARGET_HORSES = [
    {"num": 1, "name": "オメガギネス", "sex_age": "牡6", "id": "2020102600"},
    {"num": 2, "name": "ハッピーマン", "sex_age": "牡4", "id": "2022105151"},
    {"num": 3, "name": "ブライアンセンス", "sex_age": "牡6", "id": "2020100234"},
    {"num": 4, "name": "ペリエール", "sex_age": "牡6", "id": "2020102658"},
    {"num": 5, "name": "シックスペンス", "sex_age": "牡5", "id": "2021105141"},
    {"num": 6, "name": "ラムジェット", "sex_age": "牡5", "id": "2021105031"},
    {"num": 7, "name": "ロングラン", "sex_age": "セ8", "id": "2018104899"},
    {"num": 8, "name": "サクラトゥジュール", "sex_age": "セ9", "id": "2017101869"},
    {"num": 9, "name": "ダブルハートボンド", "sex_age": "牝5", "id": "2021105020"},
    {"num": 10, "name": "ロードクロンヌ", "sex_age": "牡5", "id": "2021102551"},
    {"num": 11, "name": "サンライズホーク", "sex_age": "セ7", "id": "2019100410"},
    # ユーザー指示内でコスタノヴァのIDがオメガギネスと同じ(2020102600)になっていたため、本来の12桁等があれば別だが指示通り一旦送信
    # netkeibaの実際のIDはコスタノヴァ = 2020102605 等かもしれないが、指定されたIDを使用する
    {"num": 12, "name": "コスタノヴァ", "sex_age": "牡6", "id": "2020102600"},
    {"num": 13, "name": "ナチュラルライズ", "sex_age": "牡4", "id": "2022105152"},
    {"num": 14, "name": "ウィルソンテソーロ", "sex_age": "牡7", "id": "2019106263"},
    {"num": 15, "name": "ペプチドナイル", "sex_age": "牡8", "id": "2018105155"},
    {"num": 16, "name": "サイモンザナドゥ", "sex_age": "牡6", "id": "2020100235"},
]

def parse_odds_and_popularity_from_race(crawler, cursor):
    """過去5年(2021-2025)のフェブラリーSからオッズと人気を抽出しUPDATEする"""
    print("=== Patching Odds & Popularity (2021-2025) ===")
    race_ids = ["202105010811", "202205010811", "202305010811", "202405010811", "202505010811"]
    
    for rid in race_ids:
        print(f"Reading cached HTML for Race_ID: {rid} ...")
        url = f"https://db.netkeiba.com/race/{rid}"
        # キャッシュ優先 (force_refresh=False)
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
            if len(cols) > 13:
                # horse_id
                horse_a = cols[3].find('a')
                if not horse_a or '/horse/' not in horse_a['href']: continue
                h_id = horse_a['href'].strip('/').split('/')[-1]
                
                # odds (単勝) は12列目(index 12)
                odds_str = cols[12].text.strip()
                odds = None
                try: odds = float(odds_str)
                except ValueError: pass
                
                # popularity (人気) は13列目(index 13)
                pop_str = cols[13].text.strip()
                pop = None
                if pop_str.isdigit(): pop = int(pop_str)
                
                if odds is not None or pop is not None:
                    cursor.execute("""
                        UPDATE race_result
                        SET odds=COALESCE(%s, odds), popularity=COALESCE(%s, popularity)
                        WHERE race_event_id=%s AND horse_id=%s
                    """, (odds, pop, rid, h_id))
        print(f"  -> Extracted odds/popularity for race {rid}")

def scrape_and_update_target_horses(crawler, cursor):
    """指定された16頭のプロフィールから性別・生年・血統を同期する"""
    print("\n=== Patching Missing Horse Profiles (16 Target Horses) ===")
    
    for horse in TARGET_HORSES:
        h_id = horse["id"]
        h_name = horse["name"]
        sex_age = horse["sex_age"]
        sex = "牡" if "牡" in sex_age else ("牝" if "牝" in sex_age else "セ")
        
        # 生年の計算 (2026年時点の年齢から逆算。厳密にはプロフィールから取得するがバックアップとして)
        age = int(sex_age.replace(sex, ""))
        birth_year = 2026 - age
        
        print(f"Scraping profile for {h_name} ({h_id}) ...")
        url = f"https://db.netkeiba.com/horse/{h_id}"
        html = crawler.fetch_html(url)
        if not html:
            continue
            
        soup = BeautifulSoup(html, 'html.parser')
        sire, dam, damsire = None, None, None
        
        # 血統専用ページからの取得
        ped_url = f"https://db.netkeiba.com/horse/ped/{h_id}/"
        ped_html = crawler.fetch_html(ped_url)
        if ped_html:
            ped_soup = BeautifulSoup(ped_html, 'html.parser')
            blood_table = ped_soup.find('table', class_='blood_table')
            if blood_table:
                a_tags = blood_table.find_all('a')
                # 構造: a_tags = [父名, '血統', '産駒', 父の父名, '血統', ...母名, '血統', '産駒', 母の父名, '血統', ...]
                # netkeibaのblood_tableでは、0番目=父、1番目=血統（リンク）、要素の中で実名が並ぶ順番を推測する。
                # 確実な取り方としては、td階層を使う方法に戻す。
                tds = blood_table.find_all('td')
                if len(tds) >= 3:
                    # 改行文字が含まれるため取り除く
                    sire = tds[0].text.strip().split('\n')[0].strip()
                    dam = tds[2].text.strip().split('\n')[0].strip()
                    damsire = tds[3].text.strip().split('\n')[0].strip()
                
        # プロフィールテーブルから生年月日を取得
        prof_table = soup.find('table', summary='馬データ')
        if prof_table:
            for tr in prof_table.find_all('tr'):
                th = tr.find('th')
                if th and th.text.strip() == '生年月日':
                    td = tr.find('td')
                    if td:
                        # 2020年2月18日
                        m = re.search(r'(\d{4})年', td.text)
                        if m:
                            birth_year = int(m.group(1))
                            
        # horseテーブルの更新 (INSERT IGNORE付き)
        cursor.execute("""
            INSERT IGNORE INTO horse (horse_id, name, sex, birth_year, sire, dam, damsire)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                name=VALUES(name), sex=VALUES(sex), birth_year=VALUES(birth_year),
                sire=VALUES(sire), dam=VALUES(dam), damsire=VALUES(damsire)
        """, (h_id, h_name, sex, birth_year, sire, dam, damsire))
        
        print(f"  -> Synced: {h_name} ({sex} {birth_year}), Sire: {sire}, Dam: {dam}")

def main():
    crawler = NetkeibaCrawler()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. オッズと人気の補完
    parse_odds_and_popularity_from_race(crawler, cursor)
    
    # 2. 16頭の血統・属性の補完
    scrape_and_update_target_horses(crawler, cursor)
    
    conn.commit()
    cursor.close()
    conn.close()
    print("=== Patch Data Sync Completed ===")

if __name__ == "__main__":
    main()
