#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
数据库表结构更新脚本
"""

import os
import sys
from sqlalchemy import create_engine, MetaData, Table, Column, Boolean, text
from sqlalchemy.orm import sessionmaker

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.database import DATABASE_URL, ScoringRule, AnalysisResult


def update_database_schema():
    """更新数据库表结构"""
    print('开始更新数据库表结构...')

    # 创建数据库引擎
    engine = create_engine(DATABASE_URL)

    # 反射现有表结构
    metadata = MetaData()
    metadata.reflect(bind=engine)

    # 获取scoring_rule表
    scoring_rule_table = metadata.tables.get('scoring_rule')
    if scoring_rule_table is None:
        print('错误: 找不到scoring_rule表')
        return False

    # 检查是否已存在新字段
    existing_columns = [col.name for col in scoring_rule_table.columns]
    print(f'现有字段: {existing_columns}')

    # 需要添加的字段
    new_columns = [
        ('is_qualitative', Boolean, {'default': False}),
        ('is_quantitative', Boolean, {'default': False}),
    ]

    # 检查analysis_result表
    analysis_result_table = metadata.tables.get('analysis_result')
    if analysis_result_table is None:
        print('错误: 找不到analysis_result表')
        return False

    # analysis_result表需要添加的字段
    new_analysis_columns = [
        ('qualitative_analysis_results', 'JSON', {'default': '{}'}),
        ('quantitative_analysis_results', 'JSON', {'default': '{}'}),
        ('veto_items_checked', Boolean, {'default': False}),
        ('veto_items_passed', Boolean, {'default': True}),
        ('failed_veto_items', 'JSON', {'default': '{}'}),
    ]

    # 开始添加字段
    try:
        with engine.connect() as conn:
            # 为scoring_rule表添加字段
            for col_name, col_type, col_args in new_columns:
                if col_name not in existing_columns:
                    if col_type == Boolean:
                        sql = f'ALTER TABLE scoring_rule ADD COLUMN {col_name} BOOLEAN DEFAULT {col_args.get("default", False)}'
                    else:
                        sql = (
                            f'ALTER TABLE scoring_rule ADD COLUMN {col_name} {col_type}'
                        )
                    print(f'执行SQL: {sql}')
                    conn.execute(text(sql))
                    print(f'成功添加字段: {col_name}')
                else:
                    print(f'字段已存在: {col_name}')

            # 为analysis_result表添加字段
            existing_analysis_columns = [
                col.name for col in analysis_result_table.columns
            ]
            print(f'analysis_result表现有字段: {existing_analysis_columns}')

            for col_name, col_type, col_args in new_analysis_columns:
                if col_name not in existing_analysis_columns:
                    if col_type == Boolean:
                        sql = f'ALTER TABLE analysis_result ADD COLUMN {col_name} BOOLEAN DEFAULT {col_args.get("default", False)}'
                    elif col_type == 'JSON':
                        # SQLite中使用TEXT存储JSON
                        sql = f"ALTER TABLE analysis_result ADD COLUMN {col_name} TEXT DEFAULT '{col_args.get('default', '{}')}'"
                    else:
                        sql = f'ALTER TABLE analysis_result ADD COLUMN {col_name} {col_type}'
                    print(f'执行SQL: {sql}')
                    conn.execute(text(sql))
                    print(f'成功添加字段: {col_name}')
                else:
                    print(f'字段已存在: {col_name}')

            conn.commit()

        print('数据库表结构更新完成')
        return True

    except Exception as e:
        print(f'更新数据库表结构时出错: {e}')
        return False


def main():
    """主函数"""
    print('数据库表结构更新工具')
    print('==================')

    success = update_database_schema()

    if success:
        print('数据库表结构更新成功')
    else:
        print('数据库表结构更新失败')


if __name__ == '__main__':
    main()
