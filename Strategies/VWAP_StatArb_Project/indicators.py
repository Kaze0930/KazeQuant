import pandas as pd
import numpy as np
def add_vwap_bands(df,std_dev=2.0):
    """
    计算 VWAP 及其上下轨道
    """
    df = df.copy()
    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['pv'] = df['tp'] * df['tick_volume']
    df['tp_sq_v'] = (df['tp'] ** 2) * df['tick_volume']
    daily_groups = df.groupby(df.index.date)
    df['cum_pv'] = daily_groups['pv'].cumsum()
    df['cum_vol'] = daily_groups['tick_volume'].cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    
    # 计算标准差
    mean_of_sq = daily_groups['tp_sq_v'].cumsum() / df['cum_vol']
    mean_sq = (df['vwap'] ** 2)
    df['var'] = mean_of_sq - mean_sq
    df['var'] = df['var'].clip(lower=0)  # 防止负值
    df['std_dev'] = np.sqrt(df['var'])
    
    # 上下轨道
    df['vwap_upper'] = df['vwap'] + (std_dev * df['std_dev'])
    df['vwap_lower'] = df['vwap'] - (std_dev * df['std_dev'])
    
    return df