#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-25 17:37:27
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-25 17:37:30
# 文件相对于项目的路径   : \AI_ENV2\db\check_database_structure.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
检查数据库结构脚本
"""

import os
import sys

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine, MetaData

# 数据库URL
DATABASE_URL = 'sqlite:///' + os.path.abspath(
    os.path.join(project_root, 'db', 'tender_evaluation.db')
)

# 创建引擎
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})


def check_database_structure():
    """检查数据库结构"""
    print('检查数据库结构...')

    # 检查数据库文件是否存在
    db_path = DATABASE_URL.replace('sqlite:///', '')
    if not os.path.exists(db_path):
        print('数据库文件不存在!')
        return

    # 连接数据库
    print('连接到数据库...')

    # 反射现有表结构
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # 检查所有表
    print('数据库中的表:')
    for table_name in metadata.tables:
        print(f'  - {table_name}')

    # 检查bid_document表结构
    if 'bid_document' in metadata.tables:
        bid_document_table = metadata.tables['bid_document']
        print('\nbid_document表结构:')
        for column in bid_document_table.c:
            print(f'  - {column.name}: {column.type}')
    else:
        print('bid_document表不存在!')


if __name__ == '__main__':
    check_database_structure()
