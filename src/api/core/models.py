from pydantic import BaseModel
from typing import List, Optional

class HorseBaseResult(BaseModel):
    # レース結果としての基本情報
    race_event_id: str
    horse_id: str
    name: str
    rank: Optional[int]
    frame: Optional[int]
    odds: Optional[float]
    popularity: Optional[int]
    carried_weight: Optional[float]
    horse_weight: Optional[int]
    last_3f: Optional[int]
    
    # 馬属性
    sex: Optional[str]
    birth_year: Optional[int]
    sire: Optional[str]
    dam: Optional[str]
    damsire: Optional[str]

    # このレース時の設定年齢
    age_at_race: Optional[int]
    
    # 派生特徴量（前処理後）
    horse_weight_bin: Optional[str]
    last_3f_bin: Optional[str]

    # 直近5走特徴量
    recent_highest_grade: Optional[str]
    recent_top3_count: int = 0
    recent_avg_rank_bin: Optional[str]
    has_dirt_1600_exp: bool = False
    has_tokyo_exp: bool = False

class RaceData(BaseModel):
    race_event_id: str
    year: int
    results: List[HorseBaseResult]

class AnalysisScope(BaseModel):
    target_race_id: str
    historical_races: List[RaceData]
    current_entries: List[HorseBaseResult]
