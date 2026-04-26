# telegram_bot.py

import telegram
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
import myConfig
import asyncio

class TelegramBot:
    """
    텔레그램으로 메시지를 보내는 클래스 (asyncio 호환)
    """
    def __init__(self):
        """
        봇 인스턴스를 초기화합니다.
        """
        if not myConfig.TELEGRAM_BOT_TOKEN:
            print("텔레그램 봇 토큰이 설정되지 않았습니다.")
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
        print("텔레그램 봇 준비 완료.")

    def send_message(self, message):
        """
        지정된 채팅 ID로 메시지를 보냅니다.
        :param message: 보낼 메시지 문자열
        """
        if not self.token:
            print("텔레그램 봇 토큰이 없어 메시지를 보낼 수 없습니다.")
            return

        async def _send():
            try:
                # 쉼표로 구분된 여러 채팅 ID를 리스트로 분리합니다.
                chat_ids = [cid.strip() for cid in myConfig.TELEGRAM_CHAT_ID.split(',') if cid.strip()]
                for chat_id in chat_ids:
                    await self.app.bot.send_message(chat_id=chat_id, text=message)
                print(f"텔레그램 메시지 발송 성공: {message}")
            except Exception as e:
                print(f"텔레그램 메시지 발송 실패: {e}")
                print("==================================================")
                print("      .env 파일의 토큰(TOKEN)과 채팅 ID(CHAT_ID)가      ")
                print("         올바르게 입력되었는지 다시 확인해주세요.         ")
                print("==================================================")

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
            print("텔레그램 명령어 수신 대기(Polling) 시작...")

if __name__ == '__main__':
    # --- 테스트 전 .env 파일 값 확인 ---
    print("--- .env 파일 설정 값 확인 ---")
    if myConfig.TELEGRAM_BOT_TOKEN:
        print(f"BOT TOKEN (앞 5자리): {myConfig.TELEGRAM_BOT_TOKEN[:5]}...")
    else:
        print("BOT TOKEN: 설정되지 않음")

    if myConfig.TELEGRAM_CHAT_ID:
        print(f"CHAT ID: {myConfig.TELEGRAM_CHAT_ID}")
    else:
        print("CHAT ID: 설정되지 않음")
    print("-----------------------------\n")

    # --- 간단한 테스트 ---
    print("텔레그램 봇 테스트를 시작합니다.")
    bot = TelegramBot()
    if bot.token:
        bot.send_message("이 메시지가 보인다면 텔레그램 봇 설정이 완료된 것입니다.")
        # asyncio.run()이 바로 종료되므로, 메시지 전송을 위해 잠시 대기
        # 실제 프로그램에서는 다른 작업들이 있어 필요하지 않을 수 있음
        import time
        time.sleep(1)
    else:
        print("텔레그램 봇 토큰이 없어 테스트를 진행할 수 없습니다.")
