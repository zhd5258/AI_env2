#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库迁移脚本
用于更新现有数据库结构以匹配模型定义
"""

import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, DateTime, text
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import Base, TenderProject, DATABASE_URL

def migrate_database():
    """执行数据库迁移"""
    print("开始数据库迁移...")
    
    # 创建引擎
    engine = create_engine(DATABASE_URL, echo=True)
    
    # 反射现有数据库结构
    metadata = MetaData()
    metadata.reflect(bind=engine)
    
    # 检查tender_project表是否存在
    if 'tender_project' not in metadata.tables:
        print("tender_project表不存在，创建所有表...")
        Base.metadata.create_all(bind=engine)
        print("所有表创建完成")
        return
    
    # 获取现有的tender_project表
    tender_project_table = metadata.tables['tender_project']
    
    # 检查是否需要添加analysis_start_time列
    if 'analysis_start_time' not in tender_project_table.c:
        print("添加analysis_start_time列...")
        with engine.connect() as conn:
            # 使用ALTER TABLE语句添加列
            conn.execute(
                text('ALTER TABLE tender_project ADD COLUMN analysis_start_time DATETIME')
            )
            conn.commit()
        print("analysis_start_time列添加完成")
    else:
        print("analysis_start_time列已存在")
    
    # 检查是否需要添加analysis_end_time列
    if 'analysis_end_time' not in tender_project_table.c:
        print("添加analysis_end_time列...")
        with engine.connect() as conn:
            # 使用ALTER TABLE语句添加列
            conn.execute(
                text('ALTER TABLE tender_project ADD COLUMN analysis_end_time DATETIME')
            )
            conn.commit()
        print("analysis_end_time列添加完成")
    else:
        print("analysis_end_time列已存在")
    
    print("数据库迁移完成")

if __name__ == "__main__":
    migrate_database()
