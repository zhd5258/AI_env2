#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:36:31
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:37:09
# 文件相对于项目的路径   : \AI_env2\test_streaming_with_separate_price_analysis.py
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
# 文件相对于项目的路径   : \AI_env2\test_streaming_with_separate_price_analysis.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试优化后的流式处理和价格分析分离功能
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
from modules.pdf_processor import PDFProcessor
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.price_manager import PriceManager
from modules.price_score_calculator import PriceScoreCalculator


def test_streaming_with_separate_price_analysis():
    """
    测试优化后的流式处理和价格分析分离功能
    """
    print('测试优化后的流式处理和价格分析分离功能')
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

        # 分离价格规则和非价格规则
        price_rules = [rule for rule in scoring_rules if rule.is_price_criteria]
        non_price_rules = [
            rule
            for rule in scoring_rules
            if not rule.is_price_criteria and rule.Child_Item_Name
        ]

        print(f'  价格规则数量: {len(price_rules)}')
        print(f'  非价格规则数量: {len(non_price_rules)}')

        # 显示价格规则
        if price_rules:
            price_rule = price_rules[0]
            print('\n价格规则:')
            print(f'  父项名称: {price_rule.Parent_Item_Name}')
            print(f'  描述: {price_rule.description}')
            print(f'  公式: {price_rule.price_formula}')

        # 显示非价格规则（子项）
        print('\n非价格规则（子项）:')
        for rule in non_price_rules:
            print(
                f'  {rule.Child_Item_Name}: 最高分{rule.Child_max_score}, {rule.description}'
            )

        # 创建分析器实例来测试优化后的prompt构建
        analyzer = IntelligentBidAnalyzer(
            project.tender_file_path,
            '',  # 不需要实际的投标文件路径进行测试
            db_session=session,
            project_id=2,
        )

        # 测试构建优化后的prompt（只包含非价格规则的子项）
        prompt = analyzer._build_analysis_prompt(scoring_rules)
        print('\n优化后的Prompt（只包含非价格规则的子项）:')
        print(prompt)

        # 统计包含的规则项
        prompt_lines = prompt.split('\n')
        prompt_child_items = [line for line in prompt_lines if '：，本项最高分' in line]
        print(f'\nPrompt中包含的非价格规则子项数量: {len(prompt_child_items)}')

        # 演示价格分析分离
        print('\n演示价格分析分离:')
        print('1. 流式处理阶段：只分析非价格规则项，提取投标人名称和投标总价')
        print('2. 价格分析阶段：在所有投标人总价提取完成后，单独进行价格分计算')

        # 模拟投标人总价提取结果
        bidder_prices = {
            '投标方A': 1000000.0,
            '投标方B': 950000.0,
            '投标方C': 1050000.0,
        }

        print('\n模拟提取到的投标人总价:')
        for bidder, price in bidder_prices.items():
            print(f'  {bidder}: {price}元')

        # 演示价格分计算
        if price_rules:
            price_rule = price_rules[0]
            print('\n价格分计算:')
            print(f'  评分规则: {price_rule.description}')
            print(f'  计算公式: {price_rule.price_formula}')

            # 构造发送给AI的价格分计算请求
            bidder_info_str = ','.join(
                [f'{name}：{price}' for name, price in bidder_prices.items()]
            )
            price_prompt = f"""你是一个评标专家，现在各投标人的投标总价为：『{bidder_info_str}』,价格评价标准为：『{price_rule.description}』,请计算各投标人的报价。请返回格式为JSON格式：『投标人1：价格分1,投标人2：价格分2,投标人3：价格分3,.......』,请返回结果。"""

            print('\n发送给AI的价格分计算请求:')
            print(price_prompt)

        session.close()

        print('\n优化后的流式处理和价格分析分离功能测试完成')

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    test_streaming_with_separate_price_analysis()
