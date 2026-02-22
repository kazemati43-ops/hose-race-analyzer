import os
import sys
import uuid
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# srcディレクトリへのパスを追加して解決
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.api.services.analyzer import AnalyzerService
from src.api.services.inference import InferenceService
from src.api.services.validator import ValidatorService, ValidationException
from src.api.services.ai_service import AIService
from src.scripts.scrape_race_card import RaceCardScraper, get_virtual_entries
from src.api.core.models import HorseBaseResult

app = FastAPI(title="Horse Race Analyzer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # 開発用のため全許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    race_event_id: str
    target_date: str

class ChatRequest(BaseModel):
    session_id: str
    message: str

# メモリ上のモックDB（本番ではDBの session テーブル等に保存）
MOCK_SESSION_DB = {}
# 出馬表データキャッシュ（1回限りのアクセス保証）
RACE_CARD_CACHE = {}

# Services initialization
analyzer_service = AnalyzerService()
inference_service = InferenceService()
validator_service = ValidatorService()
ai_service = AIService()
scraper = RaceCardScraper()

@app.post("/api/analyze")
def analyze_race(req: AnalyzeRequest):
    try:
        # 1. Scope (RAG)
        scope = AnalyzerService.build_analysis_scope(req.race_event_id, req.target_date)
        ValidatorService.validate_scope(scope)
        
        # 2. Inference & Evaluation
        inference_results = InferenceService.run_inference(scope.historical_races)
        adopted_conds = inference_results["adopted_conditions"]
        ValidatorService.validate_inference_results(scope.historical_races, adopted_conds)
        
        # 3. 本番出馬表（今年の出走馬）のスクレイピング取得（キャッシュ機構による1回のみアクセス保証）
        # リクエストされた race_event_id が未出走レースと想定
        if req.race_event_id in RACE_CARD_CACHE:
            print(f"[Analyze API] Using cached race card for {req.race_event_id}...")
            real_entries = RACE_CARD_CACHE[req.race_event_id]
        else:
            print(f"[Analyze API] Scraping real race card for {req.race_event_id}...")
            real_entries = scraper.fetch_current_race_card(req.race_event_id)
            if not real_entries:
                print("[Analyze API] Could not fetch real entries. Using virtual fallback entries.")
                real_entries = get_virtual_entries() # テスト用ダミー
            # 結果をキャッシュに保存
            RACE_CARD_CACHE[req.race_event_id] = real_entries

        # 4. スコアリングの前処理（事実ベースでの合致条件洗い出し）
        # プログラム依存のスコアリングは行わず、事実データのみを作る
        entries_with_facts = []
        for real_horse in real_entries:
            # DBなどから詳細を引いてHorseBaseResultを組み立てるのが本当だが、
            # ここでは簡単なダミーHorseBaseResultを組み立ててInferenceチェックを通す
            # (※ 簡略化：本来はscraper結果とDB履歴を結合する処理が必要)
            horse_obj = HorseBaseResult(
                race_event_id=req.race_event_id,
                horse_id=real_horse["horse_id"], 
                name=real_horse["horse_name"], 
                frame=real_horse["frame_number"], 
                carried_weight=real_horse["weight_carried"], 
                odds=real_horse["odds"],
                popularity=real_horse["popularity"]
            )
            
            matched = []
            # Inferenceが作った条件のうち、この馬に当てはまるかチェック (簡易版)
            for cond in adopted_conds:
                # eval_func 相当が必要だが現状 InferenceService は関数インスタンスを返さないため
                # 今回は事実レポートとして条件上位を便宜上当てはめるモック処理
                if len(matched) < 2: 
                   matched.append(cond)

            entries_with_facts.append({
                "horse_id": real_horse["horse_id"],
                "name": real_horse["horse_name"],
                "frame": real_horse["frame_number"],
                "odds": real_horse["odds"],
                "matched_conditions": matched
            })

        # 5. AI統合レイヤーへの引き渡し（推論と解釈・スコアリング）
        print("[Analyze API] Passing facts to AI Service...")
        ai_result = ai_service.evaluate_entries(entries_with_facts)

        # 6. APIレスポンス用の組み立て
        session_id = str(uuid.uuid4())
        ai_insights = ai_result["ai_reasoning"]
        scored_horses = ai_result["rankings"]

        session_data = {
            "race_event_id": req.race_event_id,
            "scope": {
                "history_count": len(scope.historical_races),
                "current_count": len(real_entries)
            },
            "trends": inference_results["adopted_conditions"][:5],
            "evaluations": scored_horses,
            "ai_insights": ai_insights,
            "chat_history": []
        }
        
        MOCK_SESSION_DB[session_id] = session_data
        
        return {
            "status": "success",
            "session_id": session_id,
            "data": {
                "race_info": f"フェブラリーS 分析完了 (該当条件: {len(inference_results['adopted_conditions'])}個)",
                "ai_reasoning": ai_insights,
                "horse_results": scored_horses
            }
        }
        
    except ValidationException as ve:
        raise HTTPException(status_code=400, detail=f"Validation Error: {ve.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.post("/api/chat")
def chat_followup(req: ChatRequest):
    """LLMとの対話を想定したフォローアップAPI"""
    session = MOCK_SESSION_DB.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # モックのAI応答
    mock_reply = f"【モックAI】ご質問「{req.message}」を受け付けました。現在の分析スコープ（フェーズA）では、算出されたスコアと根拠に基づく回答のみを行っています。"
    
    chat_history = session.get("chat_history", [])
    if isinstance(chat_history, list):
        chat_history.append({"role": "user", "content": req.message})
        chat_history.append({"role": "assistant", "content": mock_reply})
        session["chat_history"] = chat_history
    
    return {
        "reply": mock_reply,
        "history": session["chat_history"]
    }

# 開発用プレースホルダー：GET / で簡易ヘルスチェック
@app.get("/")
def read_root():
    return {"status": "ok", "app": "Horse Race Analyzer API (Phase A)"}
