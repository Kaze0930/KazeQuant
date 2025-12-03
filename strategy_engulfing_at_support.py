import MetaTrader5 as mt5
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- 1. 核心配置 (与你的机器人完全一致) ---
SYMBOL = "XAUUSDm"          # 你的品种
TIMEFRAME = mt5.TIMEFRAME_H4  # H4 周期
ATR_MULT = 1.5              # 宽止损
RR_RATIO = 3.0              # 大盈亏比
RISK_PER_TRADE = 0.02       # 每笔亏 2%
INITIAL_BALANCE = 10000     # 初始本金

# --- 2. 获取足够多的 H4 数据 ---
if not mt5.initialize():
    print("❌ MT5 初始化失败")
    quit()

print(f"正在获取 {SYMBOL} 过去 5000 根 H4 K线进行终极回测...")
# 5000根 H4 大约是过去 1.5 ~ 2 年的数据
rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 5000)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("❌ 没抓到数据，请检查品种名称！")
    quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)

# --- 3. 计算指标 ---
# ATR
df['h-l'] = df['high'] - df['low']
df['h-pc'] = abs(df['high'] - df['close'].shift(1))
df['l-pc'] = abs(df['low'] - df['close'].shift(1))
df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
df['atr'] = df['tr'].rolling(window=14).mean()

# 支撑位 (过去 20 根)
lookback = 20
prev_lows = df['low'].shift(1).rolling(window=lookback).min()
tolerance = 1.01 
df['At_Support'] = (df['low'] <= prev_lows * tolerance) | (df['low'].shift(1) <= prev_lows * tolerance)

# 形态 (看涨吞没)
prev_red = df['close'].shift(1) < df['open'].shift(1)
curr_green = df['close'] > df['open']
engulfing = (df['open'] < df['close'].shift(1)) & (df['close'] > df['open'].shift(1))

# 信号
df['Buy_Signal'] = prev_red & curr_green & engulfing & df['At_Support']

# --- 4. 逐笔回测 ---
trades = []
balance = INITIAL_BALANCE
equity_curve = [balance]
dates = [df.index[0]]

print(f"🚀 开始回测 {len(df)} 根 K 线...")

buy_signals = df[df['Buy_Signal']]

for signal_time in buy_signals.index:
    row = df.loc[signal_time]
    if pd.isna(row['atr']): continue

    # 入场参数
    entry_price = row['close']
    stop_loss = row['low'] - (row['atr'] * ATR_MULT)
    sl_distance = entry_price - stop_loss
    
    if sl_distance <= 0: continue # 异常数据保护
    
    take_profit = entry_price + (sl_distance * RR_RATIO)
    
    # 模拟未来走势
    future_data = df.loc[signal_time:].iloc[1:]
    
    # 设置超时：H4 周期如果 50 根 K线 (约10天) 还没走出结果，就平仓
    # 防止资金被无限期占用
    max_hold_bars = 50 
    future_data = future_data.head(max_hold_bars)
    
    result = "TimeOut"
    exit_price = future_data.iloc[-1]['close'] if len(future_data) > 0 else entry_price
    exit_time = future_data.index[-1] if len(future_data) > 0 else signal_time
    
    for idx, f_row in future_data.iterrows():
        # 必须先判断止损 (因为通常低点先出现)
        if f_row['low'] <= stop_loss:
            result = "Loss"
            exit_price = stop_loss
            exit_time = idx
            break
        
        # 再判断止盈
        if f_row['high'] >= take_profit:
            result = "Win"
            exit_price = take_profit
            exit_time = idx
            break
            
    # 计算盈亏 (基于 2% 风控模型)
    risk_amount = balance * RISK_PER_TRADE
    # 仓位大小 = 风险金额 / 单手止损距离
    position_size = risk_amount / sl_distance
    
    pnl = (exit_price - entry_price) * position_size
    balance += pnl
    
    # 记录数据
    trades.append({
        'Entry Time': signal_time,
        'Result': result,
        'PnL': pnl,
        'Balance': balance
    })
    
    # 记录资金曲线点
    equity_curve.append(balance)
    dates.append(exit_time)

# --- 5. 生成报告 ---
trade_df = pd.DataFrame(trades)

if len(trade_df) > 0:
    # 统计数据
    total_trades = len(trade_df)
    wins = trade_df[trade_df['Result'] == 'Win']
    losses = trade_df[trade_df['Result'] == 'Loss']
    
    win_rate = len(wins) / total_trades * 100
    total_return = (balance - INITIAL_BALANCE) / INITIAL_BALANCE * 100
    
    # 计算最大回撤 (Max Drawdown)
    equity_series = pd.Series(equity_curve)
    rolling_max = equity_series.cummax()
    drawdown = (equity_series - rolling_max) / rolling_max * 100
    max_drawdown = drawdown.min()

    print(f"\n{'='*40}")
    print(f"📊 最终回测报告: {SYMBOL} (H4)")
    print(f"{'='*40}")
    print(f"总交易次数: {total_trades}")
    print(f"净利润: {total_return:.2f}%")
    print(f"最终余额: ${balance:.2f}")
    print(f"--------------------------------")
    print(f"胜率 (Win Rate): {win_rate:.2f}%")
    print(f"盈亏比 (RR): 1 : {RR_RATIO}")
    print(f"最大回撤 (Max Drawdown): {max_drawdown:.2f}%")
    print(f"--------------------------------")
    print(f"盈利单数: {len(wins)}")
    print(f"亏损单数: {len(losses)}")
    print(f"超时平仓: {len(trade_df[trade_df['Result'] == 'TimeOut'])}")
    print(f"{'='*40}")

    # 画图
    plt.figure(figsize=(12, 8))
    
    # 子图1: 资金曲线
    plt.subplot(2, 1, 1)
    plt.plot(dates, equity_curve, color='purple', linewidth=2)
    plt.title(f'Equity Curve: {SYMBOL} (H4, ATR={ATR_MULT}, RR={RR_RATIO})')
    plt.ylabel('Account Balance ($)')
    plt.grid(True)
    
    # 标记最高点
    plt.axhline(balance, color='green', linestyle='--', alpha=0.5, label='Final Balance')
    
    # 子图2: 逐笔盈亏柱状图
    plt.subplot(2, 1, 2)
    colors = ['green' if p > 0 else 'red' for p in trade_df['PnL']]
    plt.bar(trade_df['Entry Time'], trade_df['PnL'], color=colors, width=0.5)
    plt.title('Trade by Trade PnL')
    plt.ylabel('Profit/Loss ($)')
    plt.axhline(0, color='black', linewidth=1)
    plt.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

else:
    print("⚠️ 该时间段内没有触发任何信号。")