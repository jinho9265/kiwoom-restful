# market_monitor.py

import asyncio
import datetime
import requests
import time
import threading
import pytz
import yfinance as yf
import myConfig
from myTelegram import TelegramBot

class MarketMonitor:
    def __init__(self, telegram_bot, ai_engine=None):
        self.bot = telegram_bot
        self.ai_engine = ai_engine
        # KST(한국 표준시) 타임존 설정
        self.kst = pytz.timezone('Asia/Seoul')

        if myConfig.ENABLE_PERIODIC_MARKET_MONITOR:
            self.start_background_thread()

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

        # 7. 원/달러 환율 (USDKRW=X)
        indicators['USDKRW'] = self.fetch_latest_yahoo_data("USDKRW=X")

        # 8. KOSPI 지수 (^KS11)
        indicators['KOSPI'] = self.fetch_latest_yahoo_data("^KS11")

        # 9. 나스닥 지수 (^IXIC)
        indicators['NASDAQ'] = self.fetch_latest_yahoo_data("^IXIC")

        # 10. WTI 유가 (CL=F)
        indicators['WTI'] = self.fetch_latest_yahoo_data("CL=F")

        return indicators

    def calculate_defcon(self, indicators):
        """
        사전 설정된 임계값을 바탕으로 데프콘(DEFCON 1~5) 단계를 판정합니다.
        DEFCON 1: 최고 위험 ~ DEFCON 5: 평화 (가장 안전)
        """

        # TODO: data를 AI Engine에 입력해서 DEFCON 단계 판정하도록 변경
        """
        당신은 글로벌 경제 지표를 실시간으로 브리핑하는 ‘전술 통제소 수석 참모’다.
        항상 군대식의 정중하고 단호한 보고 톤을 유지하라.

        가장 중요한 규칙:
        1. 경제 지표, 시장 가격, 뉴스, 정책 발언, 옵션 지표처럼 시간이 변하는 정보는 절대 추정하거나 기억에 의존하지 말고, 반드시 실시간 웹 검색 또는 최신 공개 데이터로 확인한 뒤 보고하라.
        2. 최신 데이터가 불충분하면 불확실성을 명시하고, 임의 숫자를 채워 넣지 마라.
        3. 보고는 항상 “보수적 해석”을 기본으로 하라.

        보고 목적:
        - 글로벌 매크로와 대한민국 방어 지표를 종합하여
        - 현재 시장의 위험 상태를 DEFCON 1.0 ~ 5.0으로 판정하고

        DEFCON 규칙:
        - DEFCON 1.0 = 최고 위기 / 타격 기회
        - DEFCON 5.0 = 평시 / 안정
        - 숫자가 1.0에 가까울수록 패닉이며, 달러 환전 및 원화 대출상환에 유리한 상황이다.
        - 환율, VIX, DXY, 유가, CDS가 급등하면 DEFCON을 낮춰라.
        - 특히 VIX가 폭등했는데 DEFCON을 높게 주는 실수를 하지 마라.
        - 숫자만 안정적이어도 SKEW, SPX put/call ratio, CDS, 지정학 리스크가 높으면 DEFCON을 과도하게 높이지 마라.

        미국 서머타임 규칙:
        항상 먼저 미국 서머타임 적용 여부를 확인하라.
        한국시간 기준 미장 브리핑 타점은 아래를 따른다.
        - 서머타임 O: 22:35(개장), 05:10(마감)
        - 서머타임 X: 23:35(개장), 06:10(마감)

        아시아 브리핑 타점:
        - 09:05 국장 개장
        - 10:35 중화권
        - 14:30 오후장
        - 15:40 국장 마감
        - 20:10 NXT 마감

        주말 규칙:
        - 토요일 미장 마감 브리핑 이후 일요일까지는 브리핑 중지 상태로 간주하라.
        - 주말에는 “휴장 상태”를 명확히 구분하고, 마지막 확정치와 실시간 거래 자산(예: 비트코인)만 분리해서 설명하라.

        시장 구분 규칙:
        - KOSPI 본장은 15:30~익일 09:00 사이에는 실시간 본장값 대신 가장 최근 종가로 처리하고, 야간선물을 실시간 데이터로 표기하라.
        - 미국 본장은 한국 주간 시간대에는 가장 최근 종가로 처리하고, 야간선물을 실시간 데이터로 표기하라.
        - 현물, 선물, CFD/추적값, 지연시세, 전일 종가를 반드시 구분해서 설명하라.

        데이터 수집 규칙:
        가능하면 현재(T)부터 과거 7개 시점(T~T-7)을 역순 정리하라.
        T-7는 정확히 24시간 전 동시간대를 의미한다.
        단, 공개 데이터가 부족하면 현재값 중심으로 보고하고, 과거 칸은 억지로 채우지 마라.

        표 기본 형식:
        [지표 (24H 증감폭) | 개별 DEFCON | T | T-1 | T-2 | T-3 | T-4 | T-5 | T-6 | T-7]

        증감 화살표/보합 기준:
        - 환율: 5원
        - DXY: 0.5pt
        - 유가: $2
        - BTC: $1k
        - VIX: 2pt
        - CDS: 2bp
        - KOSPI: 30pt
        - S&P500 본장/선물: 30pt
        - 나스닥100 본장/선물: 100pt
        기준 미만이면 보합(-) 처리하라.

        항상 포함해야 할 핵심 지표:

        [글로벌 매크로]
        - 달러인덱스 DXY
        - WTI
        - 브렌트
        - 비트코인
        - VIX
        - 미국 장단기금리차
        - 미국 하이일드 OAS 또는 하이일드 스프레드
        - 버핏 지수
        - S&P 500 본장
        - S&P 500 선물
        - 나스닥 본장
        - 나스닥100 선물
        - SKEW Index
        - SPX Put/Call Ratio

        [대한민국 방어 지표]
        - 원/달러 환율
        - 한국 5Y CDS
        - KOSPI 본장
        - KOSPI 야간선물 또는 대체 가능한 야간 지표
        - 한국 국채금리(가능시 2Y, 5Y, 10Y 중 핵심)
        - 필요시 한미 금리차

        SKEW / SPX Put-Call Ratio 해석 원칙:
        - SKEW Index = 꼬리위험 경보 지표
        - SPX Put/Call Ratio = 기관 방어 포지셔닝 지표
        - SKEW 고점권은 “겉지수 대비 아래꼬리 위험이 크다”는 뜻으로 해석하라.
        - SPX P/C가 2.0 근처이거나 2.0 이상이 자주 반복되면 강한 경계 신호로 해석하라.
        - SKEW 단독으로 하락 확정 신호를 내리지 말고, SPX P/C, VIX, 유가, CDS, 환율과 함께 판단하라.
        - “숫자상 안정 + 구조상 경계” 같은 혼합 판정을 허용하라.

        옵션만기일(OpEx) 해석 규칙:
        - 옵션만기일 이후 금요일까지는 수급상 견조할 수 있음을 감안하라.
        - 그 다음 월요일~화요일의 방향성을 특히 중요하게 보라.
        - 필요시 종합판단에 “OpEx 후 방향성 확인 구간”이라는 문구를 넣어라.

        가짜 안정기 감시 원칙:
        다음 중 여러 개가 동시에 나타나면 “가짜 안정기 가능성”을 경고하라.
        - 환율은 내려도 CDS가 안 내려감
        - 지수는 오르는데 SKEW가 높음
        - SPX P/C가 낮아지지 않고 자주 튐
        - 유가가 빠르게 재상승
        - 크레딧이 완전히 풀리지 않음
        - 좋은 뉴스에는 조금 오르고, 나쁜 뉴스에는 크게 흔들림
        - 월요일에 방향성이 다시 아래로 꺾임

        브리핑 형식:
        항상 아래 구조를 유지하라.

        ### 🚨 [종합 DEFCON STATUS: X.X / 한 줄 판정]
        - 현재 위험 상태를 한 문장으로 요약
        - 대출 상환/환전 타점 형성 여부 결론 포함

        ### 🌍 [1부: 글로벌 매크로 환경]
        - 핵심 지표 표
        - 2~5문단 해석
        - “현재 시장이 패닉인지, 불안한 안정기인지, 완화 국면인지”를 명확히 말하라

        ### 🇰🇷 [2부: 대한민국 방어 지표]
        - 원/달러, 한국 5Y CDS, KOSPI, 국채금리 등 표
        - 한국 관점에서 원화 방어 상태를 설명
        - 한국이 유가·달러·외국인 자금흐름에 얼마나 취약한지 연결해서 설명

        ### 💡 [지표별 직관적 해석 (전술 가이드)]
        - 초보자도 체감할 수 있게 작성
        - 단순 설명보다 행동 해석 위주로 작성

        ### 최종 명령
        - 지금 해야 할 행동/하지 말아야 할 행동을 2~4줄로 정리
        - “지금은 달러를 급히 털 구간이 아니다”, “몸을 가볍게 유지”, “다음 경계 격상 조건은 ...” 같은 실전 문장을 활용하라

        문체 규칙:
        - 간결하고 단호하게 써라.
        - 군 보고체 느낌을 유지하라.
        - 과장된 감탄, 이모지 남용, 가벼운 농담을 금지한다.
        - 문단은 짧고 밀도 있게 써라.

        출처 규칙:
        - 모든 시간민감 정보는 출처를 병기하라.
        - 가능하면 공식기관, 거래소, 대형 통신사, 신뢰도 높은 시장 데이터 제공처를 우선하라.
        - 수치가 출처마다 조금 다르면, 차이를 짧게 설명하고 더 보수적으로 해석하라.
        - 로딩에 시간이 걸리는 경우 3회 재검색하여 수치를 제공하라.
        - CFD/추적값은 “공식 현물 종가와 구분해서 봐야 한다”고 명시하라.

        특별 주의:
        - 숫자만 안정적이라고 해서 곧바로 “평시 복귀”라고 하지 마라.
        - 사용자가 “가짜 안정기 같다”, “폭발 전 에너지 응축 같다”는 문제의식을 가지고 있음을 감안해, 옵션 구조와 신용·환율·유가를 함께 보라.
        - 미국 AI 버블, 지정학 리스크, 오일쇼크, 원화 급락 가능성을 항상 염두에 두고 해석하라.
        - 하지만 근거 없는 공포 조성은 하지 말고, 숫자와 구조를 분리해서 판단하라.

        이 지시를 항상 유지하며, 사용자가 "브리핑" 또는 “실시간 데이터 기준으로 브리핑 해주세요”라고 말하면 즉시 위 형식으로 최신 브리핑을 제공하라.
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

    def generate_dashboard_chart(self, indicators, defcon_level):
        """FRED & Yahoo Finance 지표를 기반으로 다크테마 매크로 레이더 차트를 생성합니다."""
        try:
            import matplotlib
            matplotlib.use('Agg') # GUI 없이 파일 저장용 백엔드 설정
            import matplotlib.pyplot as plt
            import numpy as np
            import os

            labels = ['VIX', 'T10Y2Y', 'HY-SPREAD', 'UNRATE', 'BUFFETT']
            num_vars = len(labels)

            # 지표 데이터 추출
            vix = indicators.get('VIX')
            t10y2y = indicators.get('T10Y2Y')
            hy_spread = indicators.get('HY_SPREAD')
            unrate = indicators.get('UNRATE')
            buffett = indicators.get('BUFFETT')

            # 0~100 리스크 지수화 (높을수록 위기, 실제 DEFCON 점수 임계값에 맞춰 동기화)
            vix_val = max(0.0, min(100.0, ((vix - 10.0) / 30.0) * 100.0)) if vix is not None else 50.0
            t10y2y_val = max(0.0, min(100.0, ((0.5 - t10y2y) / 1.0) * 100.0)) if t10y2y is not None else 50.0
            hy_val = max(0.0, min(100.0, ((hy_spread - 3.0) / 3.0) * 100.0)) if hy_spread is not None else 50.0
            unrate_val = max(0.0, min(100.0, ((unrate - 3.5) / 2.5) * 100.0)) if unrate is not None else 50.0
            buffett_val = max(0.0, min(100.0, ((buffett - 16.0) / 6.0) * 100.0)) if buffett is not None else 50.0

            stats = [vix_val, t10y2y_val, hy_val, unrate_val, buffett_val]

            # 레이더 차트의 원형 닫기를 위한 종점 처리
            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
            stats += stats[:1]
            angles += angles[:1]

            # 피규어 생성 및 어두운 스타일 지정
            fig, ax = plt.subplots(figsize=(5.5, 5.5), subplot_kw=dict(polar=True))
            fig.patch.set_facecolor('#1c1c1e') # 다크 테마 배경
            ax.set_facecolor('#2c2c2e')
            ax.spines['polar'].set_color('#48484a')

            # 그리드선 설정
            ax.xaxis.grid(True, color='#48484a', linestyle='--')
            ax.yaxis.grid(True, color='#3a3a3c', linestyle=':')

            # 각도 보정 및 시계방향 진행
            ax.set_theta_offset(np.pi / 2)
            ax.set_theta_direction(-1)

            # 레이블 및 틱 설정
            plt.xticks(angles[:-1], labels, color='#ffffff', size=10, fontweight='bold')
            ax.set_rlabel_position(0)
            plt.yticks([25, 50, 75, 100], ["25", "50", "75", "100"], color="#8e8e93", size=8)
            plt.ylim(0, 100)

            # 데프콘 단계별 색상 지정
            if defcon_level <= 2.0:
                color = '#ff3b30' # 위험 (Red)
            elif defcon_level <= 3.5:
                color = '#ffcc00' # 주의 (Yellow)
            else:
                color = '#34c759' # 안정 (Green)

            # 그리기 및 면 채우기
            ax.plot(angles, stats, color=color, linewidth=2, linestyle='solid')
            ax.fill(angles, stats, color=color, alpha=0.25)

            # 중심에 DEFCON 등급 원형 배지 표시
            ax.text(0, 0, f"DEFCON\n{defcon_level:.1f}", color='#ffffff', size=14, 
                    fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle="circle,pad=0.4", fc="#1c1c1e", ec=color, lw=2.5))

            os.makedirs("tmp_charts", exist_ok=True)
            dashboard_path = "tmp_charts/defcon_dashboard.png"
            plt.title("Macro Risk Radar Dashboard", color='#ffffff', size=12, fontweight='bold', pad=15)
            plt.savefig(dashboard_path, facecolor=fig.get_facecolor(), bbox_inches='tight', dpi=150)
            plt.close()
            return dashboard_path
        except Exception as e:
            print(f"데프콘 대시보드 차트 생성 중 오류: {e}")
            return None

    async def job(self):
        print(f"[{datetime.datetime.now(self.kst)}] 시장 지표 확인 및 데프콘 계산 시작...")
        indicators = self.get_market_indicators()
        defcon_level = self.calculate_defcon(indicators)

        # 데프콘 대시보드 시각화 이미지 생성
        dashboard_path = self.generate_dashboard_chart(indicators, defcon_level)

        if self.ai_engine:
            print("AIEngine을 통한 AI 매크로 브리핑(DEFCON) 보고서 생성을 시작합니다...")
            ai_report = await self.ai_engine.get_defcon_report(indicators, defcon_level)
            if ai_report:
                if dashboard_path:
                    self.bot.send_photo(dashboard_path, caption=f"*🚨 [종합 DEFCON STATUS: {defcon_level:.1f}] 일일 시장 점검 대시보드*")
                    await asyncio.sleep(3)
                self.bot.send_message(ai_report)
                await asyncio.sleep(3)
                print("AI 매크로 브리핑 메시지 전송 완료.")
                return

        if dashboard_path:
            self.bot.send_photo(dashboard_path, caption=f"*🚨 [종합 DEFCON STATUS: {defcon_level:.1f}] 일일 시장 점검 대시보드*")
            await asyncio.sleep(3)

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
        await asyncio.sleep(3)
        print("시장 지표 메시지 전송 완료.")

    def run_scheduler(self):
        """KST 기준 30분마다 job이 실행되도록 무한 루프 스케줄러를 가동합니다."""
        print("시장 모니터링 스케줄러 시작. (매 시간 정각 실행, 00시~06시 제외)")
        last_run_hour = None
        last_run_minute = None

        while True:
            now_kst = datetime.datetime.now(self.kst)

            if now_kst.minute == 0 and last_run_hour != now_kst.hour and not (0 <= now_kst.hour <= 6):
            #if last_run_minute != now_kst.minute:
                # Call async job synchronously using asyncio.run
                asyncio.run(self.job())
                last_run_hour = now_kst.hour
                last_run_minute = now_kst.minute

            time.sleep(60)

    def start_background_thread(self):
        """메인 프로세스를 블록하지 않도록 스케줄러를 백그라운드 데몬 스레드로 실행합니다."""
        thread = threading.Thread(target=self.run_scheduler, daemon=True)
        thread.start()

if __name__ == "__main__":
    try:
        from myAIEngine.ai_engine import AIEngine
        ai = AIEngine()
    except Exception as e:
        print(f"AIEngine 로드 실패(기본 텍스트 리포트 사용): {e}")
        ai = None
    marketMonitor = MarketMonitor(TelegramBot(), ai)
    asyncio.run(marketMonitor.job())

