#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:26:03
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 14:31:35
#文件相对于项目的路径   : \AI_env2\config\app_config.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
应用配置文件
"""

import os
from pathlib import Path

class Config:
    # 应用配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB限制
    
    # 数据库配置
    DATABASE_URL = 'sqlite:///./tender_evaluation.db'
    
    # 创建上传目录
    UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
