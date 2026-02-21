import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def main():
    print("Testing /api/analyze endpoint...")
    response = client.post(
        "/api/analyze",
        json={"race_event_id": "202505010811", "target_date": "2025-02-23"}
    )
    
    if response.status_code != 200:
        print(f"Error calling /analyze: {response.text}")
        sys.exit(1)
        
    data = response.json()
    print("Status:", data["status"])
    session_id = data["session_id"]
    print("Session ID:", session_id)
    payload = data["data"]
    
    print("\n--- Payload Highlights ---")
    print(f"Number of horses scored: {len(payload['horse_results'])}")
    if len(payload['horse_results']) > 0:
        top_horse = payload['horse_results'][0]
        print(f"Top Horse: {top_horse['name']} (Score: {top_horse['score']})")
        print(f"AI Reasoning: {payload['ai_reasoning']}")
        
    print("\nTesting /api/chat endpoint...")
    chat_response = client.post(
        "/api/chat",
        json={"session_id": session_id, "message": "人気薄を重視するとどうなる？"}
    )
    
    if chat_response.status_code != 200:
        print(f"Error calling /chat: {chat_response.text}")
        sys.exit(1)
        
    chat_data = chat_response.json()
    print("AI Reply:", chat_data["reply"])
    print("Chat History Length:", len(chat_data["history"]))
    
    print("\nAPI Integration Tests Passed Successfully.")

if __name__ == "__main__":
    main()
