#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:14:03
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 20:10:40
#文件相对于项目的路径   : \AI_env2\app.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#


import os
import sys
import logging
from pathlib import Path
from flask import Flask, render_template, send_from_directory

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入配置
from config.app_config import Config

# 导入中间件
from middleware.cors_middleware import setup_cors

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join('logs', 'analysis.log'), encoding='utf-8'),
        logging.StreamHandler(),
    ]
)

# 创建Flask应用
app = Flask(__name__, template_folder='templates')
app.config.from_object(Config)

# 设置中间件
setup_cors(app)

def register_routes():
    """注册路由"""
    # 导入路由模块
    from routes.file_routes import router as file_router
    from routes.project_routes import router as project_router
    from routes.analysis_routes import router as analysis_router
    from routes.config_routes import router as config_router
    from routes.export_routes import router as export_router
    from routes.rules_routes import router as rules_router
    from routes.page_routes import router as page_router
    
    # 注册路由
    app.register_blueprint(file_router)
    app.register_blueprint(project_router)
    app.register_blueprint(analysis_router)
    app.register_blueprint(config_router)
    app.register_blueprint(export_router)
    app.register_blueprint(rules_router)
    app.register_blueprint(page_router)

# 注册路由
register_routes()

@app.route('/')
def index():
    """首页"""
    return render_template('index.html')

@app.route('/public/<path:filename>')
def static_files(filename):
    """提供静态文件服务"""
    return send_from_directory('public', filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
