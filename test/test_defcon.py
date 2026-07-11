import asyncio
import logging
import sys
import os

# Windows 콘솔 cp949 인코딩 문제 해결
sys.stdout.reconfigure(encoding='utf-8')

# 현재 폴더 및 상위 폴더를 path에 추가하여 모듈을 임포트할 수 있게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myMarketMonitor import MarketMonitor
from myAIEngine import AIEngine
from myTelegram import TelegramBot

logging.basicConfig(level=logging.INFO)

async def test_defcon_report():
    print("시장 데이터 수집 중...")
    telegram_bot = TelegramBot()
    ai_engine = AIEngine()
    market_monitor = MarketMonitor(telegram_bot, ai_engine)
    
    indicators = market_monitor.get_market_indicators()
    defcon_level = market_monitor.calculate_defcon(indicators)
    
    print(f"계산된 룰베이스 데프콘 레벨: {defcon_level}")
    print("차트 이미지 생성 중...")
    chart_path = market_monitor.generate_dashboard_chart(indicators, defcon_level)
    print(f"차트 이미지 저장 경로: {chart_path}")
    print("AI 보고서 생성 요청 중...")
    
    report = await ai_engine.get_defcon_report(indicators, defcon_level)
    print("\n================ AI REPORT ================")
    print(report)
    print("===========================================")

if __name__ == "__main__":
    asyncio.run(test_defcon_report())
