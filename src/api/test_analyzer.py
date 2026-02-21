import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.services.analyzer import AnalyzerService

def main():
    target_race_id = "202605010811" # 仮の今年のレースID
    target_date = "2026-02-22"
    
    print("Building analysis scope...")
    # NOTE: current entries might be empty if we haven't inserted 202605010811 into race_result yet, 
    # but let's test historical first
    scope = AnalyzerService.build_analysis_scope(target_race_id, target_date)
    
    print(f"Target Race: {scope.target_race_id}")
    print(f"Historical Races Pulled: {len(scope.historical_races)}")
    for hr in scope.historical_races:
        print(f"  Year {hr.year} (Event {hr.race_event_id}): {len(hr.results)} horses")
        if len(hr.results) > 0:
            sample = hr.results[0]
            print(f"    Sample: {sample.name}, rank: {sample.rank}, odds: {sample.odds}, recent_top3: {sample.recent_top3_count}, avg_rank_bin: {sample.recent_avg_rank_bin}")

if __name__ == "__main__":
    main()
