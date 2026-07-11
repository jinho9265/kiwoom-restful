# test_backtest.py
import pandas as pd
import numpy as np
import datetime
from myBacktest.backtester import Backtester

def generate_mock_data():
    """테스트용 가상 주식 데이터 생성"""
    np.random.seed(42)
    dates = pd.date_range(start="2025-01-01", periods=100, freq='B')
    
    # 70,000원에서 시작해서 랜덤 워크로 종가 생성
    prices = [70000.0]
    for _ in range(99):
        # -3% ~ +3% 변동
        change = np.random.uniform(-0.03, 0.03)
        prices.append(prices[-1] * (1 + change))
        
    df = pd.DataFrame(index=dates)
    df['종가'] = np.round(prices).astype(float)
    df['시가'] = np.round(df['종가'] * np.random.uniform(0.98, 1.02, size=100)).astype(float)
    df['고가'] = np.round(np.maximum(df['시가'], df['종가']) * np.random.uniform(1.0, 1.03, size=100)).astype(float)
    df['저가'] = np.round(np.minimum(df['시가'], df['종가']) * np.random.uniform(0.97, 1.0, size=100)).astype(float)
    df['거래량'] = np.random.randint(100000, 2000000, size=100).astype(float)
    
    df.index.name = '일자'
    return df

def test_backtest_flow():
    print("1. 가상 데이터 생성 중...")
    df = generate_mock_data()
    print(df.head())
    
    print("\n2. Backtester 초기화...")
    tester = Backtester(df, initial_capital=10000000.0)
    
    print("\n3. SMA 전략 백테스팅 실행...")
    sma_res = tester.run_sma(5, 20)
    print(f"SMA 최종자산: {sma_res['final_value']:,.0f}원 | 수익률: {sma_res['total_return']:.2f}% | MDD: {sma_res['mdd']:.2f}% | 거래횟수: {sma_res['num_trades']}회")
    
    print("\n4. RSI 전략 백테스팅 실행...")
    rsi_res = tester.run_rsi()
    print(f"RSI 최종자산: {rsi_res['final_value']:,.0f}원 | 수익률: {rsi_res['total_return']:.2f}% | MDD: {rsi_res['mdd']:.2f}% | 거래횟수: {rsi_res['num_trades']}회")
    
    print("\n5. 볼린저 밴드 전략 백테스팅 실행...")
    bb_res = tester.run_bb()
    print(f"BB 최종자산: {bb_res['final_value']:,.0f}원 | 수익률: {bb_res['total_return']:.2f}% | MDD: {bb_res['mdd']:.2f}% | 거래횟수: {bb_res['num_trades']}회")
    
    print("\n6. MACD 전략 백테스팅 실행...")
    macd_res = tester.run_macd()
    print(f"MACD 최종자산: {macd_res['final_value']:,.0f}원 | 수익률: {macd_res['total_return']:.2f}% | MDD: {macd_res['mdd']:.2f}% | 거래횟수: {macd_res['num_trades']}회")
    
    print("\n7. 성과 차트 이미지 생성...")
    chart_path = tester.plot_result('SMA', '테스트종목')
    print(f"차트 이미지 생성 완료: {chart_path}")
    
    assert sma_res['final_value'] > 0
    assert rsi_res['final_value'] > 0
    assert bb_res['final_value'] > 0
    assert macd_res['final_value'] > 0
    print("\n백테스트 핵심 기능 검증 성공!")

if __name__ == "__main__":
    test_backtest_flow()
