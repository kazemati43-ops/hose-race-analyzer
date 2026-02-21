import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
import pprint

from src.api.services.analyzer import AnalyzerService
from src.api.services.inference import InferenceService

def main():
    target_race_id = "202605010811" 
    target_date = "2026-02-22"
    
    print("Building analysis scope...")
    scope = AnalyzerService.build_analysis_scope(target_race_id, target_date)
    
    print(f"Historical Races Pulled: {len(scope.historical_races)}")
    
    print("Running Inference...")
    result = InferenceService.run_inference(scope.historical_races)
    
    print(f"Total Conditions Evaluated: {result['total_candidates_evaluated']}")
    print(f"Adopted Conditions (>25% win rate): {len(result['adopted_conditions'])}")
    
    print("Top 10 Conditions:")
    for cond in result['adopted_conditions'][:10]:
        print(f"  {cond['name']}")
        print(f"    - N: {cond['n_top3']} / {cond['n_all']} ({cond['rate_3in']:.2%})")
        print(f"    - Median Top3 Rate: {cond['median_rate']:.2%}")
        print(f"    - Appeared in {cond['years_appeared']} years")

if __name__ == "__main__":
    main()
