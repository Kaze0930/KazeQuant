import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt

# 1. 连接到 MT5 终端
if not mt5.initialize():
    print("初始化失败, 错误代码 =", mt5.last_error())
    quit()
else:
    print("成功连接到 MT5 终端！")

# 2. 设置参数
symbol = "XAUUSDm"  # 你的品种名称，有的平台可能是 "GOLD" 或 "XAUUSD.m"
timeframe = mt5.TIMEFRAME_D1  # 周期：D1 (日线)
count = 1000  # 获取过去 1000 根 K 线

# 3. 获取数据
# 从当前时间开始，往前获取 count 根 K 线
rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)

# 4. 关闭连接 (拿到数据就可以断开了)
mt5.shutdown()

# --- 数据处理 ---

if rates is None or len(rates) == 0:
    print(f"哎呀，没获取到数据！请检查品种名称 '{symbol}' 是否正确（有些平台叫 GOLD）。")
else:
    print(f"成功获取了 {len(rates)} 条真实数据！")

    # 把数据转换成 Pandas 表格 (DataFrame)
    df = pd.DataFrame(rates)
    
    #哪怕是 MT5 的原始数据，时间也是“秒数” (Unix Timestamp)，要转成人类能看懂的时间
    df['time'] = pd.to_datetime(df['time'], unit='s')
    
    # 只要这几列有用的
    df = df[['time', 'open', 'high', 'low', 'close', 'tick_volume']]
    
    # 设置时间为索引
    df.set_index('time', inplace=True)

    # 打印前5行看看
    print("\n数据预览：")
    print(df.tail())

    # --- 顺便画个图验证一下 ---
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['close'], label=symbol)
    plt.title(f'Real Market Data from MT5: {symbol}')
    plt.xlabel('Date')
    plt.ylabel('Price')
    plt.legend()
    plt.grid(True)
    plt.show()
import seaborn as sns
import matplotlib.pyplot as plt

# --- 接着刚才的 df 继续写 ---

# 1. 计算真实的日收益率
# pct_change() 计算 (今天-昨天)/昨天
df['Return'] = df['close'].pct_change() * 100 
df.dropna(inplace=True) # 去掉第一行空数据

# 2. 准备“昨天”的数据用来对比
df['Yesterday_Return'] = df['Return'].shift(1)
df.dropna(inplace=True)

# --- 画图揭秘 ---
plt.figure(figsize=(12, 10))

# 图1: 真实市场的波动率聚集 (Volatility Clustering)
plt.subplot(2, 1, 1)
plt.plot(df.index, df['Return'], color='gold', lw=1)
plt.title('Real XAUUSD Daily Returns - Notice the "Panic" Periods', fontsize=14)
plt.ylabel('Daily Return (%)')
plt.axhline(0, color='black', linestyle='--', linewidth=0.5)

# 图2: 真实市场的独立性验证 (Scatter Plot)
plt.subplot(2, 1, 2)
sns.scatterplot(x=df['Yesterday_Return'], y=df['Return'], alpha=0.5, color='royalblue', s=15)
plt.title('Yesterday vs Today (Real Data) - Can you find a pattern?', fontsize=14)
plt.xlabel('Yesterday Return (%)')
plt.ylabel('Today Return (%)')

# 添加辅助线
plt.axhline(0, color='black', linestyle='--', linewidth=1)
plt.axvline(0, color='black', linestyle='--', linewidth=1)

plt.tight_layout()
plt.show()

# --- 算一个具体的数值：相关系数 ---
correlation = df['Return'].corr(df['Yesterday_Return'])
print(f"------------------------------------------------")
print(f"昨天的涨跌和今天的涨跌，相关系数是: {correlation:.4f}")
print(f"------------------------------------------------")
if abs(correlation) < 0.05:
    print("结论：几乎完全不相关！昨天涨跌对预测今天没啥用。")
else:
    print("结论：有一点点微弱的关系，但很难直接用来赚钱。")