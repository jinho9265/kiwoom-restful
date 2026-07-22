import unittest
from unittest.mock import patch
import sys
import os

# 모듈 탐색 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import myConfig
from myAIEngine.ai_engine import AIEngine, GeminiAIEngine, OpenAIAIEngine, PerplexityAIEngine

class TestAIProviders(unittest.TestCase):
    def setUp(self):
        # 환경변수 로딩 우회 및 Mock 설정
        self.original_provider = getattr(myConfig, "AI_PROVIDER", "gemini")

    def tearDown(self):
        myConfig.AI_PROVIDER = self.original_provider

    def test_gemini_config(self):
        myConfig.GEMINI_API_KEY = "test-gemini-key"
        myConfig.GEMINI_MODEL_NAME = "gemini-3-flash-preview"
        engine = GeminiAIEngine()
        self.assertTrue(engine.get_api_url().startswith("https://generativelanguage.googleapis.com"))
        self.assertEqual(engine.get_headers(), {})
        
        payload = engine.build_payload("system instruction", "user query")
        self.assertIn("contents", payload)
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "user query")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "system instruction")

    def test_openai_config(self):
        myConfig.OPENAI_API_KEY = "test-openai-key"
        myConfig.OPENAI_MODEL_NAME = "gpt-4o-mini"
        engine = OpenAIAIEngine()
        self.assertEqual(engine.get_api_url(), "https://api.openai.com/v1/chat/completions")
        self.assertEqual(engine.get_headers()["Authorization"], "Bearer test-openai-key")
        
        payload = engine.build_payload("system instruction", "user query")
        self.assertEqual(payload["model"], "gpt-4o-mini")
        self.assertEqual(payload["messages"][0]["content"], "system instruction")
        self.assertEqual(payload["messages"][1]["content"], "user query")

    def test_perplexity_config(self):
        myConfig.PERPLEXITY_API_KEY = "test-perplexity-key"
        myConfig.PERPLEXITY_MODEL_NAME = "llama-3.1-sonar-large-128k-online"
        engine = PerplexityAIEngine()
        self.assertEqual(engine.get_api_url(), "https://api.perplexity.ai/chat/completions")
        self.assertEqual(engine.get_headers()["Authorization"], "Bearer test-perplexity-key")
        
        payload = engine.build_payload("system instruction", "user query")
        self.assertEqual(payload["model"], "llama-3.1-sonar-large-128k-online")
        self.assertEqual(payload["messages"][0]["content"], "system instruction")
        self.assertEqual(payload["messages"][1]["content"], "user query")

    def test_factory_router(self):
        myConfig.GEMINI_API_KEY = "test-gemini-key"
        myConfig.GEMINI_MODEL_NAME = "gemini-3-flash-preview"
        myConfig.OPENAI_API_KEY = "test-openai-key"
        myConfig.OPENAI_MODEL_NAME = "gpt-4o-mini"
        myConfig.PERPLEXITY_API_KEY = "test-perplexity-key"
        myConfig.PERPLEXITY_MODEL_NAME = "llama-3.1-sonar-large-128k-online"

        with patch('myConfig.AI_PROVIDER', 'gemini'):
            engine = AIEngine()
            self.assertIsInstance(engine.delegate, GeminiAIEngine)

        with patch('myConfig.AI_PROVIDER', 'openai'):
            engine = AIEngine()
            self.assertIsInstance(engine.delegate, OpenAIAIEngine)

        with patch('myConfig.AI_PROVIDER', 'perplexity'):
            engine = AIEngine()
            self.assertIsInstance(engine.delegate, PerplexityAIEngine)

if __name__ == "__main__":
    unittest.main()
