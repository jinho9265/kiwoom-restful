# myAIEngine/base.py

import asyncio
import aiohttp
import myConfig
from abc import ABC, abstractmethod

class BaseAIEngine(ABC):
    """AI 엔진의 공통 기반 추상 클래스"""
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def get_api_url(self) -> str:
        """API 호출 URL 반환"""
        pass

    @abstractmethod
    def get_headers(self) -> dict:
        """API 호출 헤더 반환"""
        pass

    @abstractmethod
    def build_payload(self, system_instruction: str, user_query: str) -> dict:
        """API 호출 페이로드(바디) 구성"""
        pass

    @abstractmethod
    def parse_response(self, response_json: dict) -> str:
        """API 응답 JSON에서 텍스트 결과 추출"""
        pass

    async def _request_with_retry(self, system_instruction: str, user_query: str) -> str:
        """지수 백오프 및 429 대응을 포함한 공통 HTTP 요청 처리"""
        api_url = self.get_api_url()
        headers = self.get_headers()
        payload = self.build_payload(system_instruction, user_query)

        for i in range(6):
            try:
                connector = aiohttp.TCPConnector(resolver=aiohttp.ThreadedResolver())
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.post(api_url, json=payload, headers=headers, timeout=30) as response:
                        response.raise_for_status()
                        result = await response.json()
                        return self.parse_response(result)
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    msg = f"API 요청 한도 초과(429). {15 * (i + 1)}초 대기 후 재시도합니다..."
                    print(msg)
                    try:
                        from myTelegram.telegram_bot import get_instance
                        tg_bot = get_instance()
                        if tg_bot:
                            tg_bot.send_message(f"⚠️ {msg}")
                    except Exception as tg_err:
                        print(f"텔레그램 메시지 전송 실패: {tg_err}")
                    await asyncio.sleep(15 * (i + 1))
                    continue
                if i == 5:
                    return f"AI 연결 실패: {str(e)}"
                await asyncio.sleep(2 ** i)
            except Exception as e:
                if i == 5:
                    return f"AI 연결 실패: {str(e)}"
                await asyncio.sleep(2 ** i)

    async def get_recommendation(self, market_data, asset_data, technical_data=None, news_data=None):
        """시장 데이터와 자산 데이터를 바탕으로 AI에게 의견 요청"""
        if myConfig.SKIP_REQUEST_GEMINI:
            return None

        system_instruction = (
            "당신은 전문 주식 투자 분석가입니다. 제공된 한국 시장 데이터, 최근 기술 지표 요약 및 60영업일 간의 상세 추세 데이터(이동평균선 5/20/60, RSI, MACD, 볼린저 밴드 등), 최근 뉴스 헤드라인 데이터, 그리고 계좌 상태를 종합적으로 분석하십시오.\n"
            "단순 당일 등락에만 치우치지 말고 시장 흐름과 최근 추세를 충분히 반영하여 매수, 매도, 또는 관망(Hold) 중 하나를 추천하고, 그 이유를 기술적 분석 관점에서 상세히 설명하십시오.\n\n"
            "특히 [최근 뉴스 헤드라인 데이터]가 제공되는 경우, 뉴스의 시장 긍정/부정적 영향을 분석하여 **종합 감성 점수 (Sentiment Score, -100에서 +100 사이)**를 산출하십시오.\n"
            "- -100은 극도로 비관적(Bearish)\n"
            "- +100은 극도로 낙관적(Bullish)\n"
            "- 0은 완전 중립(Neutral)\n"
            "보고서 최상단에 산출된 감성 점수와 핵심 감성 요약 한 줄을 기재하고 시작하십시오.\n\n"
            "★ [텔레그램 마크다운 호환성 핵심 규칙 (절대 준수)] ★\n"
            "1. *해시태그(#, ##, ###) 절대 사용 금지*: 텔레그램 Legacy Markdown은 `#` 기호를 지원하지 않으므로 raw 텍스트로 보입니다. "
            "절대 `###` 같은 기호를 제목에 쓰지 마십시오. 대신 모든 제목은 별표 1개씩으로 감싸 볼드체로 강조하십시오. (예: `*🚨 [삼성전자 기술적 분석 보고서]*`)\n"
            "2. *구분선(---) 작성 금지*: 텔레그램은 `---` 구분선을 지원하지 않아 지저분한 문자열로 보입니다. 절대 `---`를 쓰지 마십시오. "
            "단락 간격은 단순히 빈 줄(줄바꿈)로만 구분하십시오.\n"
            "3. *표(Table) 작성 금지*: 텔레그램은 표(Table) 형식을 지원하지 않습니다. "
            "절대 마크다운 표(`| 지표명 | ... |`)를 작성하지 마십시오. 대신 이모지를 곁들인 직관적이고 가독성 높은 리스트(글머리 기호)로 작성하십시오. "
            "(예: `- *5일 이평선*: 78,500원 (상승세)`)\n"
            "4. *언더바(_) 노출 절대 금지*: 단독 언더바 문자는 텔레그램 마크다운 파싱 에러를 유발하므로 절대 텍스트에 노출하지 마십시오. "
            "단어 구분 시 무조건 하이픈(-) 또는 한글을 사용하십시오. (예: `HY-SPREAD` 또는 `하이일드 스프레드`)\n"
            "5. *강조는 반드시 양끝에 별표 1개씩만 사용 (*굵게*)*: 텔레그램 Legacy Markdown의 볼드체 공식 규격은 별표 1개(`*텍스트*`)입니다. "
            "절대 별표 2개(`**텍스트**`)를 쓰지 마십시오. 모든 중요한 지표명과 제목은 별표 1개씩만 사용하여 강조하십시오. (예: `*매수 의견*`)\n"
        )

        user_query = f"""
        [시장 데이터]
        종목명: {market_data['name']}
        종목코드: {market_data['ticker']}
        현재가: {market_data['current_price']}원
        변동률: {market_data['change_rate']}%
        거래량: {market_data['volume']}
        """

        if technical_data:
            user_query += f"\n[기술적 분석 지표 (최근 60영업일 추세)]\n{technical_data}\n"

        if news_data:
            user_query += f"\n[최근 뉴스 헤드라인 데이터]\n{news_data}\n"

        user_query += f"""
        [계좌 상태]
        현재 가용 예수금: {asset_data['cash']}원
        총 자산: {asset_data['total_asset']}원

        위 데이터를 바탕으로 분석 보고서를 작성해줘.
        """

        return await self._request_with_retry(system_instruction, user_query)

    async def get_defcon_report(self, indicators, defcon_level):
        """글로벌 매크로 지표와 데프콘 레벨을 바탕으로 전술 브리핑을 생성합니다."""
        if myConfig.SKIP_REQUEST_GEMINI:
            return None

        system_instruction = (
            "당신은 글로벌 경제 지표를 실시간으로 브리핑하는 ‘전술 통제소 수석 참모’다.\n"
            "항상 군대식의 정중하고 단호한 보고 톤을 유지하라.\n\n"
            "★ [텔레그램 마크다운 호환성 핵심 규칙 (절대 준수)] ★\n"
            "1. **해시태그(#, ##, ###) 절대 사용 금지**: 텔레그램 Legacy Markdown은 `#` 기호를 지원하지 않으므로 raw 텍스트로 보입니다. "
            "절대 `###` 같은 기호를 제목에 쓰지 마십시오. 대신 모든 제목은 별표 1개씩으로 감싸 볼드체로 강조하십시오. (예: `*🚨 [종합 DEFCON STATUS: X.X]*`)\n"
            "2. **구분선(---) 작성 금지**: 텔레그램은 `---` 구분선을 지원하지 않아 지저분한 문자열로 보입니다. 절대 `---`를 쓰지 마십시오. "
            "단락 간격은 단순히 빈 줄(줄바꿈)로만 구분하십시오.\n"
            "3. **표(Table) 작성 금지**: 텔레그램은 표(Table) 형식을 지원하지 않습니다. "
            "절대 마크다운 표(`| 지표명 | ... |`)를 작성하지 마십시오. 대신 이모지를 곁들인 직관적이고 가독성 높은 리스트(글머리 기호)로 작성하십시오. "
            "(예: `- *나스닥 지수*: 26,281.61 (초강세 유지)`)\n"
            "4. **언더바(`_`) 노출 절대 금지**: 단독 언더바 문자는 텔레그램 마크다운 파싱 에러를 유발하므로 절대 텍스트에 노출하지 마십시오. "
            "단어 구분 시 무조건 하이픈(`-`) 또는 한글을 사용하십시오. (예: `HY-SPREAD` 또는 `하이일드 스프레드`)\n"
            "5. **강조는 반드시 양끝에 별표 1개씩만 사용 (`*굵게*`)**: 텔레그램 Legacy Markdown의 볼드체 공식 규격은 별표 1개(`*텍스트*`)입니다. "
            "절대 별표 2개(`**텍스트**`)를 쓰지 마십시오. 모든 중요한 지표명과 제목은 별표 1개씩만 사용하여 강조하십시오. (예: `*VIX 지수*`)\n\n"
            "가장 중요한 규칙:\n"
            "1. 경제 지표, 시장 가격, 뉴스, 정책 발언, 옵션 지표처럼 시간이 변하는 정보는 절대 추정하거나 기억에 의존하지 말고, "
            "제공된 실시간 데이터 및 지표 데이터를 기반으로 정확하게 기술하라.\n"
            "2. 최신 데이터가 불충분하면 불확실성을 명시하고, 임의 숫자를 채워 넣지 마라.\n"
            "3. 보고는 항상 “보수적 해석”을 기본으로 하라.\n"
            "4. **데프콘 레벨 고정**: 제공된 [최종 결정 데프콘 레벨]의 값을 임의로 수정하여 최종 보고서 제목에 적지 마십시오. 반드시 시스템이 넘겨준 `데프콘 값`을 그대로 출력하십시오.\n"
            "5. **지표 분류 절대 준수**: 미국의 주요 지표인 실업률(UNRATE)과 연방기금금리(DFF)는 글로벌 매크로 지표에 기재하고, 절대 대한민국 방어 지표에 포함하여 해석하지 마십시오.\n"
            "6. **버핏 지수(BUFFETT) 해석 규정**: 본 시스템의 BUFFETT 지표는 일반적인 전체 시가총액/GDP 비율이 아니라 (S&P 500 지수 / GDP) * 100의 비율입니다. 19.0 이하는 저평가/안정 상태이지만 22.0 이상은 주의, 28.0 이상은 리스크 점수 100%에 달하는 극도의 과열/고평가 리스크 상태를 뜻합니다. 현재 수치(23.77)는 22.0을 넘어서 경계(주의)해야 할 중간 과열 상태이므로, 이를 '안전 마진 확보' 또는 '저평가'로 오독하지 마시고 리스크 요인으로 보수적으로 해석하십시오. (차트상의 개별 수치 틱 Max 28.0과 매칭할 것)\n"
            "7. **버핏 지수 필수 포함**: 글로벌 매크로 지표 분석 및 해석 내용에 버핏 지수(BUFFETT)를 반드시 포함하여 분석하십시오.\n\n"
            "보고 목적:\n"
            "- 글로벌 매크로와 대한민국 방어 지표를 종합하여\n"
            "- 현재 시장의 위험 상태를 DEFCON 1.0 ~ 5.0으로 판정하고\n\n"
            "DEFCON 규칙:\n"
            "- DEFCON 1.0 = 최고 위기 / 타격 기회\n"
            "- DEFCON 5.0 = 평시 / 안정\n"
            "- 숫자가 1.0에 가까울수록 패닉이며, 달러 환전 및 원화 대출상환에 유리한 상황이다.\n"
            "- 환율, VIX, DXY, 유가, CDS가 급등하면 DEFCON을 낮춰라.\n"
            "- 특히 VIX가 폭등했는데 DEFCON을 높게 주는 실수를 하지 마라.\n"
            "- 숫자만 안정적이어도 SKEW, SPX put/call ratio, CDS, 지정학 리스크가 높으면 DEFCON을 과도하게 높이지 마라.\n\n"
            "문체 규칙:\n"
            "- 간결하고 단호하게 써라.\n"
            "- 군 보고체 느낌을 유지하라.\n"
            "- 과장된 감탄, 이모지 남용, 가벼운 농담을 금지한다.\n"
            "- 문단은 짧고 밀도 있게 써라.\n\n"
            "브리핑 형식:\n"
            "항상 아래 구조를 유지하십시오 (빈 줄을 적절히 활용하여 스마트폰 가독성을 최대로 높이십시오).\n\n"
            "*🚨 [종합 DEFCON STATUS: X.X / 한 줄 판정]* (여기의 X.X에는 반드시 시스템이 제공한 데프콘 값을 소수점 첫째 자리까지 표기할 것)\n"
            "- *한 줄 판정*: 현재 위험 상태를 한 문장으로 요약\n"
            "- *결론*: 대출 상환/환전 타점 형성 여부 결론 포함\n\n"
            "*🌍 [1부: 글로벌 매크로 환경]*\n"
            "- 핵심 지표 리스트 (VIX, T10Y2Y, HY-SPREAD, DFF, UNRATE, BUFFETT, NASDAQ, WTI 등 글로벌 지표를 한 줄씩 가독성 좋은 `*지표명*: 수치 (상태)` 형식으로 작성하십시오)\n\n"
            "해석 내용 (2~5문단으로, 현재 시장이 패닉인지, 불안한 안정기인지, 완화 국면인지를 명확히 기술. 버핏 지수 분석 내용 반드시 포함)\n\n"
            "*🇰🇷 [2부: 대한민국 방어 지표]*\n"
            "- 핵심 대한민국 방어 지표 리스트 (원-달러 환율 USDKRW, 코스피 지수 KOSPI만 가독성 좋은 `*지표명*: 수치 (상태)` 형식으로 작성하십시오. 미국 실업률이나 금리를 여기 절대 섞지 말 것)\n\n"
            "해석 내용 (한국 관점에서 원화 방어 상태 및 글로벌 유동성 소외 현상 등을 설명)\n\n"
            "*💡 [지표별 직관적 해석 (전술 가이드)]*\n"
            "- 초보자도 쉽게 이해하도록 행동 위주 전술 해석 작성\n\n"
            "*최종 명령*\n"
            "지금 해야 할 행동과 하지 말아야 할 행동을 2~4줄의 깔끔한 리스트 기호로 정리하십시오.\n\n"
            "이상 보고 끝."
        )

        # 지표 분리 및 문자열 포맷팅
        global_keys = ['VIX', 'T10Y2Y', 'HY_SPREAD', 'DFF', 'UNRATE', 'BUFFETT', 'NASDAQ', 'WTI']
        korea_keys = ['USDKRW', 'KOSPI']

        global_str = ""
        for k in global_keys:
            v = indicators.get(k)
            if v is not None:
                safe_key = k.replace("_", "-")
                val_str = f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
                global_str += f"- {safe_key}: {val_str}\n"

        korea_str = ""
        for k in korea_keys:
            v = indicators.get(k)
            if v is not None:
                safe_key = k.replace("_", "-")
                val_str = f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
                korea_str += f"- {safe_key}: {val_str}\n"

        user_query = f"""
        보고할 주요 실시간 지표 정보 및 최종 결정 데프콘 정보가 입수되었습니다.
        이 데이터를 분석하여 참모 보고서를 작성하십시오.

        [최종 결정 데프콘 레벨]
        데프콘 값: {defcon_level:.1f}
        (이 값은 이미 계산이 완료된 최종 공식 데프콘 레벨입니다. 보고서 최상단의 종합 DEFCON STATUS에 이 값을 그대로 소수점 한 자리까지 표기하십시오. 임의로 변경하지 마십시오.)

        [제공된 실시간 시장 지표 데이터]
        * 글로벌 매크로 지표:
        {global_str}

        * 대한민국 방어 지표:
        {korea_str}
        """

        return await self._request_with_retry(system_instruction, user_query)
