# makemoney.py

import asyncio
import myConfig
import logging
import functools

from datetime import datetime
from kiwoom import REAL, Bot
from myMarketMonitor import MarketMonitor
from myTelegram import TelegramBot
from myAIEngine import AIEngine

logger = logging.getLogger(__name__)

# CNSRLST
async def on_receive_conditional_search_list(msg: dict):
    """
    'CNSRLST' 요청에 대한 응답 콜백입니다.
    수신된 조건검색 목록을 출력합니다.
    """
    for seq, name in msg.get('data', []): # type: ignore
        logger.info(f"조건검색식 수신 - 일련번호: {seq}, 이름: {name}")

async def handle_search_request(msg: dict, ai_engine, telegram_bot):
    """
    'CNSRREQ' 요청에 대한 응답 콜백입니다.
    요청한 검색 조건에 부합하는 종목을 파악하고 AI 엔진에 분석을 요청합니다.
    """
    if msg.get('return_code') != 0:
        logger.error(f"조건검색 오류: {msg.get('return_msg')}")
        return

    market_data_list = []
    for item in msg.get('data', []):
        # 키움 API FID 매핑: 302(종목명), 9001(종목코드), 10(현재가), 12(등락율), 13(누적거래량)
        # 주의: 현재가(10)에는 부호(+, -)가 포함되어 있을 수 있어 abs() 처리가 필요합니다.
        market_data = {
            'name': item.get('302'),
            'ticker': item.get('9001'),
            'current_price': abs(int(item.get('10'))),
            'change_rate': float(item.get('12', '0')) / 1000,
            'volume': int(item.get('13'))
        }
        market_data_list.append(market_data)

    # 2. 결과가 있다면 AI 엔진에 전달
    if market_data_list:
        # TODO: 임시 자산 데이터 (추후 실제 계좌 조회 데이터로 교체 필요)
        asset_data = {'cash': 10000000, 'total_asset': 10000000}

        # TODO: Query할 종목 개수 선정
        for market_data in market_data_list[:3]:
            # 주의: get_recommendation 내부에서 requests.post(동기)를 사용하므로
            # 이벤트 루프 차단을 막기 위해 백그라운드 스레드에서 실행 (asyncio.to_thread)
            report = await asyncio.to_thread(ai_engine.get_recommendation, market_data, asset_data)
            if not report:
                continue

            logger.info(f"[{market_data['name']}] AI 분석 결과:\n{report}")
            telegram_bot.send_message(f"[{market_data['name']}] AI 의견:\n{report}")

            # 무료 API 요청 한도(15 RPM)를 초과하지 않도록 종목당 5초씩 대기합니다.
            await asyncio.sleep(5)


async def main():
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.FileHandler('makemoney.log', encoding='utf-8'), logging.StreamHandler()]
    )

    telegram_bot = TelegramBot()
    ai_engine = AIEngine()
    market_monitor = MarketMonitor(telegram_bot)

    async with Bot(REAL, myConfig.KIWOOM_APP_KEY, myConfig.KIWOOM_SECRET_KEY) as bot:
        await telegram_bot.setup_handlers(bot, ai_engine, market_monitor)
        await telegram_bot.start_polling()

        # 콜백 등록
        bot.api.add_callback_on_real_data(
            real_type="CNSRLST",
            callback=on_receive_conditional_search_list
        )
        bot.api.add_callback_on_real_data(
            real_type="CNSRREQ",
            callback=functools.partial(handle_search_request, ai_engine=ai_engine, telegram_bot=telegram_bot)
        )

        bot.debug(False)
        await bot.connect()

        if myConfig.ENABLE_CONDITION_SEARCH:
            await bot.api.conditional_search_list()
            # 서버가 조건검색 목록을 충분히 로드할 수 있도록 잠시 대기합니다.
            await asyncio.sleep(2)

        while True:
            if myConfig.ENABLE_CONDITION_SEARCH:
                logger.info(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 조건검색을 요청합니다.")
                # ⚠️ 주의: '0' 대신 앞서 출력된 실제 일련번호(seq)를 입력해야 합니다. (예: '1', '2' 등)
                await bot.api.conditional_search_request('0', '0')

            # 10분(600초) 대기 후 다시 요청합니다.
            await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
