# ai_engine.py

import myConfig
from .gemini import GeminiAIEngine
from .openai import OpenAIAIEngine
from .perplexity import PerplexityAIEngine

class AIEngine:
    """사용자가 지정한 AI Provider에 따라 적절한 AI 엔진을 호출하는 라우터 클래스"""
    def __init__(self):
        provider = getattr(myConfig, "AI_PROVIDER", "gemini").lower()
        if provider == "gemini":
            self.delegate = GeminiAIEngine()
        elif provider == "openai":
            self.delegate = OpenAIAIEngine()
        elif provider == "perplexity":
            self.delegate = PerplexityAIEngine()
        else:
            raise ValueError(f"지원하지 않는 AI Provider입니다: {provider}")

    async def get_recommendation(self, market_data, asset_data, technical_data=None, news_data=None):
        return await self.delegate.get_recommendation(market_data, asset_data, technical_data, news_data)

    async def get_defcon_report(self, indicators, defcon_level):
        return await self.delegate.get_defcon_report(indicators, defcon_level)