# 1. 导入工具箱
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# 设置画图风格，好看一点
sns.set(style="darkgrid")

# 2. 获取数据：下载黄金期货 (Gold Futures) 最近5年的数据
print("正在下载数据...")
data = yf.download("GC=F", period="5y", progress=False)

# 3. 数据处理：计算“日收益率”
# 公式：(今天收盘价 - 昨天收盘价) / 昨天收盘价
# 这就是在把价格变成“时间序列”的涨跌幅
data['Return'] = data['Close'].pct_change() * 100 # 乘以100变成百分比
data.dropna(inplace=True) # 去掉第一天（因为第一天没有前一天，算不出涨跌）

# --- 开始画图 ---

plt.figure(figsize=(15, 10))

# 图 1：波动率聚类 (验证“同分布”假设)
# 看看收益率是不是像心电图一样，有时候平静，有时候疯狂跳动？
plt.subplot(2, 1, 1)
plt.plot(data.index, data['Return'], color='gold', lw=1)
plt.title('Gold Daily Returns (5 Years) - Checking for Volatility Clustering', fontsize=14)
plt.ylabel('Daily Return (%)')
plt.axhline(0, color='black', linestyle='--', linewidth=0.5)

# 图 2：自相关性散点图 (验证“独立性”假设)
# X轴是昨天的涨跌，Y轴是今天的涨跌
# 如果有规律，应该是一条线；如果没规律，应该是一团乱麻
plt.subplot(2, 1, 2)
# 创建“昨天的数据”列 (Lag 1)
data['Yesterday_Return'] = data['Return'].shift(1)
plt.scatter(data['Yesterday_Return'], data['Return'], alpha=0.5, color='royalblue', s=10)
plt.title('Yesterday vs. Today (Scatter Plot) - Checking for Independence', fontsize=14)
plt.xlabel('Yesterday Return (%)')
plt.ylabel('Today Return (%)')

# 画一条十字线辅助观看
plt.axhline(0, color='black', linestyle='--', linewidth=1)
plt.axvline(0, color='black', linestyle='--', linewidth=1)

plt.tight_layout()
plt.show()