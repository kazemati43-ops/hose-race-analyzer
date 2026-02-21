import os
import sys
import json

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.services.analyzer import AnalyzerService
from src.api.services.inference import InferenceService

def main():
    target_race_id = "202505010811"  # 今年の出馬表の代用として2025年データを指定
    target_date = "2025-02-23"     # 2025年フェブラリーS開催日
    
    print("Building analysis scope...")
    scope = AnalyzerService.build_analysis_scope(target_race_id, target_date)
    
    print("Running Inference over historical data...")
    # NOTE: 本来は target_race_id の年は history から除くのが厳密だが、今回はテストのためそのまま流し込む
    result = InferenceService.run_inference(scope.historical_races)
    adopted_conds = result['adopted_conditions']
    print(f"Adopted Conditions: {len(adopted_conds)}")
    
    print("\nScoring Current Entries...")
    scored = InferenceService.score_entries(scope.current_entries, adopted_conds)
    
    print("\nTop 5 Scored Horses:")
    for horse in scored[:5]:
        print(f"Rank {horse['predicted_rank']}: {horse['name']} (Score: {horse['score']})")
        print("  Top 3 contributing conditions:")
        # 寄与度等を含めてソート（今回は単に中央値が高いものを3つ表示）
        sorted_conds = sorted(horse["matched_conditions"], key=lambda c: c["median_rate"], reverse=True)
        for mc in sorted_conds[:3]:
            print(f"    - {mc['name']} (Median Top3: {mc['median_rate']:.2%}, N: {mc['n_top3']}/{mc['n_all']})")
    
    # 総合情報の最下位確認
    if scored:
        worst = scored[-1]
        print(f"\nLowest Ranked Horse:")
        print(f"Rank {worst['predicted_rank']}: {worst['name']} (Score: {worst['score']})")

if __name__ == "__main__":
    main()
