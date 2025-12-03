import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime
import talib

# ================= 🏆 趋势顺势策略 V3.0 =================
SYMBOL = "XAUUSDm"          # 【请核对品种名称】
TIMEFRAME = mt5.TIMEFRAME_M5

# 交易参数
RR_RATIO = 2.0              # 盈亏比 (顺势交易胜率高，盈亏比可稍微保守一点，或者设为2.0)
RISK_PERCENT = 0.02         # 单笔风控
MAGIC_NUMBER = 99999        # 策略ID              
# =======================================================

last_traded_time = None

def get_latest_data():
    # 获取更多数据以计算 200 均线
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 600)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_signal(df):
    # 1. 计算指标
    # ATR
    df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)

    # 移动平均线 (Trend Filter)
    df['sma'] = talib.SMA(df['close'], timeperiod=MA_PERIOD)
    # 计算 RSI (相对强弱指标)
    df['rsi'] = talib.RSI(df['close'], timeperiod=14)
    # 唐奇安通道 (支撑/阻力)
    lookback = 20
    df['donchian_low'] = df['low'].shift(1).rolling(window=lookback).min()
    df['donchian_high'] = df['high'].shift(1).rolling(window=lookback).max()
    df['englufing'] = talib.CDLENGULFING(df['open'], df['high'], df['low'], df['close'])
    # 2. 锁定K线
    signal_candle = df.iloc[-2] # 刚收盘的那根
    prev_candle = df.iloc[-3]   # 前一根
    current_atr = signal_candle['atr']
    current_sma = signal_candle['sma']

    # --- 信号逻辑 ---
    
    # 公共条件：吞没形态
    pattern_value = df['englufing'].iloc[-2]
    engulfing_bull = pattern_value == 100
    engulfing_bear = pattern_value == -100
    # 信号类型：0=无，1=买，-1=卖
    signal_type = 0
    key_level = 0.0

    # 逻辑 A: 做多 (趋势向上 + 回调支撑 + 看涨吞没)
    # 趋势判定: 收盘价 > 200均线
    if signal_candle['close'] > current_sma:
        support_val = signal_candle['donchian_low']
        # 支撑位判定: 最低价接近支撑 (误差 0.5% 以内) 或 刺破支撑
        tolerance = 1.005
        at_support = (signal_candle['low'] <= support_val * tolerance)
        
        if at_support and engulfing_bull:
            signal_type = 1
            key_level = support_val

    # 逻辑 B: 做空 (趋势向下 + 反弹阻力 + 看跌吞没)
    # 趋势判定: 收盘价 < 200均线
    elif signal_candle['close'] < current_sma:
        resistance_val = signal_candle['donchian_high']
        # 阻力位判定: 最高价接近阻力 或 刺破阻力
        tolerance = 0.995 # 向下允许误差
        at_resistance = (signal_candle['high'] >= resistance_val * tolerance)
        
        if at_resistance and engulfing_bear:
            signal_type = -1
            key_level = resistance_val

    return signal_type, signal_candle, current_atr, key_level, current_sma

def execute_trade(signal_type, entry, sl, tp, lots):
    order_type = mt5.ORDER_TYPE_BUY if signal_type == 1 else mt5.ORDER_TYPE_SELL
    type_str = "BUY" if signal_type == 1 else "SELL"
    
    print(f"\n🚀 [实盘] 发送 {type_str} 指令... Lots: {lots}")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": float(lots),
        "type": order_type,
        "price": entry,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 50,
        "magic": MAGIC_NUMBER,
        "comment": f"Py Trend V3 {type_str}",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ 下单失败: {result.comment} (Code: {result.retcode})")
        return False
    return True

# ================= 🚀 主程序 =================
if not mt5.initialize(): 
    print("❌ MT5 初始化失败")
    quit()

symbol_info = mt5.symbol_info(SYMBOL)
if symbol_info is None: print(f"❌ 找不到 {SYMBOL}"); quit()

print(f"🏆 顺势吞没策略 V3.0 (多空双开) 已启动")
print(f"⚙️  MA趋势: {MA_PERIOD} | ATR x {ATR_MULTIPLIER} | RR {RR_RATIO}")
print("-" * 60)

try:
    while True:
        # 简单时间检查
        current_h = datetime.now().hour
        is_trading_time = START_HOUR <= current_h < END_HOUR
        
        status = "🟢 监控" if is_trading_time else "😴 休眠"
        now_str = datetime.now().strftime('%H:%M:%S')

        df = get_latest_data()
        
        if df is not None:
            sig_type, candle, atr, level, sma = calculate_signal(df)
            signal_time = candle.name
            
            # 获取实时价格
            tick = mt5.symbol_info_tick(SYMBOL)
            if not tick: continue
            
            # 动态打印信息
            current_price = tick.bid # 默认看买价
            trend_str = "📈 多头" if current_price > sma else "📉 空头"
            
            print(f"[{now_str}] {status} | 趋势: {trend_str} | 现价: {current_price:.2f} | MA{MA_PERIOD}: {sma:.2f}   ", end="\r")

            if is_trading_time and sig_type != 0:
                if last_traded_time == signal_time:
                    pass
                else:
                    print(f"\n\n🔥 信号触发! 方向: {'做多' if sig_type==1 else '做空'} | 时间: {signal_time}")
                    
                    # 计算止盈止损
                    if sig_type == 1: # Buy
                        entry_price = tick.ask
                        stop_loss = candle['low'] - (atr * ATR_MULTIPLIER)
                        dist = entry_price - stop_loss
                        take_profit = entry_price + (dist * RR_RATIO)
                    else: # Sell
                        entry_price = tick.bid
                        stop_loss = candle['high'] + (atr * ATR_MULTIPLIER)
                        dist = stop_loss - entry_price
                        take_profit = entry_price - (dist * RR_RATIO)

                    # 风控计算
                    if dist <= 0:
                        print("⚠️ 止损距离计算异常，跳过")
                    else:
                        account = mt5.account_info()
                        risk_amount = account.balance * RISK_PERCENT
                        contract_size = symbol_info.trade_contract_size
                        lots = risk_amount / (dist * contract_size)
                        lots = round(lots, 2)
                        if lots < 0.01: lots = 0.01

                        print(f"✅ 计划: {entry_price} | SL {stop_loss:.2f} | TP {take_profit:.2f}")
                        
                        if execute_trade(sig_type, entry_price, stop_loss, take_profit, lots):
                            last_traded_time = signal_time
                            print("🎉 订单已发送!\n")
            
        time.sleep(5)

except KeyboardInterrupt:
    mt5.shutdown()
    print("\n🛑 程序已停止。")