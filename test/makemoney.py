import asyncio
import os
import time
import myConfig
import requests

from datetime import datetime, timedelta
from pandas import DataFrame
from dotenv import load_dotenv
from kiwoom import REAL, Bot
from kiwoom.config.trade import REQUEST_LIMIT_DAYS
from kiwoom.proc.trade import to_csv
from myMarketMonitor import MarketMonitor
from myTelegram import TelegramBot
from telegram import ReplyKeyboardMarkup

class AIEngine:
    """LLM(Gemini)을 이용한 투자 전략 분석 엔진"""
    def __init__(self, api_key, model_name):
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"

    def get_recommendation(self, market_data, asset_data):
        """시장 데이터와 자산 데이터를 바탕으로 AI에게 의견 요청"""

        if myConfig.SKIP_REQUEST_GEMINI:
            return None

        system_instruction = (
            "당신은 전문 주식 투자 분석가입니다. 제공된 한국 시장 데이터와 계좌 상태를 분석하여 "
            "매수, 매도, 또는 관망(Hold) 중 하나를 추천하고, 그 이유를 기술적/기본적 분석 관점에서 설명하세요."
        )

        user_query = f"""
        [시장 데이터]
        종목명: {market_data['name']}
        종목코드: {market_data['ticker']}
        현재가: {market_data['current_price']}원
        변동률: {market_data['change_rate']}%
        거래량: {market_data['volume']}

        [계좌 상태]
        현재 가용 예수금: {asset_data['cash']}원
        총 자산: {asset_data['total_asset']}원

        위 데이터를 바탕으로 분석 보고서를 작성해줘.
        """

        payload = {
            "contents": [{
                "parts": [{"text": user_query}]
            }],
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            }
        }

        for i in range(6):
            try:
                response = requests.post(self.api_url, json=payload, timeout=30)
                response.raise_for_status()
                result = response.json()
                return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', "분석 결과 생성 실패")
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    print(f"API 요청 한도 초과(429). {15 * (i + 1)}초 대기 후 재시도합니다...")
                    time.sleep(15 * (i + 1))
                    continue
                if i == 5:
                    return f"AI 연결 실패: {str(e)}"
                time.sleep(2 ** i)
            except Exception as e:
                if i == 5:
                    return f"AI 연결 실패: {str(e)}"
                time.sleep(2 ** i)

# CNSRLST
async def on_receive_conditional_search_list(msg: dict):
    """
    'CNSRLST' 요청에 대한 응답 콜백입니다.
    수신된 조건검색 목록을 출력합니다.
    """
    for seq, name in msg.get('data', []):
        print(f"일련번호: {seq}, 이름: {name}")

#CNSRREQ
async def on_receive_conditional_search_request(msg: dict):
    """
    'CNSRREQ' 요청에 대한 응답 콜백입니다.
    요청한 검색 조건에 부합하는 종목코드 목록을 출력합니다.
    """
    #print(msg)
    if msg.get('return_code') == 0:
        print("조건검색 결과:")
        market_data_list = []
        for item in msg.get('data', []):
            # print(f"종목명: {item.get('302')}, 종목코드: {item.get('9001')}, 현재가: {item.get('10')}, 전일대비: {item.get('11')}, 등락율: {item.get('12')}, 거래량: {item.get('13')}")

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
            # print(f"변환된 시장 데이터: {market_data}")

        return market_data_list
    else:
        print(f"조건검색 오류: {msg.get('return_msg')}")
        return None



