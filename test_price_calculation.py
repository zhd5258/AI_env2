#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:10:44
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-09-22 22:13:24
#文件相对于项目的路径   : \AI_env2\test_price_calculation.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试价格评分计算功能
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
from modules.price_score_calculator import PriceScoreCalculator


def test_price_calculation():
    """
    测试价格评分计算功能
    """
    print('测试价格评分计算功能')
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
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 检查评分规则
        scoring_rules = (
            session.query(ScoringRule).filter(ScoringRule.project_id == 2).all()
        )
        print(f'\n评分规则数量: {len(scoring_rules)}')
        price_rules = [r for r in scoring_rules if r.is_price_criteria]
        print(f'  价格规则数量: {len(price_rules)}')
        for rule in price_rules:
            print(f'    规则ID: {rule.id}')
            print(f'      父项名称: {rule.Parent_Item_Name}')
            print(f'      父项分数: {rule.Parent_max_score}')
            print(f'      描述: {rule.description}')
            print(f'      公式: {rule.price_formula}')

        # 测试价格评分计算
        if price_rules:
            print('\n测试价格评分计算:')
            calculator = PriceScoreCalculator(db_session=session)
            result = calculator.calculate_project_price_scores(2)
            print(f'  计算结果: {result}')
        else:
            print('\n错误：没有找到价格评分规则')

        session.close()

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    test_price_calculation()
