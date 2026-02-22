import os
import json
from typing import List, Dict, Any

class AIService:
    def __init__(self):
        # APIキーがあるかどうかでモックか本番APIかを自動判定
        # フェーズA後半の現時点ではひとまずモックを活用してE2Eを繋ぐ
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY")
        self.use_mock = not (self.openai_api_key or self.gemini_api_key)

    def evaluate_entries(self, entries_with_facts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        プログラムが計算した「事実データ（各馬のパラメータと、合致した好走条件）」をLLMへ渡し、
        深い分析（GPT-5.2 Thinking 相当）を行って最終的な評価とランキングを生成する。
        """
        if self.use_mock:
            return self._mock_evaluate(entries_with_facts)
        
        # 本番API連携用（今後実装）
        return self._call_llm_api(entries_with_facts, mode="thinking")

    def chat_with_context(self, session_context: Dict[str, Any], user_message: str) -> str:
        """
        分析結果のコンテキストを保持したまま、ユーザーからの追加質問に答える（GPT-5.2 Instant 相当）。
        """
        if self.use_mock:
            return self._mock_chat(session_context, user_message)

        # 本番API連携用（今後実装）
        return self._call_llm_api_chat(session_context, user_message, mode="instant")

    def _mock_evaluate(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        AIの分析結果（ダミー）を返す。
        入力された事実データを元に、「AIらしい」解釈の形式で構造化JSONを生成して返す。
        """
        # 入力データをスコア（プログラムが計算したダミースコア等をベースにするか、
        # あるいはここで適当にランキング付けする）でソート
        sorted_entries = sorted(entries, key=lambda x: x.get("reference_score", 0), reverse=True)
        top_horses = sorted_entries[:5]

        # ランキング結果の構築
        ranking = []
        for i, h in enumerate(top_horses):
            # プログラムが出した「事実のリスト（adopted_conditions）」の中から主要なものをテキスト化
            facts_text = []
            if "matched_conditions" in h:
                matched: List[Dict[str, Any]] = h["matched_conditions"]
                for cond in matched[:2]: # 上位2つ
                    m_rate = float(cond.get('median_rate', 0.0))
                    rate = int(m_rate * 100)
                    facts_text.append(f"「{cond.get('name', '')}」(勝率{rate}%, {cond.get('n_top3', 0)}/{cond.get('n_all', 0)}頭)")
            
            reasoning = "事実データに基づくAIの解釈が入ります。"
            if facts_text:
                reasoning = f"過去傾向から { '、'.join(facts_text) } という強い好走データに合致している点を高く評価しました。"
            
            ranking.append({
                "horse_id": h.get("horse_id", "Unknown"),
                "name": h.get("name", "Unknown"),
                "predicted_rank": i + 1,
                # LLM本番環境では、LLM自身が0-100で採点したスコアが入る
                "ai_score": float(round(100.0 - (i * 10.5), 1)),
                "reasoning": reasoning,
                "facts_used": h.get("matched_conditions", [])[:3]
            })

        top_name = ranking[0]["name"] if ranking else "該当馬なし"
        summary_text = (
            f"【AI分析レポート（モック）】\n"
            f"提供されたファクトデータ（オッズ帯ごとの勝率、斤量、過去実績など）を総合的に解釈した結果、"
            f"今年のフェブラリーSで最も期待値が高いのは「{top_name}」と判断します。\n\n"
            "※ 本解析はダミーのAI応答です。本番環境ではOpenAI/Geminiモデル（Thinking）が、"
            "与えられたファクト間の因果関係を解釈した上でスコアリングを行います。"
        )

        return {
            "ai_reasoning": summary_text,
            "rankings": ranking
        }

    def _mock_chat(self, context: Dict[str, Any], message: str) -> str:
        """会話のモック応答"""
        if "人気" in message:
            return "（モック応答）人気薄を重視する場合、提供されたデータの中で「前走OP特別」かつ「オッズ20倍〜」のゾーンに該当する馬が穴馬として浮上します。該当馬がいれば要注意です。"
        if "なぜ" in message or "理由" in message:
            return "（モック応答）AIが独自にファクトデータを解釈した結果です。具体的な因果関係（例: 東京ダ1600m特有の枠の有利不利と、該当馬の脚質のシナジー等）を算出して評価しています。"
        
        return f"（モック応答）「{message}」ですね。承知しました。本番API統合後は、これまでの分析コンテキストを引き継いだ上で高速モデル（Instant）が回答します。"

    # --- 以下、本番API組み込み用プレースホルダー ---
    def _call_llm_api(self, facts: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """本番LLM呼び出し（未実装）"""
        return {}
    
    def _call_llm_api_chat(self, context: Dict[str, Any], message: str, mode: str) -> str:
        """本番LLMチャット呼び出し（未実装）"""
        return ""
