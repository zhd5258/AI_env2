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
    
    # 增加文件上传大小限制到500MB
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB限制，增加文件上传大小限制
    
    # 数据库配置
    DATABASE_URL = 'sqlite:///./db/tender_evaluation.db'
    
    # 创建上传目录
    UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'uploads')
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)
