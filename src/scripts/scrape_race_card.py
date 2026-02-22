import os
import sys
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any

# srcディレクトリへのパスを追加
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.scripts.crawl_netkeiba import NetkeibaCrawler
from src.api.core.models import HorseBaseResult

class RaceCardScraper:
    def __init__(self):
        self.crawler = NetkeibaCrawler()

    def fetch_current_race_card(self, race_id: str) -> List[Dict[str, Any]]:
        """
        指定されたレースID（例: 202505010811）の「出馬表ページ」に1回だけアクセスし、
        出走馬のID、枠順、馬番、馬名、斤量、騎手、現在オッズを抽出する。
        """
        # 出馬表ページのURL (race.netkeiba.com系)
        url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
        
        print(f"Fetching race card for {race_id} from: {url}")
        html = self.crawler.fetch_html(url)
        
        if not html:
            print("  -> Failed to fetch HTML.")
            return []

        soup = BeautifulSoup(html, 'html.parser')
        entries = []
        
        # 出馬表テーブルを探す (netkeibaの出馬表はいくつかclassのパターンがある)
        shutuba_table = soup.find('table', class_='Shutuba_Table')
        
        if not shutuba_table:
             print("  -> Warning: 'Shutuba_Table' not found. This might not be a valid race card URL yet, or the DOM changed.")
             return []

        # TR要素から各馬の行を抽出
        horse_rows = shutuba_table.find_all('tr', class_='HorseList')
        
        for row in horse_rows:
            try:
                # 枠番
                frame_td = row.find('td', class_='Waku')
                frame_number = int(frame_td.text.strip()) if frame_td and frame_td.text.strip().isdigit() else None
                
                # 馬番
                umaban_td = row.find('td', class_='Umaban')
                umaban = int(umaban_td.text.strip()) if umaban_td and umaban_td.text.strip().isdigit() else None
                
                # 馬情報
                horse_info_td = row.find('td', class_='HorseInfo')
                horse_id = None
                horse_name = "Unknown"
                if horse_info_td:
                    a_tag = horse_info_td.find('a')
                    if a_tag:
                        horse_name = a_tag.text.strip()
                        href = a_tag.get('href', '')
                        m = re.search(r'/horse/(\d+)', href)
                        if m:
                            horse_id = m.group(1)
                
                # 斤量
                jockey_td = row.find('td', class_='Jockey') # 斤量は騎手と同じセルまたは隣接セルにあることが多い
                weight = 0.0
                jockey_name = "Unknown"
                if jockey_td:
                    # 騎手名抽出
                    jockey_a = jockey_td.find('a')
                    if jockey_a:
                        jockey_name = jockey_a.text.strip()
                    # 斤量抽出（netkeibaの構造によるが、通常は 56.0 等直接書かれているかspanの中）
                    weight_m = re.search(r'(\d{2}\.\d)', jockey_td.text)
                    if weight_m:
                        weight = float(weight_m.group(1))

                # オッズと人気 (事前オッズ。確定前はオッズセルに記載される)
                odds_td = row.find('td', class_='Odds')
                odds = None
                popularity = None
                if odds_td:
                    txt = odds_td.text.strip()
                    # "12.3" のような数値を抽出
                    odds_m = re.search(r'(\d+\.\d+)', txt)
                    if odds_m:
                        odds = float(odds_m.group(1))
                    
                # 人気 (人気セルがある場合)
                pop_td = row.find('td', class_='Popularity')
                if pop_td and pop_td.text.strip().isdigit():
                    popularity = int(pop_td.text.strip())

                # 馬IDが取れなかった行（取消等）はスキップ
                if not horse_id:
                    continue

                entries.append({
                    "horse_id": horse_id,
                    "horse_name": horse_name,
                    "frame_number": frame_number,
                    "horse_number": umaban,
                    "weight_carried": weight,
                    "jockey": jockey_name,
                    "odds": odds,
                    "popularity": popularity
                })
                
            except Exception as e:
                print(f"  -> Error parsing row: {e}")
                continue

        print(f"Successfully parsed {len(entries)} horses from race card {race_id}.")
        return entries

def get_virtual_entries() -> List[Dict[str, Any]]:
    """
    テスト用モック：出馬表ページに該当レースがない場合等に使用する、仮想の出走馬リスト。
    （フェブラリーS用ダミー）
    """
    return [
        {"horse_id": "2020102600", "horse_name": "オメガギネス", "frame_number": 1, "horse_number": 2, "weight_carried": 57.0, "jockey": "ルメール", "odds": 4.5, "popularity": 1},
        {"horse_id": "2021105020", "horse_name": "ハッピーマン", "frame_number": 2, "horse_number": 4, "weight_carried": 56.0, "jockey": "川田将雅", "odds": 5.2, "popularity": 2},
        {"horse_id": "2020100234", "horse_name": "ブライアンセンス", "frame_number": 3, "horse_number": 6, "weight_carried": 57.0, "jockey": "モレイラ", "odds": 6.8, "popularity": 3},
        {"horse_id": "2020102658", "horse_name": "ペリエール", "frame_number": 4, "horse_number": 8, "weight_carried": 57.0, "jockey": "戸崎圭太", "odds": 9.1, "popularity": 4},
        {"horse_id": "2019105432", "horse_name": "ドンフランキー", "frame_number": 5, "horse_number": 10, "weight_carried": 57.0, "jockey": "池添謙一", "odds": 12.5, "popularity": 5},
        {"horse_id": "2020101890", "horse_name": "ミックファイア", "frame_number": 6, "horse_number": 12, "weight_carried": 57.0, "jockey": "御神本訓", "odds": 18.2, "popularity": 6},
    ]

if __name__ == "__main__":
    # テスト実行
    scraper = RaceCardScraper()
    # 2025年のフェブラリーSIDは公開終了している可能性があるため、
    # 直近公開中またはダミーのレースIDを入れて挙動を見る
    res = scraper.fetch_current_race_card("202505010811")
    if not res:
        print("Using virtual fallback entries for test.")
        res = get_virtual_entries()
        
    for r in res:
        print(r)
