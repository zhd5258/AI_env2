#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
临时文件清理工具
用于清理上传文件和分析过程中产生的临时文件，但保留根目录下的设置JSON文件
"""

import os
import shutil
import logging
from pathlib import Path
import time
import argparse

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 导入数据库模块
try:
    from modules.database import (
        SessionLocal,
        TenderProject,
        BidDocument,
        AnalysisResult,
        ScoringRule,
        ScoreModificationHistory,
        ProjectAuditLog,
    )

    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False
    logger.warning('数据库模块不可用，跳过数据库清理功能')

# 定义需要保留的根目录JSON文件
ROOT_JSON_FILES = [
    'config.json',
    'settings.json',
    'runtime_config.json',
    'MinerU_API_token.txt',  # 虽然是txt但也是配置文件
]


def clean_directory(directory_path, remove_empty_dir=True, retry_count=3):
    """
    清理指定目录下的所有文件

    Args:
        directory_path (str): 要清理的目录路径
        remove_empty_dir (bool): 是否在清空后删除空目录
        retry_count (int): 删除文件失败时的重试次数
    """
    directory = Path(directory_path)

    if not directory.exists():
        logger.info(f'目录 {directory_path} 不存在，无需清理')
        return

    if not directory.is_dir():
        logger.warning(f'{directory_path} 不是一个目录')
        return

    logger.info(f'开始清理目录: {directory_path}')

    # 删除目录下的所有文件和子目录
    for item in directory.iterdir():
        for attempt in range(retry_count):
            try:
                if item.is_file():
                    item.unlink()
                    logger.info(f'已删除文件: {item}')
                    break
                elif item.is_dir():
                    shutil.rmtree(item)
                    logger.info(f'已删除目录: {item}')
                    break
            except Exception as e:
                logger.warning(
                    f'删除 {item} 时出错 (尝试 {attempt + 1}/{retry_count}): {e}'
                )
                if attempt < retry_count - 1:
                    time.sleep(1)  # 等待1秒后重试
                else:
                    logger.error(f'无法删除 {item}，可能正在被其他程序使用')

    # 如果目录为空且设置为删除空目录，则删除目录本身
    if remove_empty_dir and not any(directory.iterdir()):
        try:
            directory.rmdir()
            logger.info(f'已删除空目录: {directory_path}')
        except Exception as e:
            logger.error(f'删除空目录 {directory_path} 时出错: {e}')


def is_root_json_file(file_path):
    """
    判断是否为需要保留的根目录JSON文件

    Args:
        file_path (Path): 文件路径

    Returns:
        bool: 如果是需要保留的根目录JSON文件返回True，否则返回False
    """
    filename = file_path.name
    return filename in ROOT_JSON_FILES


def clean_root_json_files():
    """
    清理根目录下非必要的JSON文件（保留指定的配置文件）
    """
    root_dir = Path('.')
    logger.info('检查根目录下的JSON文件...')

    for item in root_dir.iterdir():
        if item.is_file() and (
            item.suffix.lower() == '.json' or item.suffix.lower() == '.txt'
        ):
            if not is_root_json_file(item):
                try:
                    item.unlink()
                    logger.info(f'已删除根目录下的非必要文件: {item}')
                except Exception as e:
                    logger.error(f'删除 {item} 时出错: {e}')
            else:
                logger.info(f'保留根目录下的配置文件: {item}')


def clean_database():
    """
    清空数据库中的所有数据表
    """
    if not DATABASE_AVAILABLE:
        logger.warning('数据库模块不可用，跳过数据库清理')
        return

    try:
        logger.info('开始清空数据库...')
        db = SessionLocal()

        # 按照外键依赖顺序删除数据
        # 先删除有外键依赖的表
        db.query(ScoreModificationHistory).delete()
        db.query(ProjectAuditLog).delete()
        db.query(AnalysisResult).delete()
        db.query(ScoringRule).delete()
        db.query(BidDocument).delete()
        # 最后删除主表
        db.query(TenderProject).delete()

        db.commit()
        logger.info('数据库清空完成')
    except Exception as e:
        logger.error(f'清空数据库时出错: {e}')
        if 'db' in locals():
            db.rollback()
    finally:
        if 'db' in locals():
            db.close()


def main(clear_database=False):
    """主函数"""
    logger.info('开始执行临时文件清理...')

    # 定义需要清理的目录
    directories_to_clean = [
        'temp/uploads',
        'temp/md',
        'uploads',
        'temp/mineru',  # 添加对temp/mineru目录的清理
        # 如果有其他临时目录也可以添加到这里
    ]

    # 清理指定目录
    for directory in directories_to_clean:
        clean_directory(directory)

    # 清理根目录下的非必要JSON文件
    clean_root_json_files()

    # 如果指定了清空数据库选项，则清空数据库
    if clear_database:
        clean_database()

    logger.info('临时文件清理完成!')


if __name__ == '__main__':
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='临时文件清理工具')
    parser.add_argument(
        '--clear-database', action='store_true', help='是否清空数据库（默认不清理）'
    )

    args = parser.parse_args()

    main(clear_database=args.clear_database)
