# telegram_bot.py

import telegram
from telegram import ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import myConfig
import asyncio
import logging

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
        self.kiwoom_codes = None

    def _setup_logging(self):
        """로깅 설정을 초기화합니다."""
        # getLogger()는 이미 설정된 로거가 있다면 그 인스턴스를 반환합니다.
        self.logger = logging.getLogger(__name__)

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
        텔레그램 좌측 하단 '메뉴' 버튼에 표시될 명령어 목록을 설정합니다.
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
        self.add_message_handler(self.handle_text_message)

        # 텔레그램 기본 '메뉴' 버튼에 등록
        await self.set_menu_commands([
            ("start", "시작 및 키보드 버튼 표시"),
            ("defcon", "시장 지표 및 데프콘 계산"),
            ("ask", "종목 분석 요청 (예: /ask 삼성전자)")
        ])

    async def start_command(self, update, context):
        """
        하단에 고정되는 큼직한 버튼(키보드) 생성
        """
        self.waiting_for_ask.discard(update.effective_user.id)

        keyboard = [
            ["/defcon", "/ask"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "반갑습니다! 키움증권 AI 봇입니다.\n"
            "아래 버튼을 누르거나 좌측 하단의 '메뉴'를 이용해 명령을 내려주세요.\n"
            "*(/ask 버튼을 누른 후 이어서 종목명을 입력하시면 됩니다)*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    async def ask_command(self, update, context):
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

    async def defcon_command(self, update, context):
        self.waiting_for_ask.discard(update.effective_user.id)
        await update.message.reply_text("시장 지표 확인 및 데프콘 계산을 시작합니다. 잠시만 기다려주세요...")
        await asyncio.to_thread(self.market_monitor.job)

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
            report = await asyncio.to_thread(self.ai_engine.get_recommendation, market_data, asset_data)
            if report:
                self.logger.info(f"[{market_data['name']}] AI 분석 결과:\n{report}")
                self.send_message(f"[{market_data['name']}] AI 의견:\n{report}")
                await asyncio.sleep(5)
        else:
            await update.message.reply_text(f"'{stock_name}' 종목을 찾을 수 없습니다.")

if __name__ == '__main__':
    bot = TelegramBot()
    bot.logger.info("텔레그램 봇 테스트를 시작합니다.")
    if bot.token:
        bot.send_message("이 메시지가 보인다면 텔레그램 봇 설정이 완료된 것입니다.")
        import time
        time.sleep(1)
    else:
        bot.logger.warning("텔레그램 봇 토큰이 없어 테스트를 진행할 수 없습니다.")
