import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# --- 配置区域 ---
SYMBOL = "XAUUSDm"      # 你的品种
TIMEFRAME = mt5.TIMEFRAME_H4  # 你的最佳周期
ATR_MULTIPLIER = 1.5    # 你的最佳参数
RR_RATIO = 3.0          # 你的最佳参数
LOOKBACK_BARS = 200     # 获取足够的数据来算指标

def get_latest_data():
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, LOOKBACK_BARS)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def check_signal(df):
    # 1. 计算 ATR
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()

    # 2. 计算支撑位 (过去 20 根 K 线最低价)
    lookback = 20
    prev_lows = df['low'].shift(1).rolling(window=lookback).min()
    tolerance = 1.01
    
    # 3. 获取最新的两根K线 (倒数第二根是刚收盘确认的，倒数第一根是正在跳动的)
    # 我们通常只看“已收盘”的 K 线 (iloc[-2])，因为正在跳动的 K 线形态还没确定
    last_candle = df.iloc[-2]     # 昨天/上个H4 (已确认)
    prev_candle = df.iloc[-3]     # 前天/上上个H4
    
    # 这里的 ATR 用的是收盘时的值
    current_atr = last_candle['atr']
    
    # --- 逻辑判断 ---
    
    # A. 是否在支撑位附近？
    # 检查收盘的那根K线，或者它的前一根，是否触及了支撑区
    support_price = prev_lows.iloc[-2]
    is_at_support = (last_candle['low'] <= support_price * tolerance) or \
                    (prev_candle['low'] <= support_price * tolerance)
    
    # B. 是否是吞没形态？
    # 前一根是红
    prev_red = prev_candle['close'] < prev_candle['open']
    # 刚才收盘这根是绿
    curr_green = last_candle['close'] > last_candle['open']
    # 包住
    engulfing = (last_candle['open'] < prev_candle['close']) and \
                (last_candle['close'] > prev_candle['open'])
    
    signal = is_at_support and prev_red and curr_green and engulfing
    
    return signal, last_candle, current_atr

# --- 主程序 ---
if not mt5.initialize():
    print("❌ MT5 连接失败")
    quit()

print(f"📡 猎手已启动！正在监控 {SYMBOL} 的 {TIMEFRAME} 周期...")
print(f"🎯 策略参数: ATR缓冲={ATR_MULTIPLIER}, 盈亏比={RR_RATIO}")
print("按 Ctrl+C 可以停止程序。\n")

try:
    while True:
        df = get_latest_data()
        
        if df is not None:
            is_buy_signal, candle, atr = check_signal(df)
            
            current_time = datetime.now().strftime("%H:%M:%S")
            
            if is_buy_signal:
                print(f"\n" + "="*40)
                print(f"🔥 【{current_time}】 发现 H4 交易机会！！！")
                print(f"="*40)
                
                # 1. 计算价格
                sl = candle['low'] - (atr * ATR_MULTIPLIER)
                entry = candle['close']
                dist = entry - sl
                tp = entry + (dist * RR_RATIO)
                
                # 2. 计算仓位 (假设本金 10000, 风险 2%)
                balance = 10000       # <--- 你可以改成你的真实余额
                risk_percent = 0.02   # 2% 风控
                risk_amount = balance * risk_percent
                
                # 假设合约大小是 100 (请根据 XAUUSDm 的实际规格修改!)
                contract_size = 100   
                
                # 计算手数 (保留2位小数)
                lots = risk_amount / (dist * contract_size)
                lots = round(lots, 2)
                
                print(f"📈 品种: {SYMBOL}")
                print(f"💰 建议开仓手数: 【 {lots} 手 】 (基于 ${risk_amount} 风险)")
                print(f"-"*20)
                print(f"   入场 (Entry): {entry:.2f}")
                print(f"   止损 (SL)   : {sl:.2f} (距离 {dist:.2f})")
                print(f"   止盈 (TP)   : {tp:.2f} (盈亏比 {RR_RATIO})")
                print(f"="*40 + "\n")
                
            else:
                # 为了不刷屏，我们用 \r 原地刷新打印
                print(f"⏳ {current_time} 监控中... 暂无信号 (最新价: {df.iloc[-1]['close']:.2f})", end="\r")
        
        # 每 60 秒检查一次
        time.sleep(60)

except KeyboardInterrupt:
    print("\n🛑 监控已停止。")
    mt5.shutdown()