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

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")

# API URL 설정 (실전투자)
API_URL = "https://api.kiwoom.com"

# --- Validation ---
# 환경 변수가 제대로 로드되었는지 확인
required_vars = [
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "KIWOOM_APP_KEY",
    "KIWOOM_SECRET_KEY",
    "FRED_API_KEY",
    "GEMINI_API_KEY",
    "GEMINI_MODEL_NAME"
]
if not all(globals().get(var) for var in required_vars):
    raise ValueError(f"설정 파일(.env)에 필요한 모든 값이 입력되었는지 확인해주세요. (필요한 값: {', '.join(required_vars)})")

print("환경설정 로딩 완료.")
