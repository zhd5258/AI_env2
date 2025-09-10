#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-03 17:33:30
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-03 17:35:17
# 文件相对于项目的路径   : \AI_env2\update_db.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
from modules.database import (
    engine,
    Base,
    BidDocument,
    TenderProject,
    AnalysisResult,
    ScoringRule,
)
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.exc import OperationalError


def update_database():
    # 创建所有表（如果不存在）
    Base.metadata.create_all(bind=engine)

    # 检查bid_document表是否需要添加新列
    inspector = inspect(engine)
    columns = inspector.get_columns('bid_document')
    column_names = [column['name'] for column in columns]

    print('现有bid_document表列:', column_names)

    # 如果缺少partial_analysis_results列，则添加它
    if 'partial_analysis_results' not in column_names:
        print('正在添加partial_analysis_results列...')
        try:
            # 在SQLite中添加列
            with engine.connect() as conn:
                conn.execute(
                    text(
                        'ALTER TABLE bid_document ADD COLUMN partial_analysis_results VARCHAR'
                    )
                )
                conn.commit()
            print('成功添加partial_analysis_results列')
        except OperationalError as e:
            print(f'添加列时出错: {e}')
    else:
        print('partial_analysis_results列已存在')

    # 检查scoring_rule表是否需要添加新列
    columns = inspector.get_columns('scoring_rule')
    column_names = [column['name'] for column in columns]

    print('现有scoring_rule表列:', column_names)

    # 如果缺少is_veto列，则添加它
    if 'is_veto' not in column_names:
        print('正在添加is_veto列...')
        try:
            # 在SQLite中添加列
            with engine.connect() as conn:
                conn.execute(
                    text(
                        'ALTER TABLE scoring_rule ADD COLUMN is_veto BOOLEAN DEFAULT 0'
                    )
                )
                conn.commit()
            print('成功添加is_veto列')
        except OperationalError as e:
            print(f'添加列时出错: {e}')
    else:
        print('is_veto列已存在')


if __name__ == '__main__':
    update_database()
