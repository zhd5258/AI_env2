#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
验证数据库迁移脚本
"""

import os
import sys
import sqlite3

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 数据库路径
DB_PATH = os.path.abspath(os.path.join(project_root, 'db', 'tender_evaluation.db'))


def verify_migration():
    """验证数据库迁移"""
    print(f'数据库路径: {DB_PATH}')

    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        print('错误: 数据库文件不存在!')
        return False

    # 连接数据库
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 检查bid_document表结构
        cursor.execute('PRAGMA table_info(bid_document)')
        columns = cursor.fetchall()

        print('\nbid_document表结构:')
        column_names = []
        for column in columns:
            cid, name, type_, notnull, dflt_value, pk = column
            print(f'  - {name}: {type_}')
            column_names.append(name)

        # 检查updated_at列是否存在
        if 'updated_at' in column_names:
            print('\n✅ 验证通过: updated_at列已成功添加到bid_document表中')
            return True
        else:
            print('\n❌ 验证失败: updated_at列未找到')
            return False

    except Exception as e:
        print(f'错误: {e}')
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    success = verify_migration()
    if success:
        print('\n数据库迁移验证成功!')
    else:
        print('\n数据库迁移验证失败!')
