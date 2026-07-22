# myAIEngine/perplexity.py

import myConfig
from .base import BaseAIEngine

class PerplexityAIEngine(BaseAIEngine):
    """Perplexity API 구현체"""
    def __init__(self):
        super().__init__(myConfig.PERPLEXITY_API_KEY, myConfig.PERPLEXITY_MODEL_NAME)

    def get_api_url(self) -> str:
        return "https://api.perplexity.ai/chat/completions"

    def get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def build_payload(self, system_instruction: str, user_query: str) -> dict:
        return {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_query}
            ]
        }

    def parse_response(self, response_json: dict) -> str:
        return response_json.get('choices', [{}])[0].get('message', {}).get('content', "분석 결과 생성 실패")
