# telegram_bot.py

import telegram
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler
import myConfig
import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
import os
from myBacktest import Backtester


class TelegramBot:
    """
    텔레그램으로 메시지를 보내는 클래스 (asyncio 호환)
    """
    def __init__(self):
        """
        봇 인스턴스를 초기화합니다.
        """
        self._setup_logging()
        if not myConfig.TELEGRAM_BOT_TOKEN:
            self.logger.warning("텔레그램 봇 토큰이 설정되지 않았습니다.")
            self.token = None
            self.app = None
            self.loop = None
            return

        self.token = myConfig.TELEGRAM_BOT_TOKEN
        self.app = ApplicationBuilder().token(self.token).build()
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = None
        self.logger.info("텔레그램 봇 준비 완료.")

        self.waiting_for_ask = set()
        self.waiting_for_backtest = set()
        self.kiwoom_codes = None

    def _setup_logging(self):
        """로깅 설정을 초기화합니다."""
        # getLogger()는 이미 설정된 로거가 있다면 그 인스턴스를 반환합니다.
        self.logger = logging.getLogger(__name__)

    def send_photo(self, photo_path, caption="", parse_mode="Markdown"):
        """
        지정된 채팅 ID로 사진을 보냅니다.
        :param photo_path: 보낼 사진의 로컬 파일 경로
        :param caption: 사진 설명 텍스트
        :param parse_mode: 텍스트 포맷 옵션 (Markdown, HTML 등)
        """
        if not self.token:
            self.logger.warning("텔레그램 봇 토큰이 없어 사진을 보낼 수 없습니다.")
            return

        async def _send():
            try:
                # 쉼표로 구분된 여러 채팅 ID를 리스트로 분리합니다.
                chat_ids = [cid.strip() for cid in myConfig.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
                for chat_id in chat_ids:
                    try:
                        with open(photo_path, 'rb') as photo:
                            await self.app.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode=parse_mode)
                    except Exception as parse_err:
                        self.logger.warning(f"마크다운 파싱 실패로 일반 텍스트 포맷으로 재전송합니다. 오류: {parse_err}")
                        with open(photo_path, 'rb') as photo:
                            await self.app.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption)
                self.logger.info(f"텔레그램 사진 발송 성공 (경로: {photo_path})")
            except Exception as e:
                self.logger.error(f"텔레그램 사진 발송 실패: {e}")

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is not None:
            current_loop.create_task(_send())
        elif getattr(self, 'loop', None) and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_send(), self.loop)
        else:
            asyncio.run(_send())

    def send_message(self, message, parse_mode="Markdown"):
        """
        지정된 채팅 ID로 메시지를 보냅니다.
        :param message: 보낼 메시지 문자열
        :param parse_mode: 텍스트 포맷 옵션 (Markdown, HTML 등)
        """
        if not self.token:
            self.logger.warning("텔레그램 봇 토큰이 없어 메시지를 보낼 수 없습니다.")
            return

        async def _send():
            try:
                # 쉼표로 구분된 여러 채팅 ID를 리스트로 분리합니다.
                chat_ids = [cid.strip() for cid in myConfig.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
                for chat_id in chat_ids:
                    try:
                        await self.app.bot.send_message(chat_id=chat_id, text=message, parse_mode=parse_mode)
                    except Exception as parse_err:
                        self.logger.warning(f"마크다운 파싱 실패로 일반 텍스트 포맷으로 재전송합니다. 오류: {parse_err}")
                        await self.app.bot.send_message(chat_id=chat_id, text=message)
                self.logger.info(f"텔레그램 메시지 발송 성공 (포맷: {parse_mode})")
            except Exception as e:
                self.logger.error(f"텔레그램 메시지 발송 실패: {e}")
                self.logger.error("==================================================")
                self.logger.error("      .env 파일의 토큰(TOKEN)과 채팅 ID(CHAT_ID)가      ")
                self.logger.error("         올바르게 입력되었는지 다시 확인해주세요.         ")
                self.logger.error("==================================================")

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is not None:
            # 동일한 이벤트 루프 내에서 실행 중인 경우
            current_loop.create_task(_send())
        elif getattr(self, 'loop', None) and self.loop.is_running():
            # 백그라운드 스레드에서 호출되었으나, 메인 이벤트 루프가 존재하는 경우
            asyncio.run_coroutine_threadsafe(_send(), self.loop)
        else:
            # 실행 중인 이벤트 루프가 전혀 없는 경우 (단독 실행 등)
            asyncio.run(_send())

    async def set_menu_commands(self, commands: list):
        """
        텔레그램 채팅창 입력칸의 메뉴(또는 '/') 버튼에 표시될 명령어 목록을 설정합니다.
        commands: [("명령어", "설명"), ...] 형태의 리스트
        """
        if self.app:
            bot_commands = [telegram.BotCommand(cmd, desc) for cmd, desc in commands]
            await self.app.bot.set_my_commands(bot_commands)
            #print("텔레그램 메뉴 버튼 설정 완료.")

    def add_command_handler(self, command: str, handler):
        """
        명령어(예: /ask) 수신 시 실행할 비동기 핸들러를 등록합니다.
        """
        if self.app:
            self.app.add_handler(CommandHandler(command, handler))

    def add_message_handler(self, handler):
        """
        명령어가 아닌 일반 텍스트 메시지 수신 시 실행할 비동기 핸들러를 등록합니다.
        """
        if self.app:
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler))

    async def start_polling(self):
        """
        비동기 이벤트 루프 내에서 텔레그램 메시지 수신(Polling)을 백그라운드로 시작합니다.
        """
        if self.app:
            await self.app.initialize()
            await self.app.start()
            await self.app.updater.start_polling()
            self.logger.info("텔레그램 명령어 수신 대기(Polling) 시작...")

    async def setup_handlers(self, kiwoom_bot, ai_engine, market_monitor):
        """
        외부에서 전달받은 인스턴스들을 연결하고, 명령어 핸들러를 등록합니다.
        """
        self.kiwoom_bot = kiwoom_bot
        self.ai_engine = ai_engine
        self.market_monitor = market_monitor

        self.add_command_handler("start", self.start_command)
        self.add_command_handler("ask", self.ask_command)
        self.add_command_handler("defcon", self.defcon_command)
        self.add_command_handler("balance", self.balance_command)
        self.add_command_handler("portfolio", self.balance_command)
        self.add_command_handler("backtest", self.backtest_command)
        self.app.add_handler(CallbackQueryHandler(self.handle_callback_query))
        self.add_message_handler(self.handle_text_message)

        # 텔레그램 기본 '메뉴' 버튼에 등록
        await self.set_menu_commands([
            ("start", "시작 및 키보드 버튼 표시"),
            ("defcon", "시장 지표 및 데프콘 계산"),
            ("ask", "종목 분석 요청 (예: /ask 삼성전자)"),
            ("backtest", "종목 백테스팅 (예: /backtest 삼성전자)"),
            ("balance", "실시간 자산 및 포트폴리오 조회")
        ])

    async def start_command(self, update, context):
        """
        하단에 고정되는 큼직한 버튼(키보드) 생성
        """
        self.waiting_for_ask.discard(update.effective_user.id)
        self.waiting_for_backtest.discard(update.effective_user.id)

        keyboard = [
            ["/defcon", "/ask", "/balance", "/backtest"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "반갑습니다! 키움증권 AI 봇입니다.\n"
            "아래 버튼을 누르거나 채팅창 입력칸의 '/' (또는 '메뉴') 버튼을 눌러 명령을 내려주세요.\n"
            "*(/ask 또는 /backtest 버튼을 누른 후 이어서 종목명을 입력하시면 됩니다)*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def ask_command(self, update, context):
        self.waiting_for_backtest.discard(update.effective_user.id)
        if not context.args:
            self.waiting_for_ask.add(update.effective_user.id)
            await update.message.reply_text("분석할 종목명을 채팅창에 입력해주세요. (예: 삼성전자)")
            return

        stock_name = " ".join(context.args)
        await self.analyze_stock(update, stock_name)

    async def handle_text_message(self, update, context):
        user_id = update.effective_user.id
        if user_id in self.waiting_for_ask:
            self.waiting_for_ask.remove(user_id)
            stock_name = update.message.text.strip()
            await self.analyze_stock(update, stock_name)
        elif user_id in self.waiting_for_backtest:
            self.waiting_for_backtest.remove(user_id)
            stock_name = update.message.text.strip()
            await self.prompt_strategy_selection(update, stock_name)

    async def backtest_command(self, update, context):
        self.waiting_for_ask.discard(update.effective_user.id)
        if not context.args:
            self.waiting_for_backtest.add(update.effective_user.id)
            await update.message.reply_text("백테스팅할 종목명을 채팅창에 입력해주세요. (예: 삼성전자)")
            return

        stock_name = " ".join(context.args)
        await self.prompt_strategy_selection(update, stock_name)

    async def prompt_strategy_selection(self, update, stock_name):
        # 1. 종목 코드로 변환
        if not self.kiwoom_codes:
            kospi_codes = await self.kiwoom_bot.api.stock_list("0")   # KOSPI
            kosdaq_codes = await self.kiwoom_bot.api.stock_list("10") # KOSDAQ
            self.kiwoom_codes = {'list': kospi_codes.get('list', []) + kosdaq_codes.get('list', [])}

        code = next((item.get('code') for item in self.kiwoom_codes.get('list', []) if item.get('name') == stock_name), None)
        if not code:
            code = next((item.get('code') for item in self.kiwoom_codes.get('list', []) if item.get('name') == stock_name.upper()), None)

        if not code:
            await update.message.reply_text(f"'{stock_name}' 종목을 찾을 수 없습니다.")
            return

        # 2. 인라인 키보드 생성 (설명 포함)
        keyboard = [
            [InlineKeyboardButton("SMA 교차 (5일/20일선 골든&데드크로스)", callback_data=f"bt:{code}:SMA")],
            [InlineKeyboardButton("RSI 역추세 (RSI 30 이하 매수 / 70 이상 매도)", callback_data=f"bt:{code}:RSI")],
            [InlineKeyboardButton("볼린저 밴드 (하한선 매수 / 상한선 매도)", callback_data=f"bt:{code}:BB")],
            [InlineKeyboardButton("MACD 모멘텀 (MACD & 시그널선 교차)", callback_data=f"bt:{code}:MACD")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"📊 *{stock_name} ({code})* 백테스팅\n"
            f"시뮬레이션할 전략을 선택해주세요:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def handle_callback_query(self, update, context):
        query = update.callback_query
        await query.answer()

        data = query.data
        if data.startswith("bt:"):
            parts = data.split(":")
            if len(parts) == 3:
                _, code, strategy = parts
                
                # 종목명 조회
                stock_name = code
                if self.kiwoom_codes:
                    stock_name = next((item.get('name') for item in self.kiwoom_codes.get('list', []) if item.get('code') == code), code)
                
                # 진행 상태 표시
                await query.edit_message_text(text=f"🔄 {stock_name} ({code}) 종목에 대해 {strategy} 전략 백테스팅을 실행합니다. 잠시만 기다려주세요...")
                
                # 비동기 백테스트 구동
                await self.run_backtest_and_send(query, code, stock_name, strategy)

    async def run_backtest_and_send(self, query, code, stock_name, strategy):
        # 1. 일봉 캔들 데이터 조회 (최근 1년 = 365일)
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
        try:
            df = await self.kiwoom_bot.candle(code, period="day", ctype="stock", start=start_date)
            if df is None or df.empty or len(df) < 20:
                await query.edit_message_text(text=f"❌ '{stock_name}' 종목의 최근 일봉 데이터가 부족하거나 가져오지 못했습니다. (가져온 데이터 개수: {len(df) if df is not None else 0})")
                return

            # 2. 백테스터 실행
            tester = Backtester(df, initial_capital=10000000.0)
            
            if strategy == 'SMA':
                res = tester.run_sma(5, 20)
                strategy_desc = "이동평균선 교차 (5일/20일)"
            elif strategy == 'RSI':
                res = tester.run_rsi(14, 30, 70)
                strategy_desc = "RSI 과매수/과매도 (30/70)"
            elif strategy == 'BB':
                res = tester.run_bb(20, 2.0)
                strategy_desc = "볼린저 밴드 (20일, 2std)"
            elif strategy == 'MACD':
                res = tester.run_macd(12, 26, 9)
                strategy_desc = "MACD 모멘텀 교차"
            else:
                await query.edit_message_text(text=f"❌ 지원되지 않는 전략입니다: {strategy}")
                return

            # 3. 차트 생성
            chart_path = tester.plot_result(strategy, stock_name)

            # 4. 성과 지표 보고서 포맷 작성
            sign = "+" if res['total_return'] >= 0 else ""
            report_msg = (
                f"📊 *[{stock_name} ({code}) {strategy_desc} 백테스트 결과]*\n"
                f"- *분석 기간*: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')} ({len(df)} 영업일)\n"
                f"- *초기 자금*: {tester.initial_capital:,.0f}원\n"
                f"- *최종 자산*: {res['final_value']:,.0f}원\n"
                f"- *누적 수익률*: *{sign}{res['total_return']:.2f}%*\n"
                f"- *연평균 복리 수익률(CAGR)*: *{sign}{res['cagr']:.2f}%*\n"
                f"- *최대 낙폭(MDD)*: *{res['mdd']:.2f}%*\n"
                f"- *총 거래 횟수*: {res['num_trades']}회\n"
                f"- *거래 승률*: {res['win_rate']:.2f}%\n"
            )

            # 메시지 변경 완료 안내
            await query.edit_message_text(text=f"✅ {stock_name} ({code}) 백테스팅 완료! 결과 차트와 요약 리포트를 전송합니다.")
            
            # 이미지와 텍스트 전송
            if chart_path and os.path.exists(chart_path):
                self.send_photo(chart_path, caption=f"*{stock_name} ({code}) - {strategy_desc} 수익률 분석 차트*")
                await asyncio.sleep(2)
            self.send_message(report_msg)

        except Exception as e:
            self.logger.error(f"백테스트 실행 중 오류 발생: {e}", exc_info=True)
            await query.edit_message_text(text=f"❌ 백테스팅 중 오류가 발생했습니다: {str(e)}")

    async def defcon_command(self, update, context):
        self.waiting_for_ask.discard(update.effective_user.id)
        await update.message.reply_text("시장 지표 확인 및 데프콘 계산을 시작합니다. 잠시만 기다려주세요...")
        await self.market_monitor.job()

    async def analyze_stock(self, update, stock_name):
        await update.message.reply_text(f"'{stock_name}' 종목을 키움 API로 분석합니다. 잠시만 기다려주세요...")

        if not self.kiwoom_codes:
            kospi_codes = await self.kiwoom_bot.api.stock_list("0")   # KOSPI
            kosdaq_codes = await self.kiwoom_bot.api.stock_list("10") # KOSDAQ
            self.kiwoom_codes = {'list': kospi_codes.get('list', []) + kosdaq_codes.get('list', [])}

        code = next((item.get('code') for item in self.kiwoom_codes.get('list', []) if item.get('name') == stock_name), None)
        # 소문자 입력 등으로 검색에 실패한 경우, 대문자로 변환하여 다시 검색
        if not code:
            code = next((item.get('code') for item in self.kiwoom_codes.get('list', []) if item.get('name') == stock_name.upper()), None)

        if code:
            stock_info = await self.kiwoom_bot.api.get_stock_info(code)
            # TODO: 임시 자산 데이터 (추후 실제 계좌 조회 데이터로 교체 필요)
            asset_data = {'cash': 10000000, 'total_asset': 10000000}
            market_data = {
                'name': stock_info.get('stk_nm'),
                'ticker': stock_info.get('stk_cd'),
                'current_price': abs(int(stock_info.get('cur_prc'))),
                'change_rate': float(stock_info.get('flu_rt', '0')),
                'volume': int(stock_info.get('trde_qty'))
            }

            # 일봉 캔들 데이터 조회 및 기술적 지표 계산 (최근 180일 데이터를 확보하여 앞부분 지표 손실 보완)
            start_date = (datetime.now() - timedelta(days=180)).strftime("%Y%m%d")
            technical_str = ""
            photo_path = None # 이미지 전송 대기를 위해 경로 변수 선언
            try:
                # self.kiwoom_bot.candle은 DataFrame을 반환함
                df = await self.kiwoom_bot.candle(code, period="day", ctype="stock", start=start_date)
                if df is not None and len(df) >= 5:
                    # 5일/20일/60일 이동평균선
                    df['SMA5'] = df['종가'].rolling(window=5).mean()
                    if len(df) >= 20:
                        df['SMA20'] = df['종가'].rolling(window=20).mean()
                    if len(df) >= 60:
                        df['SMA60'] = df['종가'].rolling(window=60).mean()

                    # 볼린저 밴드 (20일, 표준편차 2배)
                    if len(df) >= 20:
                        std20 = df['종가'].rolling(window=20).std()
                        df['BB_Mid'] = df['SMA20']
                        df['BB_Upper'] = df['BB_Mid'] + (std20 * 2)
                        df['BB_Lower'] = df['BB_Mid'] - (std20 * 2)

                    # MACD (12, 26, 9)
                    if len(df) >= 26:
                        ema12 = df['종가'].ewm(span=12, adjust=False).mean()
                        ema26 = df['종가'].ewm(span=26, adjust=False).mean()
                        df['MACD'] = ema12 - ema26
                        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

                    # RSI (14)
                    if len(df) >= 14:
                        delta = df['종가'].diff()
                        gain = delta.clip(lower=0)
                        loss = -delta.clip(upper=0)
                        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
                        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
                        rs = avg_gain / avg_loss.replace(0, 1e-9)
                        df['RSI'] = 100 - (100 / (1 + rs))

                    # 현재 기준 기술 지표 수치 요약
                    close = df['종가'].iloc[-1]
                    sma5_val = df['SMA5'].iloc[-1] if 'SMA5' in df and pd.notna(df['SMA5'].iloc[-1]) else float('nan')
                    sma20_val = df['SMA20'].iloc[-1] if 'SMA20' in df and pd.notna(df['SMA20'].iloc[-1]) else float('nan')
                    sma60_val = df['SMA60'].iloc[-1] if 'SMA60' in df and pd.notna(df['SMA60'].iloc[-1]) else float('nan')

                    disparity_5 = (close / sma5_val) * 100 if pd.notna(sma5_val) else float('nan')
                    disparity_20 = (close / sma20_val) * 100 if pd.notna(sma20_val) else float('nan')
                    disparity_60 = (close / sma60_val) * 100 if pd.notna(sma60_val) else float('nan')

                    bb_upper = df['BB_Upper'].iloc[-1] if 'BB_Upper' in df and pd.notna(df['BB_Upper'].iloc[-1]) else float('nan')
                    bb_lower = df['BB_Lower'].iloc[-1] if 'BB_Lower' in df and pd.notna(df['BB_Lower'].iloc[-1]) else float('nan')
                    bb_percent = ((close - bb_lower) / (bb_upper - bb_lower)) * 100 if pd.notna(bb_upper) and pd.notna(bb_lower) and (bb_upper - bb_lower) != 0 else float('nan')

                    rsi_val = df['RSI'].iloc[-1] if 'RSI' in df and pd.notna(df['RSI'].iloc[-1]) else float('nan')
                    macd_val = df['MACD'].iloc[-1] if 'MACD' in df and pd.notna(df['MACD'].iloc[-1]) else float('nan')
                    macd_sig = df['MACD_Signal'].iloc[-1] if 'MACD_Signal' in df and pd.notna(df['MACD_Signal'].iloc[-1]) else float('nan')
                    macd_hist = df['MACD_Hist'].iloc[-1] if 'MACD_Hist' in df and pd.notna(df['MACD_Hist'].iloc[-1]) else float('nan')

                    def format_num(val, fmt="{:,.1f}"):
                        import math
                        return "N/A" if pd.isna(val) or math.isnan(val) else fmt.format(val)

                    summary = (
                        f"[최근 기술적 지표 요약]\n"
                        f"- 종가: {close:,.0f}원\n"
                        f"- 이동평균선(SMA): 5일선 {format_num(sma5_val)}원 | 20일선 {format_num(sma20_val)}원 | 60일선 {format_num(sma60_val)}원\n"
                        f"- 이격도(Disparity): 5일선 {format_num(disparity_5, '{:.2f}%')} | 20일선 {format_num(disparity_20, '{:.2f}%')} | 60일선 {format_num(disparity_60, '{:.2f}%')}\n"
                        f"- 볼린저 밴드: 하한선 {format_num(bb_lower)}원 | 상한선 {format_num(bb_upper)}원 (현재가 위치 %B: {format_num(bb_percent, '{:.2f}%')})\n"
                        f"- RSI(14): {format_num(rsi_val, '{:.2f}')} (30이하 과매도, 70이상 과매수)\n"
                        f"- MACD: {format_num(macd_val, '{:.2f}')} | Signal: {format_num(macd_sig, '{:.2f}')} | Hist: {format_num(macd_hist, '{:.2f}')}\n"
                    )

                    # 최근 60영업일 데이터 필터링
                    df_recent = df.tail(60)
                    cols_to_show = [c for c in ['종가', 'SMA5', 'SMA20', 'SMA60', 'RSI', 'MACD', 'BB_Lower', 'BB_Upper'] if c in df]
                    df_subset = df_recent[cols_to_show].round(1)

                    table_str = df_subset.to_string()
                    technical_str = f"{summary}\n[최근 60영업일 일자별 추세 데이터]\n{table_str}"

                    # 캔들 차트 이미지 생성 및 전송 (최근 1개월 주가 추세)
                    try:
                        import mplfinance as mpf
                        import os
                        
                        # 최근 1개월(약 30일치 데이터) 준비
                        df_chart = df.tail(30).copy()
                        df_chart.rename(columns={
                            '시가': 'Open',
                            '고가': 'High',
                            '저가': 'Low',
                            '종가': 'Close',
                            '거래량': 'Volume'
                        }, inplace=True)
                        
                        os.makedirs("tmp_charts", exist_ok=True)
                        photo_path = f"tmp_charts/{code}_candle.png"
                        
                        # 한국 주식 차트 색상 (상승: 빨강, 하락: 파랑)
                        mc = mpf.make_marketcolors(up='red', down='blue', inherit=True)
                        s = mpf.make_mpf_style(marketcolors=mc, gridstyle='--', y_on_right=True)
                        
                        # 차트 그리기 및 파일 저장
                        mpf.plot(
                            df_chart, 
                            type='candle', 
                            style=s, 
                            volume=True, 
                            savefig=photo_path, 
                            title=f"\n{code} 1-Month Trend"
                        )
                    except Exception as chart_err:
                        self.logger.error(f"캔들 차트 이미지 생성 중 오류 발생: {chart_err}", exc_info=True)
                        photo_path = None
                else:
                    self.logger.warning(f"'{stock_name}' 종목의 기술 분석 데이터가 충분하지 않습니다. (가져온 데이터 개수: {len(df) if df is not None else 0})")
            except Exception as e:
                self.logger.error(f"Candle 데이터 조회/지표 계산 중 오류 발생: {e}", exc_info=True)

            # 뉴스 데이터 비동기 수집 (네이버 API 대안 구글 뉴스 RSS 활용)
            news_str = ""
            try:
                news_titles = await self.fetch_google_news(market_data['name'])
                if news_titles:
                    news_str = "\n".join(f"- {title}" for title in news_titles)
            except Exception as news_err:
                self.logger.error(f"뉴스 수집 오류: {news_err}")

            report = await self.ai_engine.get_recommendation(market_data, asset_data, technical_data=technical_str, news_data=news_str)
            if report:
                self.logger.info(f"[{market_data['name']}] AI 분석 결과:\n{report}")
                # AI 답변이 준비되었을 때, 캔들 차트와 설명 텍스트를 연달아 전송
                if photo_path and os.path.exists(photo_path):
                    self.send_photo(photo_path, caption=f"*{market_data['name']} ({code}) 최근 1개월 캔들 차트 추세*")
                    await asyncio.sleep(3) # 발송 대기
                self.send_message(f"[{market_data['name']}] AI 의견:\n{report}")
                await asyncio.sleep(5)
        else:
            await update.message.reply_text(f"'{stock_name}' 종목을 찾을 수 없습니다.")

    async def fetch_google_news(self, stock_name: str) -> list[str]:
        """구글 뉴스 RSS를 통해 해당 종목 관련 최신 뉴스 헤드라인 5개를 비동기로 수집합니다."""
        import urllib.parse
        import xml.etree.ElementTree as ET
        import aiohttp
        
        query = urllib.parse.quote(stock_name)
        url = f"https://news.google.com/rss/search?q={query}&hl=ko&gl=KR&ceid=KR:ko"
        
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, timeout=5) as response:
                    if response.status == 200:
                        xml_data = await response.text()
                        root = ET.fromstring(xml_data)
                        titles = []
                        seen_titles = set()
                        for item in root.findall(".//item"):
                            title = item.find("title").text
                            if " - " in title:
                                title = title.rsplit(" - ", 1)[0]
                            title_stripped = title.strip()
                            if title_stripped not in seen_titles:
                                seen_titles.add(title_stripped)
                                titles.append(title_stripped)
                            if len(titles) >= 5:
                                break
                        return titles
        except Exception as e:
            self.logger.error(f"구글 뉴스 RSS 수집 실패 ({stock_name}): {e}")
        return []

    async def balance_command(self, update, context):
        """실시간 계좌 잔고 및 포트폴리오를 조회하고 파이 차트로 전송합니다."""
        await update.message.reply_text("💼 실시간 계좌 정보 및 보유 종목 잔고를 조회 중입니다. 잠시만 기다려주세요...")
        
        # 1. API를 통해 데이터 조회
        deposit_data = None
        portfolio_data = None
        try:
            if self.kiwoom_bot and self.kiwoom_bot.api:
                deposit_data = await self.kiwoom_bot.api.get_deposit_info()
                portfolio_data = await self.kiwoom_bot.api.get_balance_portfolio()
        except Exception as e:
            self.logger.error(f"실시간 잔고 조회 중 오류: {e}")
            
        # 2. 파싱 및 폴백(Fallback) 처리
        is_mock = False
        holdings = []
        cash = 0
        total_buy = 0
        total_eval = 0
        total_pl = 0
        total_rt = 0.0

        # API 데이터를 정상 수신한 경우 파싱 시도
        if deposit_data and deposit_data.get("return_code") == 0 and portfolio_data and portfolio_data.get("return_code") == 0:
            try:
                dep_body = deposit_data.get("body", {})
                cash = int(dep_body.get("dstd_dps", dep_body.get("d2_dps", 0)))
                
                port_body = portfolio_data.get("body", {})
                raw_holdings = port_body.get("acnt_eval_bal_array", [])
                
                for item in raw_holdings:
                    stk_cd = item.get("stk_cd", "")
                    stk_nm = item.get("stk_nm", "")
                    qty = int(item.get("hold_qty", item.get("qty", 0)))
                    buy_uv = int(item.get("buy_uv", item.get("buy_dprc", 0)))
                    cur_prc = int(item.get("cur_prc", item.get("cur_dprc", 0)))
                    eval_pl = int(item.get("eval_pl", item.get("eval_pft_loss_amt", 0)))
                    eval_pl_rt = float(item.get("eval_pl_rt", item.get("eval_pft_loss_rt", 0.0)))
                    
                    if qty > 0:
                        holdings.append({
                            "code": stk_cd,
                            "name": stk_nm,
                            "qty": qty,
                            "buy_price": buy_uv,
                            "current_price": cur_prc,
                            "eval_pl": eval_pl,
                            "eval_pl_rt": eval_pl_rt,
                            "eval_amt": qty * cur_prc
                        })
                
                total_buy = sum(h["qty"] * h["buy_price"] for h in holdings)
                total_eval = sum(h["eval_amt"] for h in holdings)
                total_pl = total_eval - total_buy
                total_rt = (total_pl / total_buy * 100) if total_buy > 0 else 0.0
                
            except Exception as parse_err:
                self.logger.error(f"잔고 데이터 파싱 중 에러: {parse_err}. 가상 데이터로 폴백합니다.")
                is_mock = True

        # 보유 종목이 아예 없거나 파싱 오류난 경우 폴백
        if not holdings or is_mock:
            is_mock = True
            cash = 3500000 # 350만원 예수금
            holdings = [
                {"code": "005930", "name": "삼성전자", "qty": 50, "buy_price": 72000, "current_price": 74500, "eval_pl": 125000, "eval_pl_rt": 3.47, "eval_amt": 50 * 74500},
                {"code": "000660", "name": "SK하이닉스", "qty": 15, "buy_price": 180000, "current_price": 185000, "eval_pl": 75000, "eval_pl_rt": 2.78, "eval_amt": 15 * 185000},
                {"code": "005380", "name": "현대차", "qty": 10, "buy_price": 250000, "current_price": 242500, "eval_pl": -75000, "eval_pl_rt": -3.00, "eval_amt": 10 * 242500}
            ]
            total_buy = sum(h["qty"] * h["buy_price"] for h in holdings)
            total_eval = sum(h["eval_amt"] for h in holdings)
            total_pl = total_eval - total_buy
            total_rt = (total_pl / total_buy * 100) if total_buy > 0 else 0.0

        # 3. Matplotlib를 사용해 다크 테마 포트폴리오 파이 차트 생성
        chart_path = self.render_portfolio_pie(cash, holdings)
        
        # 4. 텔레그램 전송
        mock_tag = " (⚠️ 모의 데모 잔고)" if is_mock else ""
        summary_msg = (
            f"💼 *[실시간 계좌 잔고 및 포트폴리오 요약]{mock_tag}*\n"
            f"- *총 자산*: {total_eval + cash:,.0f}원\n"
            f"- *예수금 (현금)*: {cash:,.0f}원\n"
            f"- *총 매입 금액*: {total_buy:,.0f}원\n"
            f"- *총 평가 금액*: {total_eval:,.0f}원\n"
            f"- *총 평가 손익*: *{total_pl:+,.0f}원*\n"
            f"- *총 수익률*: *{total_rt:+.2f}%*\n\n"
            f"📈 *보유 종목 현황*\n"
        )
        
        for h in holdings:
            sign = "+" if h["eval_pl"] >= 0 else ""
            summary_msg += (
                f"• *{h['name']}* ({h['code']}): {h['qty']}주\n"
                f"   └ 매입: {h['buy_price']:,.0f}원 | 현재: {h['current_price']:,.0f}원\n"
                f"   └ 평가금: {h['eval_amt']:,.0f}원 | 손익: {sign}{h['eval_pl']:,.0f}원 ({sign}{h['eval_pl_rt']:.2f}%)\n"
            )

        if chart_path and os.path.exists(chart_path):
            self.send_photo(chart_path, caption=f"*💼 실시간 포트폴리오 자산 배분 비중*{mock_tag}")
            await asyncio.sleep(3)
        self.send_message(summary_msg)

    def render_portfolio_pie(self, cash, holdings):
        """보유 현황을 Pie Chart 이미지로 렌더링하고 경로를 리턴합니다."""
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import matplotlib.font_manager as fm
        import os
        
        try:
            # 다크 테마 및 한글 폰트 설정
            plt.style.use('dark_background')
            
            font_list = ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'sans-serif']
            font_set = False
            for font in font_list:
                if any(f.name == font for f in fm.fontManager.ttflist):
                    plt.rcParams['font.family'] = font
                    font_set = True
                    break
            if not font_set:
                plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['axes.unicode_minus'] = False # 마이너스 기호 깨짐 방지

            # 데이터 취합
            labels = ["CASH"]
            sizes = [cash]
            
            for h in holdings:
                labels.append(h["name"])
                sizes.append(h["eval_amt"])
            fig, ax = plt.subplots(figsize=(6, 5))
            
            # 은은하고 세련된 색상 조합
            colors = ['#4f5b66', '#268bd2', '#859900', '#dc322f', '#b58900', '#cb4b16', '#6c71c4']
            if len(sizes) > len(colors):
                colors = colors * (len(sizes) // len(colors) + 1)
            colors = colors[:len(sizes)]
            
            # 차트 그리기
            wedges, texts, autotexts = ax.pie(
                sizes, 
                labels=labels, 
                autopct='%1.1f%%', 
                startangle=90, 
                colors=colors,
                textprops=dict(color="w"),
                wedgeprops=dict(width=0.4, edgecolor='black', linewidth=1.5) # 도넛 모양
            )
            
            plt.setp(autotexts, size=9, weight="bold")
            plt.setp(texts, size=10)
            
            # 중앙 텍스트 (총자산 표시)
            total_assets = cash + sum(h["eval_amt"] for h in holdings)
            ax.text(0, 0, f"Total\n{total_assets/10000:,.0f}만원", ha='center', va='center', fontsize=11, color='w', weight='bold')
            
            plt.title("Portfolio Asset Allocation", color='white', fontsize=13, pad=15, weight='bold')
            plt.tight_layout()
            
            os.makedirs("tmp_charts", exist_ok=True)
            chart_path = "tmp_charts/portfolio_pie.png"
            plt.savefig(chart_path, dpi=150, transparent=False)
            plt.close()
            return chart_path
        except Exception as e:
            self.logger.error(f"포트폴리오 Pie Chart 렌더링 실패: {e}", exc_info=True)
            return None

if __name__ == '__main__':
    bot = TelegramBot()
    bot.logger.info("텔레그램 봇 테스트를 시작합니다.")
    if bot.token:
        bot.send_message("이 메시지가 보인다면 텔레그램 봇 설정이 완료된 것입니다.")
        import time
        time.sleep(1)
    else:
        bot.logger.warning("텔레그램 봇 토큰이 없어 테스트를 진행할 수 없습니다.")
