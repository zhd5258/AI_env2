@echo off
echo ================================
echo   智能投标分析系统 - Windows启动
echo ================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查依赖是否安装
echo 检查Python依赖...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo 安装必要的Python依赖...
    pip install -r requirements.txt
)

echo.
echo 启动服务...
echo 服务地址: http://0.0.0.0:8000
echo 按 Ctrl+C 停止服务
echo.

REM 运行主程序
python run.py

pause
