#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:33:22
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 14:33:24
#文件相对于项目的路径   : \AI_env2\middleware\cors_middleware.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
CORS中间件
"""

from flask import Flask
from flask_cors import CORS

def setup_cors(app: Flask):
    """设置CORS"""
    CORS(app)
