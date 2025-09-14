#!/bin/bash
echo "================================"
echo "  智能投标分析系统 - Linux/Mac启动"
echo "================================"
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python 3.8+"
    exit 1
fi

# 检查依赖是否安装
echo "检查Python依赖..."
if ! python3 -c "import fastapi" &> /dev/null; then
    echo "安装必要的Python依赖..."
    pip3 install -r requirements.txt
fi

echo
echo "启动服务..."
echo "服务地址: http://0.0.0.0:8000"
echo "按 Ctrl+C 停止服务"
echo

# 运行主程序
python3 run.py