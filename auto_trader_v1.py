import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# ================= 配置区域 =================
SYMBOL = "XAUUSDm"          # 你的品种代码
TIMEFRAME = mt5.TIMEFRAME_H4  # 周期
ATR_MULTIPLIER = 1.5        # 最佳参数
RR_RATIO = 3.0              # 最佳参数
RISK_PERCENT = 0.02         # 单笔风控 2%
MAGIC_NUMBER = 20241125     # 机器人的身份证号
# ===========================================

# 全局变量：记录上一次交易的 K 线时间，防止重复下单
last_traded_time = None

def get_latest_data():
    # 获取 200 根数据用于计算指标
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 200)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_indicators_and_signal(df):
    # 1. 计算 ATR
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()

    # 2. 计算支撑位
    lookback = 20
    prev_lows = df['low'].shift(1).rolling(window=lookback).min()
    tolerance = 1.01

    # 3. 锁定倒数第二根K线 (刚刚收盘确认的那根)
    signal_candle = df.iloc[-2]
    prev_candle = df.iloc[-3]
    
    # 获取收盘那根线的 ATR
    current_atr = signal_candle['atr']

    # --- 信号逻辑 ---
    # A. 支撑位判定
    support_val = prev_lows.iloc[-2]
    at_support = (signal_candle['low'] <= support_val * tolerance) or \
                 (prev_candle['low'] <= support_val * tolerance)
    
    # B. 吞没形态判定
    prev_red = prev_candle['close'] < prev_candle['open']
    curr_green = signal_candle['close'] > signal_candle['open']
    engulfing = (signal_candle['open'] < prev_candle['close']) and \
                (signal_candle['close'] > prev_candle['open'])
    
    is_buy = at_support and prev_red and curr_green and engulfing
    
    return is_buy, signal_candle, current_atr

def execute_trade(entry, sl, tp, lots):
    print(f"🚀 正在发送开仓指令... 手数: {lots}")
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": float(lots),
        "type": mt5.ORDER_TYPE_BUY,
        "price": entry,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 20,
        "magic": MAGIC_NUMBER,
        "comment": "Python Auto H4",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ 下单失败: {result.comment} (代码: {result.retcode})")
        return False
    else:
        print(f"✅ 下单成功! 订单号: {result.order}")
        return True

# ================= 主程序 =================
if not mt5.initialize():
    print("❌ MT5 连接失败")
    quit()

# 自动获取合约规格 (防止算错手数)
symbol_info = mt5.symbol_info(SYMBOL)
if symbol_info is None:
    print(f"❌ 找不到品种 {SYMBOL}")
    quit()
    
contract_size = symbol_info.trade_contract_size
print(f"📡 全自动交易机器人已启动")
print(f"🎯 监控品种: {SYMBOL} | 周期: H4 | 合约大小: {contract_size}")
print(f"🛡️ 风控设置: ATR x {ATR_MULTIPLIER} | 盈亏比 1:{RR_RATIO}")
print("按 Ctrl+C 停止。\n")

try:
    while True:
        # 1. 打印心跳，证明活着
        print(f"⏳ [{datetime.now().strftime('%H:%M:%S')}] 扫描中...", end="\r")
        
        df = get_latest_data()
        
        if df is not None:
            is_signal, candle, atr = calculate_indicators_and_signal(df)
            
            # 获取这根K线的时间戳 (作为唯一标识)
            signal_time = candle.name 
            
            # 2. 发现信号
            if is_signal:
                # 3. 检查是否已经做过这单了
                if last_traded_time == signal_time:
                    # 已经做过了，跳过
                    pass 
                else:
                    print(f"\n\n🔥 发现交易机会! K线时间: {signal_time}")
                    
                    # 4. 计算点位
                    # 实际下单用当前的 Ask 价买入
                    tick = mt5.symbol_info_tick(SYMBOL)
                    entry_price = tick.ask
                    
                    stop_loss = candle['low'] - (atr * ATR_MULTIPLIER)
                    dist = entry_price - stop_loss
                    take_profit = entry_price + (dist * RR_RATIO)
                    
                    # 5. 计算仓位
                    account_info = mt5.account_info()
                    if account_info:
                        balance = account_info.balance
                        risk_amount = balance * RISK_PERCENT
                        
                        # 手数公式：风险 / (止损距离 * 合约大小)
                        lots = risk_amount / (dist * contract_size)
                        lots = round(lots, 2)
                        
                        # 检查最小手数限制 (通常是 0.01)
                        if lots < 0.01: lots = 0.01
                        
                        print(f"💰 账户余额: {balance} | 计划亏损: {risk_amount:.2f}")
                        print(f"📊 建议: Buy @ {entry_price} | SL {stop_loss:.2f} | TP {take_profit:.2f} | 手数 {lots}")
                        
                        # 6. 执行！
                        success = execute_trade(entry_price, stop_loss, take_profit, lots)
                        
                        if success:
                            # 标记这根K线已交易，防止重复
                            last_traded_time = signal_time
                            print("🎉 等待下一个 H4 信号...\n")
                    else:
                        print("❌ 无法获取账户余额，跳过下单。")
            
        # 休息 30 秒再看
        time.sleep(30)

except KeyboardInterrupt:
    print("\n🛑 机器人已停止。")
    mt5.shutdown()