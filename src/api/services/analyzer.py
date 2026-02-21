from typing import List, Dict, Any
from src.api.core.database import get_db_connection
from src.api.core.models import HorseBaseResult, RaceData, AnalysisScope

class AnalyzerService:
    @staticmethod
    def _bin_horse_weight(weight: int) -> str:
        if weight is None or weight == 0:
            return "欠損"
        if weight < 440: return "<440"
        if weight < 460: return "440-459"
        if weight < 480: return "460-479"
        if weight < 500: return "480-499"
        if weight < 520: return "500-519"
        if weight < 540: return "520-539"
        return "540+"

    @staticmethod
    def _bin_last_3f(rank: int) -> str:
        if rank is None or rank == 0:
            return "欠損"
        if rank <= 3: return "1-3"
        if rank <= 6: return "4-6"
        return "7+"

    @staticmethod
    def _bin_avg_rank(avg: float) -> str:
        if avg <= 3.9: return "<=3.9"
        if avg <= 6.9: return "4.0-6.9"
        return "7.0+"

    @staticmethod
    def get_recent_5_races(cursor, horse_id: str, before_date: str) -> Dict[str, Any]:
        """指定日以前の直近5走データを取得し、派生特徴量を計算する"""
        query = """
            SELECT 
                r.rank, re.distance, re.surface, re.course_id, rm.grade
            FROM race_result r
            JOIN race_event re ON r.race_event_id = re.race_event_id
            LEFT JOIN race_master rm ON re.race_master_id = rm.race_master_id
            WHERE r.horse_id = %s AND re.race_date < %s
            ORDER BY re.race_date DESC
            LIMIT 5
        """
        cursor.execute(query, (horse_id, before_date))
        rows = cursor.fetchall()
        
        has_dirt_1600 = False
        has_tokyo = False
        top3_count = 0
        ranks = []
        highest_grade = "OTHER" # 簡易判定：G1 > G2 > G3 > OP > OTHER
        
        grade_ranks = {"G1": 5, "G2": 4, "G3": 3, "OP": 2, "OTHER": 1, None: 1}
        current_highest_rank = 0

        for row in rows:
            rank_val, distance, surface, course_id, grade = row
            
            # 着順のパース（'1', '10', '取消' などが入る可能性があるため安全にint化）
            rank = None
            if rank_val:
                try:
                    rank = int(rank_val)
                except ValueError:
                    pass

            if rank is not None and rank > 0:
                ranks.append(rank)
                if rank <= 3:
                    top3_count += 1
            if distance == 1600 and surface == "ダート":
                has_dirt_1600 = True
            if course_id in ("東京", "05"): # course_idの実態に合わせて調整（ここでは安全に文字列一致を想定）
                has_tokyo = True
                
            g_rank = grade_ranks.get(grade, 1)
            if g_rank > current_highest_rank:
                current_highest_rank = g_rank
                highest_grade = grade if grade else "OTHER"

        avg_rank = sum(ranks) / len(ranks) if ranks else 99.9

        return {
            "recent_highest_grade": highest_grade,
            "recent_top3_count": top3_count,
            "recent_avg_rank_bin": AnalyzerService._bin_avg_rank(avg_rank),
            "has_dirt_1600_exp": has_dirt_1600,
            "has_tokyo_exp": has_tokyo
        }

    @staticmethod
    def get_historical_data(race_name_keyword: str="フェブラリー", limit_years: int=10) -> List[RaceData]:
        """指定レースの過去履歴を取得する（RAGのRetrievalに相当）"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 今回はフェブラリーS用として固定のrace_event_id等で引くか、名前で引く設計
        # ※ 実運用では race_master と紐付けるが、現在は手動パッチした2021-2025を確実にとるようクエリ構築
        target_event_ids = ["202105010811", "202205010811", "202305010811", "202405010811", "202505010811"] # 過去5年分（要件上過去10年だが現在データがある分を全取得）
        
        format_strings = ','.join(['%s'] * len(target_event_ids))
        query = f"""
            SELECT 
                r.race_event_id, re.race_year, re.race_date,
                r.horse_id, h.name, r.rank, r.frame, r.odds, r.popularity,
                r.carried_weight, r.horse_weight, r.last_3f,
                h.sex, h.birth_year, h.sire, h.dam, h.damsire
            FROM race_result r
            JOIN race_event re ON r.race_event_id = re.race_event_id
            JOIN horse h ON r.horse_id = h.horse_id
            WHERE r.race_event_id IN ({format_strings})
            ORDER BY re.race_year DESC
        """
        cursor.execute(query, tuple(target_event_ids))
        rows = cursor.fetchall()
        
        # 年ごとにグルーピング
        races_dict = {}
        for row in rows:
            rid = row["race_event_id"]
            if rid not in races_dict:
                # race_year が DB上でNULLの場合は日付やIDの先頭から補完する
                r_year = row["race_year"]
                if not r_year:
                    r_year = int(str(row["race_date"])[:4]) if row["race_date"] else int(rid[:4])
                    
                races_dict[rid] = {
                    "race_event_id": rid,
                    "year": r_year,
                    "results": []
                }
            
            # 直近5走特徴量抽出（レース日基準）
            recent_features = AnalyzerService.get_recent_5_races(cursor, row["horse_id"], str(row["race_date"]))
            
            # 生年からの年齢計算
            age = row["race_year"] - row["birth_year"] if row["birth_year"] else None
            
            result = HorseBaseResult(
                race_event_id=rid,
                horse_id=row["horse_id"],
                name=row["name"],
                rank=row["rank"],
                frame=row["frame"],
                odds=float(row["odds"]) if row["odds"] is not None else None,
                popularity=row["popularity"],
                carried_weight=float(row["carried_weight"]) if row["carried_weight"] else None,
                horse_weight=row["horse_weight"],
                last_3f=row["last_3f"],
                sex=row["sex"],
                birth_year=row["birth_year"],
                sire=row["sire"],
                dam=row["dam"],
                damsire=row["damsire"],
                age_at_race=age,
                horse_weight_bin=AnalyzerService._bin_horse_weight(row["horse_weight"]),
                last_3f_bin=AnalyzerService._bin_last_3f(row["last_3f"]),
                **recent_features
            )
            races_dict[rid]["results"].append(result)
            
        cursor.close()
        conn.close()
        
        return [RaceData(**v) for v in races_dict.values()]
        
    @staticmethod
    def get_current_entries(target_race_id: str, target_date: str) -> List[HorseBaseResult]:
        """今年の出馬表の取得と前処理（現状は固定の16頭などのDBデータから取得を想定）"""
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # 今回のフェブラリーS用パッチで挿入した枠番等を使用する場合、対象レースIDを直接引く
        query = """
            SELECT 
                r.race_event_id, r.horse_id, h.name, r.rank, r.frame, r.odds, r.popularity,
                r.carried_weight, r.horse_weight, r.last_3f,
                h.sex, h.birth_year, h.sire, h.dam, h.damsire
            FROM race_result r
            JOIN horse h ON r.horse_id = h.horse_id
            WHERE r.race_event_id = %s
        """
        cursor.execute(query, (target_race_id,))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            # 今年のターゲット日付未満の5走
            recent_features = AnalyzerService.get_recent_5_races(cursor, row["horse_id"], target_date)
            # 現在は仮で2026年想定
            age = 2026 - row["birth_year"] if row["birth_year"] else None
            
            result = HorseBaseResult(
                race_event_id=row["race_event_id"],
                horse_id=row["horse_id"],
                name=row["name"],
                rank=row["rank"],
                frame=row["frame"],
                odds=row["odds"],
                popularity=row["popularity"],
                carried_weight=float(row["carried_weight"]) if row["carried_weight"] else None,
                horse_weight=row["horse_weight"],
                last_3f=row["last_3f"],
                sex=row["sex"],
                birth_year=row["birth_year"],
                sire=row["sire"],
                dam=row["dam"],
                damsire=row["damsire"],
                age_at_race=age,
                horse_weight_bin=AnalyzerService._bin_horse_weight(row["horse_weight"]),
                last_3f_bin=AnalyzerService._bin_last_3f(row["last_3f"]),
                **recent_features
            )
            results.append(result)
            
        cursor.close()
        conn.close()
        return results

    @staticmethod
    def build_analysis_scope(target_race_id: str, target_date: str) -> AnalysisScope:
        historical = AnalyzerService.get_historical_data()
        current = AnalyzerService.get_current_entries(target_race_id, target_date)
        return AnalysisScope(
            target_race_id=target_race_id,
            historical_races=historical,
            current_entries=current
        )
