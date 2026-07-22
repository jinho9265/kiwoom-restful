import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from myAIEngine.ai_engine import AIEngine

async def main():
    ai = AIEngine()
    print("Testing get_recommendation with Gemini...")
    market_data = {
        'name': '삼성전자',
        'ticker': '005930',
        'current_price': 70000,
        'change_rate': 1.5,
        'volume': 1500000
    }
    asset_data = {'cash': 10000000, 'total_asset': 10000000}
    try:
        res = await ai.get_recommendation(market_data, asset_data)
        print("RESULT:")
        print(res)
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
