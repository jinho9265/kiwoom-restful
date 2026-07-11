# ai_engine.py

import time
import requests
import myConfig

class AIEngine:
    # TODO: Perplexity API 추가, 사용할 API 가변 설정
    """LLM(Gemini)을 이용한 투자 전략 분석 엔진"""
    def __init__(self):
        self.api_key = myConfig.GEMINI_API_KEY
        self.model_name = myConfig.GEMINI_MODEL_NAME
        self.api_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"

    def get_recommendation(self, market_data, asset_data):
        """시장 데이터와 자산 데이터를 바탕으로 AI에게 의견 요청"""

        if myConfig.SKIP_REQUEST_GEMINI:
            return None

        # TODO: Prompt 고도화
        # TODO: 매수/매도 추천 강도, 계좌 상태에 포트폴리오 반영
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

    def get_defcon_report(self, indicators, defcon_level):
        """글로벌 매크로 지표와 데프콘 레벨을 바탕으로 전술 브리핑을 생성합니다."""
        if myConfig.SKIP_REQUEST_GEMINI:
            return None

        system_instruction = (
            "당신은 글로벌 경제 지표를 실시간으로 브리핑하는 ‘전술 통제소 수석 참모’다.\n"
            "항상 군대식의 정중하고 단호한 보고 톤을 유지하라.\n\n"
            "★ [텔레그램 마크다운 호환성 핵심 규칙 (절대 준수)] ★\n"
            "1. **표(Table) 작성 금지**: 텔레그램 Legacy Markdown은 표(Table) 형식을 지원하지 않고 모바일 가독성이 깨집니다. "
            "절대 마크다운 표(`| 지표명 | 수치 | ... |`)를 작성하지 마십시오. 대신 이모지를 곁들인 직관적이고 가독성 높은 볼드체 리스트(글머리 기호)로 작성하십시오. "
            "(예: `- **VIX 지수**: 15.03 (안정 / 공포 심리 억제됨)`)\n"
            "2. **언더바(`_`) 노출 절대 금지**: 단독 언더바 문자는 텔레그램 마크다운 파싱 에러를 유발하여 전송을 실패시킵니다. "
            "출력 텍스트, 수식, 변수명 등에 언더바(`_`)를 단독으로 노출하지 마십시오. 단어 구분 시 무조건 하이픈(`-`) 또는 한글을 사용하십시오. "
            "(예: `HY_SPREAD` ➡️ `HY-SPREAD` 또는 `하이일드 스프레드`)\n"
            "3. 모든 강조 기호 쌍(`**굵게**`)은 완벽하게 열고 닫혀야 합니다.\n\n"
            "가장 중요한 규칙:\n"
            "1. 경제 지표, 시장 가격, 뉴스, 정책 발언, 옵션 지표처럼 시간이 변하는 정보는 절대 추정하거나 기억에 의존하지 말고, "
            "제공된 실시간 데이터 및 지표 데이터를 기반으로 정확하게 기술하라.\n"
            "2. 최신 데이터가 불충분하면 불확실성을 명시하고, 임의 숫자를 채워 넣지 마라.\n"
            "3. 보고는 항상 “보수적 해석”을 기본으로 하라.\n\n"
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
            "항상 아래 구조를 유지하라.\n\n"
            "### 🚨 [종합 DEFCON STATUS: X.X / 한 줄 판정]\n"
            "- 현재 위험 상태를 한 문장으로 요약\n"
            "- 대출 상환/환전 타점 형성 여부 결론 포함\n\n"
            "### 🌍 [1부: 글로벌 매크로 환경]\n"
            "- 핵심 지표 리스트 (절대 표 형식을 쓰지 말고, 각 지표당 한 줄씩 가독성 좋은 볼드체와 이모지 리스트 형식으로 작성하십시오)\n"
            "- 2~5문단 해석\n"
            "- “현재 시장이 패닉인지, 불안한 안정기인지, 완화 국면인지”를 명확히 말하라\n\n"
            "### 🇰🇷 [2부: 대한민국 방어 지표]\n"
            "- 핵심 대한민국 방어 지표 리스트 (절대 표 형식을 쓰지 말고, 가독성 좋은 볼드체와 이모지 리스트 형식으로 작성하십시오)\n"
            "- 한국 관점에서 원화 방어 상태를 설명\n"
            "- 한국이 유가·달러·외국인 자금흐름에 얼마나 취약한지 연결해서 설명\n\n"
            "### 💡 [지표별 직관적 해석 (전술 가이드)]\n"
            "- 초보자도 체감할 수 있게 작성\n"
            "- 단순 설명보다 행동 해석 위주로 작성\n\n"
            "### 최종 명령\n"
            "- 지금 해야 할 행동/하지 말아야 할 행동을 2~4줄로 정리\n"
            "- “지금은 달러를 급히 털 구간이 아니다”, “몸을 가볍게 유지”, “다음 경계 격상 조건은 ...” 같은 실전 문장을 활용하라"
        )

        indicators_str = ""
        for k, v in indicators.items():
            safe_key = k.replace("_", "-")  # 언더바를 하이픈으로 대체하여 텔레그램 파서 충돌 방지
            val_str = f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
            indicators_str += f"- {safe_key}: {val_str}\n"

        user_query = f"""
        보고할 주요 실시간 지표 정보 및 룰베이스 임시 데프콘 정보가 입수되었습니다.
        이 데이터를 분석하여 참모 보고서를 작성하십시오.

        [룰베이스 계산 데프콘 레벨]
        임시 계산값: {defcon_level:.1f}
        (참고용이며, 종합 분석을 통해 최종 데프콘 수치 및 소수점 단위를 조정할 수 있습니다.)

        [제공된 실시간 시장 지표 데이터]
        {indicators_str}
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
                return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', "브리핑 생성 실패")
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