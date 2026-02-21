from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid

from src.api.services.analyzer import AnalyzerService
from src.api.services.inference import InferenceService
from src.api.services.validator import ValidatorService, ValidationException

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

@app.post("/api/analyze")
def analyze_race(req: AnalyzeRequest):
    try:
        # 1. Scope (RAG)
        scope = AnalyzerService.build_analysis_scope(req.race_event_id, req.target_date)
        ValidatorService.validate_scope(scope)
        
        # 2. Inference & Evaluation
        result = InferenceService.run_inference(scope.historical_races)
        adopted_conds = result["adopted_conditions"]
        ValidatorService.validate_inference_results(scope.historical_races, adopted_conds)
        
        # 3. Scoring
        scored = InferenceService.score_entries(scope.current_entries, adopted_conds)
        ValidatorService.validate_scored_results(scored)
        
        # 4. Mock AI Reasoning (LLM APIコールを隠蔽・モック化した部分)
        # フロントへ渡すため、上位人気の馬や特徴的な馬をAIが選定した「フリ」をする
        top_horse = scored[0] if scored else None
        ai_mock_reasoning = ""
        if top_horse:
            conds_str = ", ".join([f"{c['name']}({c['rate_3in']:.0%})" for c in top_horse["matched_conditions"][:2]])
            ai_mock_reasoning = f"【AI見解】\nデータ分析の結果、今年のフェブラリーSでは「{top_horse['name']}」が最も期待値が高いと評価されました。主な根拠は「{conds_str}」等、過去の好走条件との強い合致です。"

        # セッション保存
        session_id = str(uuid.uuid4())
        payload = {
            "race_event_id": req.race_event_id,
            "target_date": req.target_date,
            "horse_results": scored,
            "conditions_summary": adopted_conds[:10], # Top 10 conditions
            "ai_reasoning": ai_mock_reasoning
        }
        
        MOCK_SESSION_DB[session_id] = {
            "status": "ANALYSIS_DONE",
            "payload": payload,
            "chat_history": [{"role": "assistant", "content": ai_mock_reasoning}]
        }
        
        return {
            "session_id": session_id,
            "status": "success",
            "data": payload
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
    
    session["chat_history"].append({"role": "user", "content": req.message})
    session["chat_history"].append({"role": "assistant", "content": mock_reply})
    
    return {
        "reply": mock_reply,
        "history": session["chat_history"]
    }

# 開発用プレースホルダー：GET / で簡易ヘルスチェック
@app.get("/")
def read_root():
    return {"status": "ok", "app": "Horse Race Analyzer API (Phase A)"}