async def main():
    telegram_bot = TelegramBot()
    ai_engine = AIEngine(myConfig.GEMINI_API_KEY, myConfig.GEMINI_MODEL_NAME)
    market_monitor = MarketMonitor(telegram_bot)
    if myConfig.ENABLE_PERIODIC_MARKET_MONITOR:
        market_monitor.start_background_thread()

    codes = None

    async def handle_search_request(msg: dict):
        # 1. 기존 콜백 함수를 호출하여 dict 리스트 반환 받기
        market_data_list = await on_receive_conditional_search_request(msg)

        # 2. 결과가 있다면 AI 엔진에 전달
        if market_data_list:
            # 임시 자산 데이터 (추후 실제 계좌 조회 데이터로 교체 필요)
            asset_data = {'cash': 10000000, 'total_asset': 10000000}

            for market_data in market_data_list[:3]:
                # 주의: get_recommendation 내부에서 requests.post(동기)를 사용하므로
                # 이벤트 루프 차단을 막기 위해 백그라운드 스레드에서 실행 (asyncio.to_thread)
                report = await asyncio.to_thread(ai_engine.get_recommendation, market_data, asset_data)
                if not report:
                    continue

                print(f"[{market_data['name']}] AI 분석 결과:\n{report}")
                telegram_bot.send_message(f"[{market_data['name']}] AI 의견:\n{report}")

                # 무료 API 요청 한도(15 RPM)를 초과하지 않도록 종목당 5초씩 대기합니다.
                await asyncio.sleep(5)


    async with Bot(REAL, myConfig.KIWOOM_APP_KEY, myConfig.KIWOOM_SECRET_KEY) as bot:
        waiting_for_ask = set()

        async def analyze_stock(update, stock_name):
            nonlocal codes
            await update.message.reply_text(f"'{stock_name}' 종목을 키움 API로 분석합니다. 잠시만 기다려주세요...")

            # Fetch codes
            if not codes:
                kospi_codes = await bot.api.stock_list("0")   # KOSPI
                kosdaq_codes = await bot.api.stock_list("10") # KOSDAQ
                codes = {'list': kospi_codes.get('list', []) + kosdaq_codes.get('list', [])}

            code = None
            for item in codes.get('list', []):
                if item.get('name') == stock_name:
                    code = item.get('code')
                    break

            # 소문자 입력 등으로 검색에 실패한 경우, 대문자로 변환하여 다시 검색
            if not code:
                stock_name_upper = stock_name.upper()
                for item in codes.get('list', []):
                    if item.get('name') == stock_name_upper:
                        code = item.get('code')
                        break

            # print(f"종목코드: {code}")
            if code:
                stock_info = await bot.api.get_stock_info(code)
                # print(f"주식기본정보요청 응답: {stock_info}")

                # 임시 자산 데이터 (추후 실제 계좌 조회 데이터로 교체 필요)
                asset_data = {'cash': 10000000, 'total_asset': 10000000}

                market_data = {
                    'name': stock_info.get('stk_nm'),
                    'ticker': stock_info.get('stk_cd'),
                    'current_price': abs(int(stock_info.get('cur_prc'))),
                    'change_rate': float(stock_info.get('flu_rt', '0')) / 1000,
                    'volume': int(stock_info.get('trde_qty'))
                }

                # 주의: get_recommendation 내부에서 requests.post(동기)를 사용하므로
                # 이벤트 루프 차단을 막기 위해 백그라운드 스레드에서 실행 (asyncio.to_thread)
                report = await asyncio.to_thread(ai_engine.get_recommendation, market_data, asset_data)
                if not report:
                    return
                print(f"[{market_data['name']}] AI 분석 결과:\n{report}")
                telegram_bot.send_message(f"[{market_data['name']}] AI 의견:\n{report}")

                # 무료 API 요청 한도(15 RPM)를 초과하지 않도록 종목당 5초씩 대기합니다.
                await asyncio.sleep(5)
            else:
                await update.message.reply_text(f"'{stock_name}' 종목을 찾을 수 없습니다.")

        # 텔레그램 명령어('/ask') 핸들러
        async def ask_command(update, context):
            if not context.args:
                waiting_for_ask.add(update.effective_user.id)
                await update.message.reply_text("분석할 종목명을 채팅창에 입력해주세요. (예: 삼성전자)")
                return

            stock_name = " ".join(context.args)
            await analyze_stock(update, stock_name)

        # 일반 텍스트 메시지 핸들러
        async def handle_text_message(update, context):
            user_id = update.effective_user.id
            if user_id in waiting_for_ask:
                waiting_for_ask.remove(user_id)
                stock_name = update.message.text.strip()
                await analyze_stock(update, stock_name)

        async def defcon_command(update, context):
            waiting_for_ask.discard(update.effective_user.id)
            await update.message.reply_text("시장 지표 확인 및 데프콘 계산을 시작합니다. 잠시만 기다려주세요...")
            await asyncio.to_thread(market_monitor.job)

        async def start_command(update, context):
            waiting_for_ask.discard(update.effective_user.id)
            # 하단에 고정되는 큼직한 버튼(키보드) 생성
            keyboard = [
                ["/defcon", "/ask"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text(
                "반갑습니다! 키움증권 AI 봇입니다.\n"
                "아래 버튼을 누르거나 좌측 하단의 '메뉴'를 이용해 명령을 내려주세요.\n"
                "*(/ask 버튼을 누른 후 이어서 종목명을 입력하시면 됩니다)*",
                reply_markup=reply_markup
            )

        telegram_bot.add_command_handler("start", start_command)
        telegram_bot.add_command_handler("ask", ask_command)
        telegram_bot.add_command_handler("defcon", defcon_command)
        telegram_bot.add_message_handler(handle_text_message)

        # 텔레그램 기본 '메뉴' 버튼에 등록
        await telegram_bot.set_menu_commands([
            ("start", "시작 및 키보드 버튼 표시"),
            ("defcon", "시장 지표 및 데프콘 계산"),
            ("ask", "종목 분석 요청 (예: /ask 삼성전자)")
        ])
        await telegram_bot.start_polling()

        # 콜백 등록
        bot.api.add_callback_on_real_data(
            real_type="CNSRLST",
            callback=on_receive_conditional_search_list
        )
        bot.api.add_callback_on_real_data(
            real_type="CNSRREQ",
            callback=handle_search_request
        )

        bot.debug(False)
        await bot.connect()

        if myConfig.ENABLE_CONDITION_SEARCH:
            await bot.api.conditional_search_list()
            # 서버가 조건검색 목록을 충분히 로드할 수 있도록 잠시 대기합니다.
            await asyncio.sleep(2)

        while True:
            if myConfig.ENABLE_CONDITION_SEARCH:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 조건검색을 요청합니다.")
                # ⚠️ 주의: '0' 대신 앞서 출력된 실제 일련번호(seq)를 입력해야 합니다. (예: '1', '2' 등)
                await bot.api.conditional_search_request('0', '0')

            # 10분(600초) 대기 후 다시 요청합니다.
            await asyncio.sleep(600)

if __name__ == "__main__":
    asyncio.run(main())
