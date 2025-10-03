#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:39:07
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 14:39:10
#文件相对于项目的路径   : \AI_env2\run.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
应用启动脚本
"""

import os
import sys
import subprocess
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """检查必要的依赖"""
    try:
        import flask
        import sqlalchemy
        print("✓ Flask和SQLAlchemy已安装")
        return True
    except ImportError as e:
        print(f"✗ 缺少必要的依赖: {e}")
        return False

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(os.path.join('logs', 'app.log'), encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )

def main():
    """主函数"""
    print("================================")
    print("  智能投标分析系统 - Flask版本")
    print("================================")
    print()
    
    # 检查Python版本
    if sys.version_info < (3, 8):
        print("错误: 需要Python 3.8或更高版本")
        sys.exit(1)
    
    # 检查依赖
    if not check_dependencies():
        print("正在安装依赖...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
            print("依赖安装完成")
        except subprocess.CalledProcessError:
            print("依赖安装失败")
            sys.exit(1)
    
    # 设置日志
    setup_logging()
    
    # 启动应用
    print("启动服务...")
    print("服务地址: http://0.0.0.0:8000")
    print("按 Ctrl+C 停止服务")
    print()
    
    try:
        from app import app
        app.run(host='0.0.0.0', port=8000, debug=True)
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"启动服务时出错: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
