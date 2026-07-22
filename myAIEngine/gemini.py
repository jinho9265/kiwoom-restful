# myAIEngine/gemini.py

import myConfig
from .base import BaseAIEngine

class GeminiAIEngine(BaseAIEngine):
    """Gemini API 구현체"""
    def __init__(self):
        super().__init__(myConfig.GEMINI_API_KEY, myConfig.GEMINI_MODEL_NAME)

    def get_api_url(self) -> str:
        return f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def get_headers(self) -> dict:
        return {}

    def build_payload(self, system_instruction: str, user_query: str) -> dict:
        return {
            "contents": [{"parts": [{"text": user_query}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]}
        }

    def parse_response(self, response_json: dict) -> str:
        return response_json.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', "분석 결과 생성 실패")
