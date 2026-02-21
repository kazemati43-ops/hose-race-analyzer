from typing import List, Dict, Any
from src.api.core.models import AnalysisScope

class ValidationException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

class ValidatorService:
    @staticmethod
    def validate_scope(scope: AnalysisScope):
        """入力データの整合性（欠損等の基本条件）を検証する"""
        if not scope.historical_races:
            raise ValidationException("過去のレースデータが取得されていません。")
        if len(scope.historical_races) < 5:
            # 要件上は過去10年だが、現在DBに5年分しかないため5でガード
            raise ValidationException(f"過去の開催データが不足しています（{len(scope.historical_races)}年分のみ）")
            
        for race in scope.historical_races:
            if not race.results:
                raise ValidationException(f"{race.year}年の出走馬データが存在しません。")

    @staticmethod
    def validate_inference_results(history: List[Any], adopted_conditions: List[Dict[str, Any]]):
        """推論エンジンによって生成された条件リストの論理的・数学的検証を行う"""
        
        for cond in adopted_conditions:
            # 1. 複合条件のルール検証 (3つ以上のANDは禁止)
            if "_AND_" in cond["key"]:
                parts = cond["key"].split("_AND_")
                if len(parts) > 2:
                    raise ValidationException(f"禁止事項: 3つ以上の複合条件が生成されました（{cond['name']}）")
                    
            # 2. 割合と母数の再計算と検証 (事実と出力の乖離がないか)
            if cond["n_all"] == 0:
                raise ValidationException(f"エラー: 母数が0の条件が採用されています（{cond['name']}）")
            
            recalculated_rate = cond["n_top3"] / cond["n_all"]
            # 浮動小数点の誤差を考慮して差をチェック
            if abs(cond["rate_3in"] - recalculated_rate) > 0.001:
                raise ValidationException(
                    f"計算不一致エラー: 条件『{cond['name']}』の算出割合({cond['rate_3in']})が母数からの再計算({recalculated_rate})と一致しません。"
                )
                
            # 3. 採否基準 (25%ルール)
            if cond["median_rate"] < 0.25:
                raise ValidationException(f"採否ルール違反: 3着内率中央値が25%未満の条件が採用されています（{cond['name']}, {cond['median_rate']}）")

    @staticmethod
    def validate_scored_results(scored_entries: List[Dict[str, Any]]):
        """最終出力される各馬の情報の検証"""
        if not scored_entries:
            raise ValidationException("出馬表のスコアリング結果が空です。")
            
        # スコアの正規化範囲をチェック (0.0 から 100.0)
        for horse in scored_entries:
            if not (0.0 <= horse["score"] <= 100.0):
                raise ValidationException(f"正規化エラー: {horse['name']} のスコアが範囲外です（{horse['score']}）")
            
            for cond in horse["matched_conditions"]:
                if "median_rate" not in cond or "n_all" not in cond or "n_top3" not in cond:
                    raise ValidationException(f"情報欠落: {horse['name']} の根拠条件に母数または割合が欠落しています。")
