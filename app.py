#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:14:03
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-04 10:55:43
#文件相对于项目的路径   : \AI_env2\app.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
主应用文件
"""

import logging
from flask import Flask, render_template, send_from_directory
from config.app_config import Config
# 修复导入路径 - 从 cors_middleware 导入而不是 cors
from middleware.cors_middleware import setup_cors

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 创建Flask应用
app = Flask(__name__, template_folder='templates')

# 从配置类加载配置
app.config.from_object(Config)

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
