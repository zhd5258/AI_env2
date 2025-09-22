#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:08:41
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:08:44
# 文件相对于项目的路径   : \AI_env2\check_projects.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查数据库中的项目
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)


def check_projects():
    """
    检查数据库中的项目
    """
    print('检查数据库中的项目')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查所有项目
        projects = session.query(TenderProject).all()
        print(f'项目总数: {len(projects)}')
        for project in projects:
            print(f'  项目ID: {project.id}')
            print(f'    名称: {project.name}')
            print(f'    项目代码: {project.project_code}')
            print(f'    状态: {project.status}')
            print(f'    招标文件: {project.tender_file_path}')

            # 检查评分规则
            scoring_rules = (
                session.query(ScoringRule)
                .filter(ScoringRule.project_id == project.id)
                .all()
            )
            print(f'    评分规则数量: {len(scoring_rules)}')
            price_rules = [r for r in scoring_rules if r.is_price_criteria]
            print(f'    价格规则数量: {len(price_rules)}')

            # 检查投标文档
            bid_docs = (
                session.query(BidDocument)
                .filter(BidDocument.project_id == project.id)
                .all()
            )
            print(f'    投标文档数量: {len(bid_docs)}')

            # 检查分析结果
            analysis_results = (
                session.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project.id)
                .all()
            )
            print(f'    分析结果数量: {len(analysis_results)}')
            print()

        session.close()

    except Exception as e:
        print(f'检查过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    check_projects()
