import MetaTrader5 as mt5
import pandas as pd
import numpy as np

# ================= ⚙️ 参数扫描配置 =================
SYMBOL = "XAUUSDm"
TIMEFRAME = mt5.TIMEFRAME_M5
DATA_COUNT = 10000

# 我们要测试的参数组合
ATR_TESTS = [0.5, 0.8, 1.0, 1.2]   # 测试 4 种止损宽度
RR_TESTS = [1.5, 2.0, 2.5]         # 测试 3 种盈亏比

FIXED_SPREAD = 0.20
START_HOUR = 8
END_HOUR = 21 
# =================================================

if not mt5.initialize(): quit()

def get_data():
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, DATA_COUNT)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def run_test(df, atr_mult, rr_ratio):
    # 基础指标只需计算一次，放在外面传入即可优化速度，但为了代码简单这里重算
    df = df.copy()
    
    # 1. 计算 ATR
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()
    
    # 2. 支撑位
    df['prev_lows'] = df['low'].shift(1).rolling(window=20).min()
    
    trades = []
    
    for i in range(30, len(df)-1):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # A. 时间过滤
        if not (START_HOUR <= curr['time'].hour < END_HOUR): continue

        # B. 信号 (去除 EMA，回归原始逻辑)
        tolerance = 1.005
        support_val = curr['prev_lows']
        at_support = (curr['low'] <= support_val * tolerance) or \
                     (prev['low'] <= support_val * tolerance)
        
        prev_red = prev['close'] < prev['open']
        curr_green = curr['close'] > curr['open']
        engulfing = (curr['open'] < prev['close']) and \
                    (curr['close'] > prev['open'])
        
        if at_support and prev_red and curr_green and engulfing:
            entry = curr['close']
            # --- 动态参数 ---
            sl_dist = curr['atr'] * atr_mult  # 使用测试的 ATR 系数
            sl_price = curr['low'] - sl_dist
            
            risk = entry - sl_price
            if risk <= 0: continue
            
            tp_price = entry + (risk * rr_ratio) # 使用测试的 RR
            
            result = "No Result"
            r_outcome = 0
            
            # 这里的 60 是持仓超时限制，可以不动
            for j in range(i+1, min(i+100, len(df))):
                future = df.iloc[j]
                
                if future['low'] <= sl_price:
                    spread_cost = (FIXED_SPREAD / risk)
                    r_outcome = -1.0 - spread_cost
                    result = "Loss"
                    break
                
                if future['high'] >= tp_price:
                    spread_cost = (FIXED_SPREAD / risk)
                    r_outcome = rr_ratio - spread_cost
                    result = "Win"
                    break
            
            if result != "No Result":
                trades.append(r_outcome)
    
    if len(trades) == 0: return 0, 0, 0
    
    total_r = sum(trades)
    win_count = len([x for x in trades if x > 0])
    win_rate = (win_count / len(trades)) * 100
    
    return total_r, win_rate, len(trades)

# ================= 🚀 开始扫描 =================
df_raw = get_data()

print(f"🧬 开始参数基因扫描 (XAUUSDm)...")
print("-" * 60)
print(f"{'ATR x':<8} | {'RR':<5} | {'Trades':<8} | {'Win Rate':<10} | {'Net R (Profit)':<15}")
print("-" * 60)

best_score = -999
best_params = ""

for atr_mult in ATR_TESTS:
    for rr in RR_TESTS:
        net_r, win_rate, count = run_test(df_raw, atr_mult, rr)
        
        print(f"{atr_mult:<8} | {rr:<5} | {count:<8} | {win_rate:.2f}%     | {net_r:.2f} R")
        
        if net_r > best_score:
            best_score = net_r
            best_params = f"ATR x {atr_mult} | RR {rr}"

print("-" * 60)
print(f"🏆 最佳参数组合: [{best_params}] -> 净利 {best_score:.2f} R")