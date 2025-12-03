import MetaTrader5 as mt5
import pandas as pd
import time
from datetime import datetime

# ================= M5 剥头皮配置 (固定点差版) =================
SYMBOL = "XAUUSDm"          # 你的品种
TIMEFRAME = mt5.TIMEFRAME_M5  # M5 周期
ATR_MULTIPLIER = 0.5        # 极窄止损
RR_RATIO = 2.0              # 2倍盈亏比
RISK_PERCENT = 0.02         # 单笔风控 2%
MAGIC_NUMBER = 55555        # 机器人ID
# ============================================================

last_traded_time = None

def get_latest_data():
    # 取 100 根就够了
    rates = mt5.copy_rates_from_pos(SYMBOL, TIMEFRAME, 0, 100)
    if rates is None: return None
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    df.set_index('time', inplace=True)
    return df

def calculate_signal(df):
    # 1. 计算 ATR
    df['h-l'] = df['high'] - df['low']
    df['h-pc'] = abs(df['high'] - df['close'].shift(1))
    df['l-pc'] = abs(df['low'] - df['close'].shift(1))
    df['tr'] = df[['h-l', 'h-pc', 'l-pc']].max(axis=1)
    df['atr'] = df['tr'].rolling(window=14).mean()

    # 2. 支撑位 (看过去 20 根)
    lookback = 20
    prev_lows = df['low'].shift(1).rolling(window=lookback).min()
    df['ema_200'] = df['close'].ewm(span=200, adjust=False).mean()
    tolerance = 1.005 

    # 3. 锁定倒数第二根 (刚收盘的)
    signal_candle = df.iloc[-2]
    prev_candle = df.iloc[-3]
    current_atr = signal_candle['atr']

    # --- 信号逻辑 ---
    support_val = prev_lows.iloc[-2]
    at_support = (signal_candle['low'] <= support_val * tolerance) or \
                 (prev_candle['low'] <= support_val * tolerance)
    
    prev_red = prev_candle['close'] < prev_candle['open']
    curr_green = signal_candle['close'] > signal_candle['open']
    engulfing = (signal_candle['open'] < prev_candle['close']) and \
                (signal_candle['close'] > prev_candle['open'])
    
    is_buy = at_support and prev_red and curr_green and engulfing
    
    return is_buy, signal_candle, current_atr

def execute_trade(entry, sl, tp, lots):
    print(f"🚀 [M5极速] 发送开仓指令... 手数: {lots}")
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": float(lots),
        "type": mt5.ORDER_TYPE_BUY,
        "price": entry,
        "sl": float(sl),
        "tp": float(tp),
        "deviation": 50,          # 【注意】因为你是3位小数，我把滑点容忍度调大到了 50 (0.05美金)
        "magic": MAGIC_NUMBER,
        "comment": "Python M5 Scalp",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"❌ 下单失败: {result.comment} (代码: {result.retcode})")
        return False
    return True

# ================= 主程序 =================
if not mt5.initialize(): quit()

symbol_info = mt5.symbol_info(SYMBOL)
if symbol_info is None: print(f"❌ 找不到 {SYMBOL}"); quit()
contract_size = symbol_info.trade_contract_size

print(f"🏎️ M5 剥头皮机器人启动 (无点差限制版) | ATR x {ATR_MULTIPLIER} | RR {RR_RATIO}")
print(f"📊 当前最小报价单位: {symbol_info.point} (3位小数模式)")

try:
    while True:
        print(f"⚡ M5 扫描中... [{datetime.now().strftime('%H:%M:%S')}]", end="\r")
        
        df = get_latest_data()
        
        if df is not None:
            is_signal, candle, atr = calculate_signal(df)
            signal_time = candle.name 
            
            if is_signal:
                if last_traded_time == signal_time:
                    pass 
                else:
                    print(f"\n\n🔥 M5 信号出现! K线: {signal_time}")
                    
                    # 获取最新买价
                    tick = mt5.symbol_info_tick(SYMBOL)
                    entry_price = tick.ask
                    
                    # 计算点位
                    stop_loss = candle['low'] - (atr * ATR_MULTIPLIER)
                    dist = entry_price - stop_loss
                    
                    # M5 唯一保留的风控：如果ATR太小导致止损距离小于 0.05 美金，不做 (防止MT5报错)
                    if dist < 0.05: 
                         print("⚠️ 波动太小(ATR过低)，放弃交易。")
                    else:
                        take_profit = entry_price + (dist * RR_RATIO)
                        
                        account = mt5.account_info()
                        risk_amount = account.balance * RISK_PERCENT
                        lots = risk_amount / (dist * contract_size)
                        lots = round(lots, 2)
                        
                        # 检查最小手数
                        if lots < 0.01: lots = 0.01

                        print(f"✅ 信号确认。Buy @ {entry_price} | SL {stop_loss:.2f} | Lots {lots}")
                        
                        if execute_trade(entry_price, stop_loss, take_profit, lots):
                            last_traded_time = signal_time
                            print("🎉 下单完成，准备下一单...\n")
            
        time.sleep(10)

except KeyboardInterrupt:
    mt5.shutdown()