#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-18 08:22:38
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-11-01 12:19:05
# 文件相对于项目的路径   : \AI_env2\config\app_config.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
应用配置文件
"""

import os
from pathlib import Path
from modules.runtime_config import load_config


class Config:
    # 应用配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'uploads'
    )

    # 从运行时配置加载文件上传大小限制
    # 设置一个足够大的值，让我们的自定义单文件大小检查起作用
    # 1GB应该足够大，以允许我们进行自定义检查
    runtime_config = load_config()
    MAX_CONTENT_LENGTH = 1024 * 1024 * 1024  # 1GB

    # 数据库配置 - 修复：使用与models/database.py中一致的路径
    DATABASE_URL = 'sqlite:///' + os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'db', 'tender_evaluation.db')
    )

    # 创建上传目录
    UPLOADS_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', 'uploads'
    )
    Path(UPLOADS_DIR).mkdir(parents=True, exist_ok=True)

    # RAG优化配置
    RAG_ENABLED = os.environ.get('RAG_ENABLED', 'false').lower() == 'true'
    RAG_EMBEDDING_MODEL = os.environ.get('RAG_EMBEDDING_MODEL', 'qwen3-embedding:4b')
    RAG_RERANKER_MODEL = os.environ.get(
        'RAG_RERANKER_MODEL', 'dengcao/Qwen3-Reranker-8B:Q5_K_M'
    )
    RAG_OLLAMA_HOST = os.environ.get('RAG_OLLAMA_HOST', 'http://localhost:11434')
    RAG_CHUNK_SIZE = int(os.environ.get('RAG_CHUNK_SIZE', '1000'))
    RAG_CHUNK_OVERLAP = int(os.environ.get('RAG_CHUNK_OVERLAP', '200'))
    RAG_MAX_GROUP_SIZE = int(os.environ.get('RAG_MAX_GROUP_SIZE', '5'))
