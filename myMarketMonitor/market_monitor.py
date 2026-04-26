# market_monitor.py

import datetime
import requests
import time
import threading
import pytz
import yfinance as yf
import pandas as pd
import myConfig
from myTelegram import TelegramBot


class MarketMonitor:
    def __init__(self, telegram_bot):
        self.bot = telegram_bot
        # KST(한국 표준시) 타임존 설정
        self.kst = pytz.timezone('Asia/Seoul')

    def fetch_latest_fred_data(self, series_id):
        """FRED API를 사용하여 가장 최신 값을 반환합니다."""
        try:
            end = datetime.datetime.now()
            # GDP(분기별), UNRATE(월별) 데이터가 포함되도록 넉넉하게 1년(365일) 조회
            start = end - datetime.timedelta(days=365)

            cosd = start.strftime('%Y-%m-%d')
            coed = end.strftime('%Y-%m-%d')
            url = "https://api.stlouisfed.org/fred/series/observations"

            params = {
                'series_id': series_id,
                'api_key': myConfig.FRED_API_KEY,
                'file_type': 'json',
                'observation_start': cosd,
                'observation_end': coed,
            }

            # 타임아웃(10초) 설정 및 최대 3회 재시도
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, params=params, timeout=10)
                    break
                except requests.exceptions.RequestException as e:
                    print(f"FRED '{series_id}' 요청 타임아웃/오류 (시도 {attempt+1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        raise # 마지막 시도에도 실패하면 예외 발생
                    time.sleep(5) # 5초 대기 후 재시도

            response.raise_for_status() # 오류 발생 시 여기서 Exception 발생

            data = response.json()
            observations = data.get('observations', [])

            # 뒤에서부터 유효한(결측치가 아닌) 값을 찾음
            for obs in reversed(observations):
                if obs.get('value') != '.':
                    return float(obs.get('value'))

            return None
        except Exception as e:
            print(f"FRED '{series_id}' 데이터 조회 실패: {e}")
            return None

    def fetch_latest_yahoo_data(self, ticker):
        """Yahoo Finance에서 가장 최신의 종가 데이터를 반환합니다."""
        try:
            ticker_obj = yf.Ticker(ticker)
            df = ticker_obj.history(period="5d")
            return df['Close'].iloc[-1]
        except Exception as e:
            print(f"Yahoo Finance '{ticker}' 데이터 조회 실패: {e}")
            return None

    def get_market_indicators(self):
        indicators = {}

        # 1. VIX 지수 (^VIX)
        indicators['VIX'] = self.fetch_latest_yahoo_data("^VIX")

        # 2. 10년-2년 장단기 금리차 (T10Y2Y)
        indicators['T10Y2Y'] = self.fetch_latest_fred_data('T10Y2Y')

        # 3. 하이일드 스프레드 (BAMLH0A0HYM2)
        indicators['HY_SPREAD'] = self.fetch_latest_fred_data('BAMLH0A0HYM2')

        # 4. 기준금리 (DFF)
        indicators['DFF'] = self.fetch_latest_fred_data('DFF')

        # 5. 미국 실업률 (UNRATE)
        indicators['UNRATE'] = self.fetch_latest_fred_data('UNRATE')

        # 6. 버핏 지수 (SPX / GDP)
        spx = self.fetch_latest_yahoo_data("^GSPC")
        gdp = self.fetch_latest_fred_data('GDP') # 단위: Billions of Dollars

        if spx is not None and gdp is not None:
            # 단순히 지수/GDP 비율(%)로 변환하여 기록
            indicators['BUFFETT'] = (spx / gdp) * 100
        else:
            indicators['BUFFETT'] = None

        return indicators

    def calculate_defcon(self, indicators):
        """
        사전 설정된 임계값을 바탕으로 데프콘(DEFCON 1~5) 단계를 판정합니다.
        DEFCON 1: 최고 위험 ~ DEFCON 5: 평화 (가장 안전)
        """
        score = 0

        # 1. VIX (공포 지수) 임계값
        vix = indicators.get('VIX')
        if vix is not None:
            if vix >= 35: score += 4
            elif vix >= 25: score += 3
            elif vix >= 20: score += 2
            elif vix >= 15: score += 1

        # 2. 장단기 금리차 (T10Y2Y) 임계값
        t10y2y = indicators.get('T10Y2Y')
        if t10y2y is not None:
            if t10y2y <= -0.5: score += 4
            elif t10y2y <= -0.1: score += 3
            elif t10y2y <= 0.0: score += 2
            elif t10y2y <= 0.5: score += 1

        # 3. 하이일드 스프레드 (신용 리스크) 임계값
        hy_spread = indicators.get('HY_SPREAD')
        if hy_spread is not None:
            if hy_spread >= 6.0: score += 4
            elif hy_spread >= 5.0: score += 3
            elif hy_spread >= 4.0: score += 2
            elif hy_spread >= 3.0: score += 1

        # 4. 미국 실업률 (UNRATE) 임계값
        unrate = indicators.get('UNRATE')
        if unrate is not None:
            if unrate >= 6.0: score += 4
            elif unrate >= 5.0: score += 3
            elif unrate >= 4.0: score += 2
            elif unrate >= 3.5: score += 1

        # 5. 버핏 지수 (SPX/GDP) 임계값 (상황에 맞게 비율 조정 필요)
        buffett = indicators.get('BUFFETT')
        if buffett is not None:
            if buffett >= 22: score += 4
            elif buffett >= 20: score += 3
            elif buffett >= 18: score += 2
            elif buffett >= 16: score += 1

        # 총점 기반으로 DEFCON 단계 산정 (소수점 한 자리)
        # 기존과 동일하게 15점 이상을 DEFCON 1.0으로 두고, 0점을 5.0으로 선형 변환합니다.
        defcon = 5.0 - (score / 15.0) * 4.0
        defcon = max(1.0, min(5.0, defcon))
        return round(defcon, 1)

    def job(self):
        print(f"[{datetime.datetime.now(self.kst)}] 시장 지표 확인 및 데프콘 계산 시작...")
        indicators = self.get_market_indicators()
        defcon_level = self.calculate_defcon(indicators)

        message = f"🚨 [일일 시장 점검] 오늘의 DEFCON 레벨: {defcon_level:.1f} 🚨\n"
        message += "(1: 최고 위험 ~ 5: 평화)\n\n"

        message += "📊 주요 시장 지표:\n"
        message += f"- VIX 지수: {indicators.get('VIX', 'N/A'):.2f}\n" if indicators.get('VIX') is not None else "- VIX 지수: 데이터 없음\n"
        message += f"- 10년-2년 장단기 금리차: {indicators.get('T10Y2Y', 'N/A'):.2f}%\n" if indicators.get('T10Y2Y') is not None else "- 10년-2년 장단기 금리차: 데이터 없음\n"
        message += f"- 하이일드 스프레드: {indicators.get('HY_SPREAD', 'N/A'):.2f}%\n" if indicators.get('HY_SPREAD') is not None else "- 하이일드 스프레드: 데이터 없음\n"
        message += f"- 기준금리(DFF): {indicators.get('DFF', 'N/A'):.2f}%\n" if indicators.get('DFF') is not None else "- 기준금리(DFF): 데이터 없음\n"
        message += f"- 미국 실업률: {indicators.get('UNRATE', 'N/A'):.1f}%\n" if indicators.get('UNRATE') is not None else "- 미국 실업률: 데이터 없음\n"
        message += f"- 버핏 지수(SPX/GDP): {indicators.get('BUFFETT', 'N/A'):.2f}%\n" if indicators.get('BUFFETT') is not None else "- 버핏 지수: 데이터 없음\n"

        self.bot.send_message(message)
        print("시장 지표 메시지 전송 완료.")

    def run_scheduler(self):
        """KST 기준 30분마다 job이 실행되도록 무한 루프 스케줄러를 가동합니다."""
        print("시장 모니터링 스케줄러 시작. (매 시간 정각 실행, 00시~06시 제외)")
        last_run_hour = None
        last_run_minute = None

        while True:
            now_kst = datetime.datetime.now(self.kst)

            # 매 1분마다 실행
            if now_kst.minute == 0 and last_run_hour != now_kst.hour and not (0 <= now_kst.hour <= 6):
            #if last_run_minute != now_kst.minute:
                self.job()
                last_run_hour = now_kst.hour
                last_run_minute = now_kst.minute

            time.sleep(60)

    def start_background_thread(self):
        """메인 프로세스를 블록하지 않도록 스케줄러를 백그라운드 데몬 스레드로 실행합니다."""
        thread = threading.Thread(target=self.run_scheduler, daemon=True)
        thread.start()

if __name__ == "__main__":
    marketMonitor = MarketMonitor(TelegramBot())
    marketMonitor.job()

