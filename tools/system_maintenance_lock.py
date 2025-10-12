#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统维护锁定工具
用于在系统优化或纠错后阻止自动启动主程序
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 锁定文件路径
LOCK_FILE = Path('system_maintenance.lock')


def create_lock():
    """
    创建系统维护锁定文件
    """
    try:
        # 创建锁定文件并写入创建时间
        with open(LOCK_FILE, 'w', encoding='utf-8') as f:
            f.write(f'系统维护锁定文件\n创建时间: {datetime.now().isoformat()}\n')
            f.write('在系统优化或纠错后，禁止自动启动主程序\n')
            f.write('请手动检查系统状态并移除该文件以允许程序启动\n')

        logger.info(f'已创建系统维护锁定文件: {LOCK_FILE}')
        logger.warning('系统已锁定，主程序将无法自动启动！')
        return True
    except Exception as e:
        logger.error(f'创建锁定文件失败: {e}')
        return False


def remove_lock():
    """
    移除系统维护锁定文件
    """
    try:
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()
            logger.info(f'已移除系统维护锁定文件: {LOCK_FILE}')
            logger.info('系统维护完成，允许主程序启动')
            return True
        else:
            logger.info('未找到系统维护锁定文件')
            return True
    except Exception as e:
        logger.error(f'移除锁定文件失败: {e}')
        return False


def check_lock():
    """
    检查是否存在系统维护锁定文件
    """
    if LOCK_FILE.exists():
        try:
            with open(LOCK_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f'系统维护锁定文件存在:\n{content}')
            return True
        except Exception as e:
            logger.error(f'读取锁定文件失败: {e}')
            return True  # 出错时仍然认为锁定存在以确保安全
    else:
        logger.info('系统维护锁定文件不存在，允许启动')
        return False


def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description='系统维护锁定工具')
    parser.add_argument(
        'action',
        choices=['lock', 'unlock', 'check'],
        help='操作类型: lock(创建锁定), unlock(移除锁定), check(检查锁定状态)',
    )

    args = parser.parse_args()

    if args.action == 'lock':
        return create_lock()
    elif args.action == 'unlock':
        return remove_lock()
    elif args.action == 'check':
        return check_lock()


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
