#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-18 08:22:38
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-18 13:10:30
# 文件相对于项目的路径   : \AI_env2\app.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#


import logging
import sys
from pathlib import Path
from flask import Flask, render_template, send_from_directory
from config.app_config import Config

from middleware.cors_middleware import setup_cors
from modules.runtime_config import load_config

# 配置日志
import os
import logging.handlers

# 确保logs目录存在
log_dir = 'logs'
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# 创建formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# 配置根logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# 清除现有的处理器
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# 创建控制台处理器
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(formatter)

# 创建文件处理器
file_handler = logging.handlers.RotatingFileHandler(
    os.path.join(log_dir, 'application.log'),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5,
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# 添加处理器到根logger
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# 检查系统维护锁定文件
LOCK_FILE = Path('system_maintenance.lock')
if LOCK_FILE.exists():
    print('=' * 50)
    print('系统维护锁定中！')
    print('检测到系统维护锁定文件，禁止自动启动主程序。')
    print('请在确认系统优化或纠错完成后手动移除锁定文件：')
    print(f'  {LOCK_FILE.absolute()}')
    print('或使用命令：python tools/system_maintenance_lock.py unlock')
    print('=' * 50)
    sys.exit(1)

# 创建Flask应用
app = Flask(__name__, template_folder='templates')

# 从配置类加载配置
app.config.from_object(Config)

# 从运行时配置加载文件上传大小限制
runtime_config = load_config()
app.config['MAX_CONTENT_LENGTH'] = runtime_config.get(
    'max_content_length', 1000 * 1024 * 1024
)

# 启动资源监控器
from modules.resource_monitor import start_resource_monitoring

start_resource_monitoring()

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
    from routes.page_routes import router as page_router
    from routes.settings_routes import router as settings_router

    # 注册路由
    app.register_blueprint(file_router)
    app.register_blueprint(project_router)
    app.register_blueprint(analysis_router)
    app.register_blueprint(config_router)
    app.register_blueprint(export_router)
    app.register_blueprint(page_router)
    app.register_blueprint(settings_router)


# 注册路由
register_routes()


@app.route('/')
def index():
    """首页"""
    return render_template('index.html')


@app.route('/static/<path:filename>')
def static_files(filename):
    """提供静态文件服务"""
    return send_from_directory('static', filename)


if __name__ == '__main__':
    # 记录应用启动日志
    logging.info('应用启动中...')

    # 再次检查锁定文件（双重保险）
    if LOCK_FILE.exists():
        print('=' * 50)
        print('系统维护锁定中！')
        print('检测到系统维护锁定文件，禁止自动启动主程序。')
        print('请在确认系统优化或纠错完成后手动移除锁定文件：')
        print(f'  {LOCK_FILE.absolute()}')
        print('或使用命令：python tools/system_maintenance_lock.py unlock')
        print('=' * 50)
        sys.exit(1)

    app.run(host='0.0.0.0', port=8000, debug=False)
