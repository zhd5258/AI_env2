#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
日志配置模块
统一配置应用的日志记录功能
"""

import logging
import logging.handlers
import os
from pathlib import Path


def setup_logging():
    """设置日志配置"""
    # 确保logs目录存在
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)

    # 创建formatter，与终端输出保持一致
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # 创建统一的文件处理器
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / 'application.log',
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 添加处理器到根logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # 确保所有模块的日志都传播到根logger，不创建独立的处理器
    modules = [
        'modules.price_extraction_manager',
        'modules.local_ai_analyzer',
        'modules.unified_comprehensive_calculator',
        'modules.resource_monitor',
        'app',
    ]

    for module_name in modules:
        module_logger = logging.getLogger(module_name)
        module_logger.propagate = True  # 传播到根logger
        # 移除模块特定的处理器
        for handler in module_logger.handlers[:]:
            module_logger.removeHandler(handler)

    return root_logger


def get_logger(name: str):
    """
    获取指定名称的logger

    Args:
        name: logger名称

    Returns:
        logging.Logger: 配置好的logger实例
    """
    return logging.getLogger(name)
