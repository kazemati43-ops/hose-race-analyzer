import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.api.services.analyzer import AnalyzerService
from src.api.services.inference import InferenceService
from src.api.services.validator import ValidatorService, ValidationException

def main():
    target_race_id = "202505010811"  
    target_date = "2025-02-23"     
    
    print("Testing Validation Pipeline...")
    
    try:
        print("1. Validating Scope...")
        scope = AnalyzerService.build_analysis_scope(target_race_id, target_date)
        ValidatorService.validate_scope(scope)
        print(" -> Scope Validation Passed!")
        
        print("2. Validating Inference Results...")
        result = InferenceService.run_inference(scope.historical_races)
        adopted_conds = result['adopted_conditions']
        # 意図的に不正なデータを混入させて例外が発生するかは、モックテスト等でやるべきだが
        # まずは正常系がPassするかを確認する
        ValidatorService.validate_inference_results(scope.historical_races, adopted_conds)
        print(" -> Inference Validation Passed!")
        
        print("3. Validating Scored Results...")
        scored = InferenceService.score_entries(scope.current_entries, adopted_conds)
        ValidatorService.validate_scored_results(scored)
        print(" -> Scoring Validation Passed!")
        
        print("\nAll Guardrail Checks Passed Successfully.")
        
    except ValidationException as e:
        print(f"\n[Validation Failed] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[Unexpected Error] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
