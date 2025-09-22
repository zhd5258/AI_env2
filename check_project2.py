#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:08:55
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:08:58
# 文件相对于项目的路径   : \AI_env2\check_project2.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查项目2的详细信息
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


def check_project2():
    """
    检查项目2的详细信息
    """
    print('检查项目2的详细信息')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查项目2
        project = session.query(TenderProject).filter(TenderProject.id == 2).first()
        if not project:
            print('错误：项目2不存在')
            return

        print('项目信息:')
        print(f'  ID: {project.id}')
        print(f'  名称: {project.name}')
        print(f'  项目代码: {project.project_code}')
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 检查评分规则
        scoring_rules = (
            session.query(ScoringRule).filter(ScoringRule.project_id == 2).all()
        )
        print(f'\n评分规则数量: {len(scoring_rules)}')
        for rule in scoring_rules:
            print(f'  规则ID: {rule.id}')
            print(f'    父项名称: {rule.Parent_Item_Name}')
            print(f'    父项分数: {rule.Parent_max_score}')
            print(f'    子项名称: {rule.Child_Item_Name}')
            print(f'    子项分数: {rule.Child_max_score}')
            print(f'    描述: {rule.description}')
            print(f'    是否价格规则: {rule.is_price_criteria}')
            print(f'    公式: {rule.price_formula}')

        # 检查投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 2).all()
        print(f'\n投标文档数量: {len(bid_docs)}')
        for doc in bid_docs:
            print(f'  文档ID: {doc.id}')
            print(f'    投标方: {doc.bidder_name}')
            print(f'    文件路径: {doc.file_path}')
            print(f'    处理状态: {doc.processing_status}')
            print(
                f'    进度: {doc.progress_completed_rules}/{doc.progress_total_rules}'
            )
            print(f'    当前规则: {doc.progress_current_rule}')

        session.close()

    except Exception as e:
        print(f'检查过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    check_project2()
