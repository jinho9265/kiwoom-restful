# config.py
import os
from dotenv import load_dotenv

# Option list
ENABLE_PERIODIC_MARKET_MONITOR = False
ENABLE_CONDITION_SEARCH = False
SEND_TELEGRAM_GROUP_MESSAGE = True
SKIP_REQUEST_GEMINI = False

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# --- API & Bot Keys ---
# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_GROUP_CHAT_ID") if SEND_TELEGRAM_GROUP_MESSAGE else os.getenv("TELEGRAM_SINGLE_CHAT_ID")

# Kiwoom REST API
KIWOOM_APP_KEY = os.getenv("KIWOOM_APP_KEY")
KIWOOM_SECRET_KEY = os.getenv("KIWOOM_SECRET_KEY")

# FRED API
FRED_API_KEY = os.getenv("FRED_API_KEY")

# AI Provider 설정 (gemini, openai, perplexity)
AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini").lower()

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

# Perplexity API
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")
PERPLEXITY_MODEL_NAME = os.getenv("PERPLEXITY_MODEL_NAME", "llama-3.1-sonar-large-128k-online")

# API URL 설정 (실전투자)
API_URL = "https://api.kiwoom.com"

# --- Validation ---
# 환경 변수가 제대로 로드되었는지 확인
required_vars = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "KIWOOM_APP_KEY",
    "KIWOOM_SECRET_KEY",
    "FRED_API_KEY"
]

if AI_PROVIDER == "gemini":
    required_vars.extend(["GEMINI_API_KEY", "GEMINI_MODEL_NAME"])
elif AI_PROVIDER == "openai":
    required_vars.extend(["OPENAI_API_KEY", "OPENAI_MODEL_NAME"])
elif AI_PROVIDER == "perplexity":
    required_vars.extend(["PERPLEXITY_API_KEY", "PERPLEXITY_MODEL_NAME"])
else:
    raise ValueError(f"지원하지 않는 AI Provider입니다: {AI_PROVIDER}")

if not all(globals().get(var) for var in required_vars):
    missing_vars = [var for var in required_vars if not globals().get(var)]
    raise ValueError(f"설정 파일(.env)에 필요한 모든 값이 입력되었는지 확인해주세요. (누락된 값: {', '.join(missing_vars)})")

print("환경설정 로딩 완료.")
