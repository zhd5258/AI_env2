#!/usr/bin/env python3
"""
跨平台启动脚本
在Windows和Linux系统上都能运行main.py
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """主函数"""
    print("=== 智能投标分析系统 ===")
    print("正在启动服务...")
    
    # 检查必要的目录是否存在
    required_dirs = ['uploads', 'static', 'templates']
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            Path(dir_name).mkdir(exist_ok=True)
            print(f"创建目录: {dir_name}")
    
    # 设置Python路径
    current_dir = Path(__file__).parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    
    # 启动FastAPI服务
    try:
        print("启动FastAPI服务器...")
        print("服务地址: http://0.0.0.0:8000")
        print("按 Ctrl+C 停止服务")
        print("-" * 50)
        
        # 直接导入并运行main模块
        from main import app
        import uvicorn
        
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info",
            access_log=False
        )
        
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动服务时出错: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()