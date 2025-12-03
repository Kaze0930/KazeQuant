from setuptools import setup, find_packages

setup(
    name="KazeQuant",                 # 你的包名（pip install 时用的名字）
    version="0.1.0",                  # 版本号
    author="Kaze",             # 作者（就是你）
    description="My Quant Library",
    
    # 核心功能：自动寻找你写的源代码
    packages=find_packages(),
    
    # 核心功能：自动安装依赖的小弟
    install_requires=[
        "MetaTrader5",
        "pandas",
        "numpy",
        "TA-Lib"  # 如果你用了 TA-Lib，最好也写上
    ],
)