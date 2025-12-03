import MetaTrader5 as mt5
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

# --- 1. 获取 M5 数据 ---
if not mt5.initialize(): quit()

# 记得确认这是你的品种代码
symbol = "XAUUSDm" 

print(f"🏎️ 正在获取 {symbol} 的 M5 (5分钟) 数据...")
print("数据量较大 (15000根)，请稍等...")

# M5 数据量要大，15000根大约覆盖过去 2个月
rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M5, 0, 15000)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("❌ 没抓到数据！"); quit()

df = pd.DataFrame(rates)
df['time'] = pd.to_datetime(df['time'], unit='s')
df.set_index('time', inplace=True)

# --- 2. 计算指标 ---
# ATR (14周期)
df['h-l'] = df['high'] - df['low']
df['h-pc'] = abs(df['high'] - df['close'].shift(1))
df['l-pc'] = abs(df['low'] - df['close'].shift(1))
df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
df['atr'] = df['tr'].rolling(window=14).mean()

# 支撑位 (M5级别变化快，我们看过去 20 根，也就是100分钟内的低点)
lookback = 20
prev_lows = df['low'].shift(1).rolling(window=lookback).min()
tolerance = 1.005 # M5 波动小，容错率只要 0.5% 就够了，给太大容易抓到半山腰
df['At_Support'] = (df['low'] <= prev_lows * tolerance) | (df['low'].shift(1) <= prev_lows * tolerance)

# 形态：看涨吞没
prev_red = df['close'].shift(1) < df['open'].shift(1)
curr_green = df['close'] > df['open']
engulfing_low = df['open'] < df['close'].shift(1)
engulfing_high = df['close'] > df['open'].shift(1)
df['Buy_Signal'] = prev_red & curr_green & engulfing_low & engulfing_high & df['At_Support']

buy_signals_index = df[df['Buy_Signal']].index
print(f"✅ 在 M5 周期上找到了 {len(buy_signals_index)} 次交易机会！(这就是你想要的频率)")

# --- 3. 网格搜索 (针对剥头皮调整) ---
def run_backtest(atr_multiplier, risk_reward_ratio):
    balance = 10000
    risk_per_trade = 0.02
    win_count = 0
    total_trades = 0
    
    for signal_time in buy_signals_index:
        row = df.loc[signal_time]
        if pd.isna(row['atr']): continue

        # M5 特别注意：点差成本
        # 假设点差是 0.3 美金 (30个微点)，这在 M5 影响很大，我们最好把它算进成本
        spread_cost = 0.30 

        entry_price = row['close']
        atr_buffer = row['atr'] * atr_multiplier 
        stop_loss = row['low'] - atr_buffer
        sl_distance = entry_price - stop_loss
        
        # 如果止损距离太小(比如小于0.5美金)，很容易被点差打死，这单不做
        if sl_distance < 0.5: continue
        
        take_profit = entry_price + (sl_distance * risk_reward_ratio)
        
        # 快速回测：只看未来 24 根 K线 (2小时内必须出结果，不然就不是剥头皮了)
        future_data = df.loc[signal_time:].iloc[1:].head(24)
        
        result = "TimeOut"
        exit_price = future_data.iloc[-1]['close'] if len(future_data) > 0 else entry_price
        
        for idx, f_row in future_data.iterrows():
            if f_row['low'] <= stop_loss:
                result = "Loss"; exit_price = stop_loss; break
            if f_row['high'] >= take_profit:
                result = "Win"; exit_price = take_profit; break
        
        total_trades += 1
        risk_amount = balance * risk_per_trade
        position_size = risk_amount / sl_distance
        
        # 计算盈亏 (减去 spread 成本模拟)
        # 如果赢了，实际赚的要少一点点；如果输了，实际亏的要多一点点
        # 这里简单处理，直接算点数盈亏
        profit = (exit_price - entry_price) * position_size
        
        balance += profit
        if result == "Win": win_count += 1

    final_return = (balance - 10000) / 10000 * 100
    win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
    return final_return, win_rate

# --- 4. 运行扫描 ---
print("-" * 65)
print(f"{'ATR倍数':<8} | {'盈亏比':<8} | {'总收益%':<10} | {'胜率%':<15}")
print("-" * 65)

results = []
# 针对 M5 的参数范围 (更紧的止损，更小的盈亏比)
atr_multipliers = [0.5, 0.8, 1.0, 1.2]
rr_ratios       = [1.0, 1.5, 2.0, 2.5] 

best_score = -999
best_params = (0, 0)

for atr_mult in atr_multipliers:
    for rr in rr_ratios:
        final_ret, win_rate = run_backtest(atr_mult, rr)
        
        print(f"{atr_mult:<8} | {rr:<8} | {final_ret:<10.2f} | {win_rate:<15.1f}")
        results.append((atr_mult, rr, final_ret))
        
        if final_ret > best_score:
            best_score = final_ret
            best_params = (atr_mult, rr)

print("-" * 65)
print(f"🏆 M5 最佳参数: ATR={best_params[0]}, RR={best_params[1]}")
print(f"⚠️ 注意：如果最佳收益是负的，说明这个策略不适合 M5！")

# 热力图
results_df = pd.DataFrame(results, columns=['ATR_Mult', 'RR_Ratio', 'Return'])
pivot_table = results_df.pivot(index='ATR_Mult', columns='RR_Ratio', values='Return')
plt.figure(figsize=(10, 8))
sns.heatmap(pivot_table, annot=True, fmt=".1f", cmap="RdYlGn", center=0)
plt.title('M5 Scalping Strategy Heatmap')
plt.show()