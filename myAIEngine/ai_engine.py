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