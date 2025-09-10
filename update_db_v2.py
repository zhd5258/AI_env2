#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-03 18:09:43
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-03 18:10:35
# 文件相对于项目的路径   : \AI_env2\update_db_v2.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import sqlite3
import os

# 连接到数据库
DB_PATH = './tender_evaluation.db'
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 添加新的detailed_progress_info列到bid_document表
try:
    cursor.execute('ALTER TABLE bid_document ADD COLUMN detailed_progress_info TEXT')
    print('成功添加detailed_progress_info列到bid_document表')
except sqlite3.OperationalError as e:
    if 'duplicate column name' in str(e):
        print('detailed_progress_info列已存在')
    else:
        print(f'添加列时出错: {e}')

# 提交更改并关闭连接
conn.commit()
conn.close()

print('数据库更新完成')
