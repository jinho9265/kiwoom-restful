# backtester.py
import pandas as pd
import numpy as np
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

class Backtester:
    def __init__(self, df: pd.DataFrame, initial_capital: float = 10000000.0, fee_rate: float = 0.00015, tax_rate: float = 0.0018):
        """
        백테스터 초기화
        :param df: '시가', '고가', '저가', '종가', '거래량' 컬럼과 DatetimeIndex를 가진 DataFrame
        :param initial_capital: 초기 투자 자금 (기본값: 10,000,000원)
        :param fee_rate: 거래 수수료율 (기본값: 0.015%)
        :param tax_rate: 매도 거래세율 (기본값: 0.18%)
        """
        self.df = df.copy()
        # 컬럼 존재 확인 및 한글 컬럼 처리 지원
        required_cols = ['시가', '고가', '저가', '종가', '거래량']
        for col in required_cols:
            if col not in self.df.columns:
                raise ValueError(f"입력 데이터에 '{col}' 컬럼이 필요합니다.")
        
        self.initial_capital = initial_capital
        self.fee_rate = fee_rate
        self.tax_rate = tax_rate
        
        # 성과 지표 결과 저장용
        self.results = {}

    def _simulate(self, signal_series: pd.Series) -> dict:
        """
        신호 시퀀스에 따라 일별 자산을 시뮬레이션합니다.
        :param signal_series: 1(매수), -1(매도), 0(관망)으로 이루어진 시리즈
        :return: 성과 요약 딕셔너리
        """
        cash = self.initial_capital
        shares = 0
        portfolio_values = []
        trade_log = [] # 거래 기록: (매수일, 매수가, 매수금액, 매도일, 매도가, 매도금액, 수익률)
        
        active_buy = None # 현재 진행중인 매수 정보: (일자, 가격, 수량)
        
        # 시뮬레이션 루프
        for date, row in self.df.iterrows():
            close_price = row['종가']
            signal = signal_series.loc[date]
            
            # 매수 신호가 발생했고, 주식이 없는 경우 (전량 매수)
            if signal == 1 and shares == 0:
                buy_price = close_price
                # 수수료 고려하여 살 수 있는 최대 수량 계산
                shares = int(cash / (buy_price * (1 + self.fee_rate)))
                if shares > 0:
                    buy_cost = shares * buy_price
                    fee = buy_cost * self.fee_rate
                    cash -= (buy_cost + fee)
                    active_buy = {
                        'date': date,
                        'price': buy_price,
                        'amount': buy_cost + fee,
                        'shares': shares
                    }
            
            # 매도 신호가 발생했고, 주식을 보유 중인 경우 (전량 매도)
            elif signal == -1 and shares > 0:
                sell_price = close_price
                sell_val = shares * sell_price
                fee = sell_val * self.fee_rate
                tax = sell_val * self.tax_rate
                cash += (sell_val - fee - tax)
                
                # 거래 성과 계산
                profit = (sell_val - fee - tax) - active_buy['amount']
                profit_rt = (profit / active_buy['amount']) * 100
                
                trade_log.append({
                    'buy_date': active_buy['date'],
                    'buy_price': active_buy['price'],
                    'sell_date': date,
                    'sell_price': sell_price,
                    'profit': profit,
                    'return_rt': profit_rt
                })
                shares = 0
                active_buy = None
                
            # 일별 포트폴리오 가치 기록
            current_value = cash + (shares * close_price)
            portfolio_values.append(current_value)
            
        self.df['Portfolio_Value'] = portfolio_values
        self.df['Equity_Return'] = (self.df['Portfolio_Value'] / self.initial_capital - 1) * 100
        
        # 만약 마지막 날까지 매도하지 않고 주식을 들고 있는 경우, 임시로 청산하여 거래 기록에 추가 (승률 계산용)
        if shares > 0 and active_buy:
            last_date = self.df.index[-1]
            last_price = self.df['종가'].iloc[-1]
            sell_val = shares * last_price
            fee = sell_val * self.fee_rate
            tax = sell_val * self.tax_rate
            profit = (sell_val - fee - tax) - active_buy['amount']
            profit_rt = (profit / active_buy['amount']) * 100
            trade_log.append({
                'buy_date': active_buy['date'],
                'buy_price': active_buy['price'],
                'sell_date': last_date,
                'sell_price': last_price,
                'profit': profit,
                'return_rt': profit_rt
            })
            
        # 성과 지표 산출
        final_value = portfolio_values[-1]
        total_return = (final_value / self.initial_capital - 1) * 100
        
        # CAGR (연평균 복리 수익률)
        days = (self.df.index[-1] - self.df.index[0]).days
        years = days / 365.25 if days > 0 else 0
        cagr = ((final_value / self.initial_capital) ** (1 / years) - 1) * 100 if years > 0 and final_value > 0 else total_return
        
        # MDD (최대 낙폭)
        peak = self.df['Portfolio_Value'].cummax()
        drawdown = (self.df['Portfolio_Value'] - peak) / peak * 100
        mdd = drawdown.min()
        
        # 승률 및 거래 횟수
        num_trades = len(trade_log)
        wins = sum(1 for t in trade_log if t['profit'] > 0)
        win_rate = (wins / num_trades * 100) if num_trades > 0 else 0.0
        
        return {
            'final_value': final_value,
            'total_return': total_return,
            'cagr': cagr,
            'mdd': mdd,
            'num_trades': num_trades,
            'win_rate': win_rate,
            'trade_log': trade_log,
            'equity_curve': self.df['Portfolio_Value'].copy()
        }

    def run_sma(self, short_window: int = 5, long_window: int = 20) -> dict:
        """
        이동평균선(SMA) 골든/데드 크로스 전략
        """
        self.df['SMA_short'] = self.df['종가'].rolling(window=short_window).mean()
        self.df['SMA_long'] = self.df['종가'].rolling(window=long_window).mean()
        
        signals = pd.Series(0, index=self.df.index)
        position = 0 # 0: 현금, 1: 주식보유
        
        for i in range(1, len(self.df)):
            prev_date = self.df.index[i-1]
            curr_date = self.df.index[i]
            
            # 이전 행과 현재 행의 이평선 비교
            prev_short = self.df['SMA_short'].iloc[i-1]
            prev_long = self.df['SMA_long'].iloc[i-1]
            curr_short = self.df['SMA_short'].iloc[i]
            curr_long = self.df['SMA_long'].iloc[i]
            
            if pd.isna(prev_long) or pd.isna(curr_long):
                continue
                
            # 골든크로스: 단기 이평선이 장기 이평선을 상향 돌파
            if position == 0 and curr_short > curr_long and prev_short <= prev_long:
                signals.loc[curr_date] = 1
                position = 1
            # 데드크로스: 단기 이평선이 장기 이평선을 하향 돌파
            elif position == 1 and curr_short < curr_long and prev_short >= prev_long:
                signals.loc[curr_date] = -1
                position = 0
                
        self.df['SMA_Signal'] = signals
        result = self._simulate(signals)
        self.results['SMA'] = result
        return result

    def run_rsi(self, period: int = 14, lower: float = 30.0, upper: float = 70.0) -> dict:
        """
        RSI 역추세 전략 (30 이하 과매도 매수, 70 이상 과매수 매도)
        """
        delta = self.df['종가'].diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        self.df['RSI'] = 100 - (100 / (1 + rs))
        
        signals = pd.Series(0, index=self.df.index)
        position = 0
        
        for i in range(1, len(self.df)):
            curr_date = self.df.index[i]
            curr_rsi = self.df['RSI'].iloc[i]
            
            if pd.isna(curr_rsi):
                continue
                
            if position == 0 and curr_rsi <= lower:
                signals.loc[curr_date] = 1
                position = 1
            elif position == 1 and curr_rsi >= upper:
                signals.loc[curr_date] = -1
                position = 0
                
        self.df['RSI_Signal'] = signals
        result = self._simulate(signals)
        self.results['RSI'] = result
        return result

    def run_bb(self, period: int = 20, num_std: float = 2.0) -> dict:
        """
        볼린저 밴드 전략 (하한선 돌파 시 매수, 상한선 돌파 시 매도)
        """
        ma = self.df['종가'].rolling(window=period).mean()
        std = self.df['종가'].rolling(window=period).std()
        
        self.df['BB_Mid'] = ma
        self.df['BB_Upper'] = ma + (std * num_std)
        self.df['BB_Lower'] = ma - (std * num_std)
        
        signals = pd.Series(0, index=self.df.index)
        position = 0
        
        for i in range(1, len(self.df)):
            curr_date = self.df.index[i]
            close = self.df['종가'].iloc[i]
            bb_lower = self.df['BB_Lower'].iloc[i]
            bb_upper = self.df['BB_Upper'].iloc[i]
            
            if pd.isna(bb_lower) or pd.isna(bb_upper):
                continue
                
            # 가격이 볼린저 밴드 하한선 이하로 떨어지면 매수
            if position == 0 and close <= bb_lower:
                signals.loc[curr_date] = 1
                position = 1
            # 가격이 볼린저 밴드 상한선 이상으로 오르면 매도
            elif position == 1 and close >= bb_upper:
                signals.loc[curr_date] = -1
                position = 0
                
        self.df['BB_Signal'] = signals
        result = self._simulate(signals)
        self.results['BB'] = result
        return result

    def run_macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
        """
        MACD 모멘텀 교차 전략 (MACD 선이 Signal 선을 상향 돌파 시 매수, 하향 돌파 시 매도)
        """
        ema_fast = self.df['종가'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['종가'].ewm(span=slow, adjust=False).mean()
        
        self.df['MACD'] = ema_fast - ema_slow
        self.df['MACD_Signal'] = self.df['MACD'].ewm(span=signal, adjust=False).mean()
        
        signals = pd.Series(0, index=self.df.index)
        position = 0
        
        for i in range(1, len(self.df)):
            prev_date = self.df.index[i-1]
            curr_date = self.df.index[i]
            
            prev_macd = self.df['MACD'].iloc[i-1]
            prev_sig = self.df['MACD_Signal'].iloc[i-1]
            curr_macd = self.df['MACD'].iloc[i]
            curr_sig = self.df['MACD_Signal'].iloc[i]
            
            if pd.isna(prev_sig) or pd.isna(curr_sig):
                continue
                
            # MACD가 Signal 선을 골든크로스
            if position == 0 and curr_macd > curr_sig and prev_macd <= prev_sig:
                signals.loc[curr_date] = 1
                position = 1
            # MACD가 Signal 선을 데드크로스
            elif position == 1 and curr_macd < curr_sig and prev_macd >= prev_sig:
                signals.loc[curr_date] = -1
                position = 0
                
        self.df['MACD_Signal_Trade'] = signals
        result = self._simulate(signals)
        self.results['MACD'] = result
        return result

    def plot_result(self, strategy_name: str, stock_name: str) -> str:
        """
        백테스트 결과를 차트로 렌더링하고 이미지로 저장합니다.
        :param strategy_name: 실행한 전략 이름 ('SMA', 'RSI', 'BB', 'MACD')
        :param stock_name: 종목명
        :return: 생성된 이미지의 로컬 파일 경로
        """
        if strategy_name not in self.results:
            raise ValueError(f"먼저 '{strategy_name}' 전략을 실행해야 차트를 생성할 수 있습니다.")
            
        result = self.results[strategy_name]
        
        # 다크 테마 설정
        plt.style.use('dark_background')
        
        # 한글 폰트 설정
        font_list = ['Malgun Gothic', 'NanumGothic', 'AppleGothic', 'sans-serif']
        font_set = False
        for font in font_list:
            if any(f.name == font for f in fm.fontManager.ttflist):
                plt.rcParams['font.family'] = font
                font_set = True
                break
        if not font_set:
            plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        
        # 1. 상단 차트: 종가 & 매매 시그널
        ax1.plot(self.df.index, self.df['종가'], label='종가', color='#888888', alpha=0.8, linewidth=1.5)
        
        # 전략별 보조지표 추가 표시
        if strategy_name == 'SMA' and 'SMA_short' in self.df:
            ax1.plot(self.df.index, self.df['SMA_short'], label='SMA 5', color='#ffcc00', linestyle='--', alpha=0.7)
            ax1.plot(self.df.index, self.df['SMA_long'], label='SMA 20', color='#ff33cc', linestyle='--', alpha=0.7)
            signal_col = 'SMA_Signal'
        elif strategy_name == 'BB' and 'BB_Upper' in self.df:
            ax1.plot(self.df.index, self.df['BB_Upper'], label='BB Upper', color='#cb4b16', linestyle=':', alpha=0.6)
            ax1.plot(self.df.index, self.df['BB_Lower'], label='BB Lower', color='#268bd2', linestyle=':', alpha=0.6)
            signal_col = 'BB_Signal'
        elif strategy_name == 'RSI':
            signal_col = 'RSI_Signal'
        elif strategy_name == 'MACD':
            signal_col = 'MACD_Signal_Trade'
        else:
            signal_col = None
            
        # 매수/매도 시점 마커 표시
        if signal_col and signal_col in self.df:
            buys = self.df[self.df[signal_col] == 1]
            sells = self.df[self.df[signal_col] == -1]
            
            ax1.scatter(buys.index, buys['종가'], label='매수 진입', marker='^', color='#34c759', s=100, zorder=5)
            ax1.scatter(sells.index, sells['종가'], label='매도 청산', marker='v', color='#ff3b30', s=100, zorder=5)
            
        ax1.set_title(f"{stock_name} ({strategy_name} 전략) 백테스트 분석", fontsize=14, fontweight='bold', pad=15)
        ax1.set_ylabel('주가 (원)', fontsize=10)
        ax1.grid(True, color='#2c2c2e', linestyle='--')
        ax1.legend(loc='upper left', fontsize=9)
        
        # 2. 하단 차트: 누적 수익률 곡선 (Equity Curve)
        equity_curve = (result['equity_curve'] / self.initial_capital - 1) * 100
        ax2.plot(equity_curve.index, equity_curve, label='누적 수익률', color='#268bd2', linewidth=2)
        ax2.fill_between(equity_curve.index, equity_curve, 0, color='#268bd2', alpha=0.15)
        
        ax2.set_ylabel('수익률 (%)', fontsize=10)
        ax2.set_xlabel('날짜', fontsize=10)
        ax2.grid(True, color='#2c2c2e', linestyle='--')
        
        # 최종 수익률 텍스트 표시
        final_ret = result['total_return']
        mdd = result['mdd']
        color = '#34c759' if final_ret >= 0 else '#ff3b30'
        ax2.text(0.02, 0.85, f"누적 수익률: {final_ret:+.2f}%\n최대 낙폭(MDD): {mdd:.2f}%", 
                 transform=ax2.transAxes, fontsize=10, weight='bold', color=color,
                 bbox=dict(boxstyle="round,pad=0.3", fc="#1c1c1e", ec=color, lw=1.5))
                 
        plt.tight_layout()
        
        os.makedirs("tmp_charts", exist_ok=True)
        chart_path = f"tmp_charts/backtest_{strategy_name.lower()}_{stock_name}.png"
        plt.savefig(chart_path, dpi=150, facecolor='#1c1c1e')
        plt.close()
        
        return chart_path
