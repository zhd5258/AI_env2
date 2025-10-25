#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
数据库迁移脚本 - 添加bid_document表的updated_at列
"""

import os
import sys
import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, MetaData, text
from sqlalchemy.dialects.sqlite.base import SQLiteDialect

# 数据库URL
DATABASE_URL = 'sqlite:///' + os.path.abspath(
    os.path.join(project_root, 'db', 'tender_evaluation.db')
)

# 创建引擎
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})


def migrate_database():
    """执行数据库迁移"""
    print('开始数据库迁移...')

    # 检查数据库文件是否存在
    db_path = DATABASE_URL.replace('sqlite:///', '')
    if not os.path.exists(db_path):
        print('数据库文件不存在，将创建新数据库...')
        # 在这里我们应该导入Base并创建所有表，但由于导入问题，我们只打印消息
        print('请先启动应用程序以创建数据库结构!')
        return

    # 连接数据库
    print('连接到数据库...')

    # 反射现有表结构
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # 检查bid_document表是否存在
    if 'bid_document' not in metadata.tables:
        print('bid_document表不存在!')
        return

    # 获取现有bid_document表
    bid_document_table = metadata.tables['bid_document']

    # 检查updated_at列是否已存在
    if 'updated_at' in bid_document_table.c:
        print('updated_at列已存在，无需迁移!')
        return

    # 添加updated_at列
    print('添加updated_at列...')

    # 对于SQLite，我们需要使用ALTER TABLE语句添加列
    if isinstance(engine.dialect, SQLiteDialect):
        # SQLite的ALTER TABLE语法相对简单
        sql = 'ALTER TABLE bid_document ADD COLUMN updated_at DATETIME'
        with engine.connect() as conn:
            conn.execute(text(sql))
            conn.commit()
        print('updated_at列添加成功!')
    else:
        print('不支持的数据库类型!')

    print('数据库迁移完成!')


if __name__ == '__main__':
    migrate_database()
