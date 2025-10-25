#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
日志配置模块
统一配置应用的日志记录功能
"""

import logging
import logging.handlers
import os
import sys
import time
from pathlib import Path


def setup_logging(log_to_file=True):
    """
    设置日志配置
    
    Args:
        log_to_file: 是否将日志输出到文件，默认为True
    """
    # 确保logs目录存在（使用项目根目录）
    project_root = Path(__file__).parent.parent
    log_dir = project_root / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    # 创建更详细的formatter
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # 简洁的控制台formatter
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 配置根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 控制台只显示INFO及以上级别
    console_handler.setFormatter(console_formatter)
    
    # 添加处理器到根logger
    root_logger.addHandler(console_handler)
    
    if log_to_file:
        # 创建当前日期的日志文件名
        current_date = time.strftime('%Y-%m-%d')
        log_filename = f'application_{current_date}.log'
        
        # 创建统一的文件处理器 - 所有级别日志
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / log_filename,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_handler.setFormatter(detailed_formatter)
        
        # 创建错误日志文件处理器 - 只记录ERROR及以上级别
        error_file_handler = logging.handlers.RotatingFileHandler(
            log_dir / f'error_{current_date}.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8',
        )
        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(detailed_formatter)
        
        # 添加文件处理器到根logger
        root_logger.addHandler(file_handler)
        root_logger.addHandler(error_file_handler)

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
