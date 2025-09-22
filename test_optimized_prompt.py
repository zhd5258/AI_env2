#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:36:01
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:36:04
# 文件相对于项目的路径   : \AI_env2\test_optimized_prompt.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:07:27
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:07:30
# 文件相对于项目的路径   : \AI_env2\test_optimized_prompt.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试优化后的prompt
"""

import sys
import os
import json
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer


def test_optimized_prompt():
    """
    测试优化后的prompt
    """
    print('测试优化后的prompt')
    print('=' * 60)

    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    try:
        session = SessionLocal()

        # 检查项目2（有评分规则）
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

        # 创建分析器实例来测试优化后的prompt构建
        analyzer = IntelligentBidAnalyzer(
            project.tender_file_path,
            '',  # 不需要实际的投标文件路径进行测试
            db_session=session,
            project_id=2,
        )

        # 测试构建优化后的prompt
        prompt = analyzer._build_analysis_prompt(scoring_rules)
        print('\n优化后的Prompt:')
        print(prompt)

        # 统计包含的规则项
        lines = prompt.split('\n')
        child_item_count = 0
        price_rule_count = 0
        parent_item_count = 0

        for rule in scoring_rules:
            if rule.is_price_criteria:
                price_rule_count += 1
            elif rule.Child_Item_Name:
                child_item_count += 1
            elif rule.Parent_Item_Name:
                parent_item_count += 1

        print('\n规则统计:')
        print(f'  价格规则数量: {price_rule_count}')
        print(f'  子项规则数量: {child_item_count}')
        print(f'  父项规则数量: {parent_item_count}')

        # 检查prompt中是否只包含了子项规则
        prompt_lines = prompt.split('\n')
        prompt_child_items = [line for line in prompt_lines if '：，本项最高分' in line]
        print(f'\nPrompt中包含的规则项数量: {len(prompt_child_items)}')

        print('\nPrompt中的规则项:')
        for item in prompt_child_items:
            print(f'  {item.strip()}')

        session.close()

        print('\n优化后的prompt测试完成')

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    test_optimized_prompt()
