import statistics
from typing import List, Dict, Any, Tuple
from src.api.core.models import RaceData, HorseBaseResult

class Condition:
    """単条件または複合条件を表現するクラス"""
    def __init__(self, key: str, name: str, evaluator: callable, group: str):
        self.key = key          # 例: "frame_1"
        self.name = name        # 例: "1枠"
        self.evaluator = evaluator # 馬のデータ(HorseBaseResult)を受け取りboolを返す関数
        self.group = group      # 独立性を担保するためのグループ名(例: "frame", "popularity")

class InferenceService:
    @staticmethod
    def _build_atomic_conditions() -> List[Condition]:
        conditions = []
        
        # 1. 枠 (1-8)
        for i in range(1, 9):
            conditions.append(Condition(f"frame_{i}", f"{i}枠", lambda h, i=i: h.frame == i, "frame"))
            
        # 2. 人気帯 (1, 2-3, 4-6, 7+)
        def pop_eval(h, min_p, max_p):
            if not h.popularity: return False
            return min_p <= h.popularity <= max_p
        
        conditions.append(Condition("pop_1", "1番人気", lambda h: pop_eval(h, 1, 1), "popularity"))
        conditions.append(Condition("pop_2_3", "2-3番人気", lambda h: pop_eval(h, 2, 3), "popularity"))
        conditions.append(Condition("pop_4_6", "4-6番人気", lambda h: pop_eval(h, 4, 6), "popularity"))
        conditions.append(Condition("pop_7_over", "7番人気以下", lambda h: h.popularity and h.popularity >= 7, "popularity"))
        
        # 3. オッズ帯 (<=3.9, 4.0-9.9, 10-19.9, 20+)
        def odds_eval(h, min_o, max_o):
            if not h.odds: return False
            return min_o <= h.odds <= max_o
            
        conditions.append(Condition("odds_under_3.9", "オッズ3.9倍以下", lambda h: odds_eval(h, 0, 3.9), "odds"))
        conditions.append(Condition("odds_4_9.9", "オッズ4.0-9.9倍", lambda h: odds_eval(h, 4.0, 9.9), "odds"))
        conditions.append(Condition("odds_10_19.9", "オッズ10.0-19.9倍", lambda h: odds_eval(h, 10.0, 19.9), "odds"))
        conditions.append(Condition("odds_20_over", "オッズ20倍以上", lambda h: h.odds and h.odds >= 20.0, "odds"))
        
        # 4. 馬体重帯
        weight_bins = ["<440", "440-459", "460-479", "480-499", "500-519", "520-539", "540+"]
        for wb in weight_bins:
            conditions.append(Condition(f"weight_{wb}", f"馬体重{wb}", lambda h, wb=wb: h.horse_weight_bin == wb, "horse_weight"))
            
        # 5. 上がり3F順位帯
        last3f_bins = ["1-3", "4-6", "7+"]
        for lb in last3f_bins:
            conditions.append(Condition(f"last3f_{lb}", f"上がり3F {lb}位", lambda h, lb=lb: h.last_3f_bin == lb, "last_3f"))
            
        # 6. 馬齢
        conditions.append(Condition("age_4", "4歳", lambda h: h.age_at_race == 4, "age"))
        conditions.append(Condition("age_5", "5歳", lambda h: h.age_at_race == 5, "age"))
        conditions.append(Condition("age_6", "6歳", lambda h: h.age_at_race == 6, "age"))
        conditions.append(Condition("age_7_over", "7歳以上", lambda h: h.age_at_race and h.age_at_race >= 7, "age"))
        
        # 7. 性別
        conditions.append(Condition("sex_male", "牡馬", lambda h: h.sex == "牡", "sex"))
        conditions.append(Condition("sex_female", "牝馬", lambda h: h.sex == "牝", "sex"))
        conditions.append(Condition("sex_gelding", "セ", lambda h: h.sex == "セ", "sex"))

        # 8. 直近5走: 最高格
        conditions.append(Condition("recent_g1", "近5走にG1出走あり", lambda h: h.recent_highest_grade == "G1", "recent_grade"))
        conditions.append(Condition("recent_g2_g3", "近5走最高がG2/G3", lambda h: h.recent_highest_grade in ["G2", "G3"], "recent_grade"))
        conditions.append(Condition("recent_op", "近5走最高がOP", lambda h: h.recent_highest_grade == "OP", "recent_grade"))
        
        # 9. 直近5走: 3着内回数
        conditions.append(Condition("recent_top3_0", "近5走3着内なし", lambda h: h.recent_top3_count == 0, "recent_top3"))
        conditions.append(Condition("recent_top3_1", "近5走3着内1回", lambda h: h.recent_top3_count == 1, "recent_top3"))
        conditions.append(Condition("recent_top3_2", "近5走3着内2回", lambda h: h.recent_top3_count == 2, "recent_top3"))
        conditions.append(Condition("recent_top3_3_over", "近5走3着内3回以上", lambda h: h.recent_top3_count >= 3, "recent_top3"))

        # 10. 直近5走: 各種経験
        conditions.append(Condition("exp_dirt_1600", "近5走ダ1600経験あり", lambda h: h.has_dirt_1600_exp, "exp_dist"))
        conditions.append(Condition("exp_tokyo", "近5走東京経験あり", lambda h: h.has_tokyo_exp, "exp_course"))
        
        # 血統等はパッチ完了後に母数が揃ってから拡張可能（今回は設計に準拠した基本セットを全実装）
        return conditions

    @staticmethod
    def _evaluate_condition_on_history(cond: Condition, history: List[RaceData]) -> Dict[str, Any]:
        """過去10年データ（年別）に対して条件の該当母数と3着内率を計算する"""
        n_all = 0
        n_top3 = 0
        yearly_rates = []

        for race in history:
            y_all = 0
            y_top3 = 0
            for horse in race.results:
                if cond.evaluator(horse):
                    y_all += 1
                    n_all += 1
                    if horse.rank and horse.rank <= 3:
                        y_top3 += 1
                        n_top3 += 1
            
            # その年に条件に該当する馬がいれば割合計算、いなければスキップ
            if y_all > 0:
                yearly_rates.append(y_top3 / y_all)
                
        # 中央値の算出 (年データが1件以上ある場合)
        median_rate = 0.0
        if yearly_rates:
            median_rate = statistics.median(yearly_rates)
            
        rate_3in = (n_top3 / n_all) if n_all > 0 else 0.0

        return {
            "key": cond.key,
            "name": cond.name,
            "n_all": n_all,
            "n_top3": n_top3,
            "rate_3in": rate_3in, # N_top3 / N_all 全期間プール
            "median_rate": median_rate,
            "years_appeared": len(yearly_rates)
        }

    @staticmethod
    def run_inference(history: List[RaceData]) -> Dict[str, Any]:
        """
        全条件（単条件＋複合条件）について母数・勝率を計算し、
        3着内率 >= 25% の有意な条件を抽出する
        """
        atomics = InferenceService._build_atomic_conditions()
        results = []
        
        # 1. 単条件の評価
        for cond in atomics:
            stats = InferenceService._evaluate_condition_on_history(cond, history)
            # 母数が過少（例: 過去10年で3頭未満）のものは参考外として弾く
            if stats["n_all"] >= 5: 
                stats["is_composite"] = False
                results.append(stats)
                
        # 2. 複合条件（AND）の生成と評価
        # 独立したGroupを持つ2つの条件の全組み合わせを生成
        for i in range(len(atomics)):
            for j in range(i + 1, len(atomics)):
                c1 = atomics[i]
                c2 = atomics[j]
                
                # 同一文脈のグループ（例: oddsとpopularity等）を組み合わせないようにする
                # 要件定義に基づく「同一文脈派生」の除外
                if c1.group == c2.group: continue
                # 強い相関があるグループは複合させないガードレール
                if set([c1.group, c2.group]).issubset({"odds", "popularity"}): continue 
                
                comp_key = f"{c1.key}_AND_{c2.key}"
                comp_name = f"{c1.name} ＋ {c2.name}"
                # lambda の遅延評価によるキャプチャバグを防ぐため c1,c2をデフォルト引数で束縛する
                comp_eval = lambda h, cond1=c1, cond2=c2: cond1.evaluator(h) and cond2.evaluator(h)
                
                comp_cond = Condition(comp_key, comp_name, comp_eval, "composite")
                stats = InferenceService._evaluate_condition_on_history(comp_cond, history)
                
                if stats["n_all"] >= 5:
                    stats["is_composite"] = True
                    results.append(stats)

        # 3. 採択基準の適用 (3着内率の中央値が25%以上)
        adopted = [r for r in results if r["median_rate"] >= 0.25]
        
        # 評価順にソート (中央値が高い順 -> 母数が多い順)
        adopted.sort(key=lambda x: (x["median_rate"], x["n_all"]), reverse=True)
        
        return {
            "total_candidates_evaluated": len(results),
            "adopted_conditions": adopted
        }

    @staticmethod
    def score_entries(entries: List[HorseBaseResult], adopted_conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        import math
        
        scored_horses = []
        atomics = base_atomics = InferenceService._build_atomic_conditions()
        
        # 採用された条件のevaluatorを文字列名(key)から再構成するためのマッピング作成
        # （本番ではConditionオブジェクトをそのまま持ち回すか、評価用辞書を作る）
        cond_dict = {}
        for c in atomics:
            cond_dict[c.key] = c
            
        # 複合条件のevaluatorの動的復元
        # key 形式: "A_AND_B"
        comp_evaluators = {}
        for ac in adopted_conditions:
            k = ac["key"]
            if ac["is_composite"]:
                parts = k.split("_AND_")
                if len(parts) == 2:
                    k1, k2 = parts
                    c1 = cond_dict.get(k1)
                    c2 = cond_dict.get(k2)
                    if c1 and c2:
                        comp_evaluators[k] = lambda h, cond1=c1, cond2=c2: cond1.evaluator(h) and cond2.evaluator(h)
            else:
                comp_evaluators[k] = cond_dict[k].evaluator
                
        # 各馬のスコアリング
        max_possible_score = 0.0
        
        for horse in entries:
            horse_score = 0.0
            matched_conds = []
            
            for ac in adopted_conditions:
                k = ac["key"]
                evaluator = comp_evaluators.get(k)
                
                if evaluator and evaluator(horse):
                    # 【スコア計算仕様】: 重み w(c) = log10(n_all + 1) * years_appeared
                    # ※母数が大きく、毎年安定して出現しているものを高く評価
                    weight = math.log10(ac["n_all"] + 1) * (ac["years_appeared"] / 10.0)
                    contribution = ac["median_rate"] * weight
                    
                    horse_score += contribution
                    
                    matched_conds.append({
                        "name": ac["name"],
                        "median_rate": ac["median_rate"],
                        "n_top3": ac["n_top3"],
                        "n_all": ac["n_all"],
                        "rate_3in": ac["rate_3in"]
                    })
                    
            scored_horses.append({
                "horse_id": horse.horse_id,
                "name": horse.name,
                "raw_score": horse_score,
                "matched_conditions": matched_conds
            })

        # 正規化 (0-100)
        # 1位の馬のスコアを100とする相対評価
        max_raw = max([h["raw_score"] for h in scored_horses]) if scored_horses else 1.0
        if max_raw == 0: max_raw = 1.0
        
        for h in scored_horses:
            h["score"] = round((h["raw_score"] / max_raw) * 100, 1)
            
        # スコア順にソート
        scored_horses.sort(key=lambda x: x["score"], reverse=True)
        
        # 順位(rank)を付与
        for i, h in enumerate(scored_horses):
            h["predicted_rank"] = i + 1
            
        return scored_horses
