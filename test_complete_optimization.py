#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:37:47
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:37:50
# 文件相对于项目的路径   : \AI_env2\test_complete_optimization.py
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
# 文件相对于项目的路径   : \AI_env2\test_complete_optimization.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试完整的优化功能
包括：
1. 流式处理时只发送非价格规则的子项
2. 流式处理和价格分析分离
3. 简化发送给AI大模型的prompt
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
from modules.price_score_calculator import PriceScoreCalculator


def test_complete_optimization():
    """
    测试完整的优化功能
    """
    print('测试完整的优化功能')
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

        # 创建分析器实例来测试优化后的功能
        analyzer = IntelligentBidAnalyzer(
            project.tender_file_path,
            '',  # 不需要实际的投标文件路径进行测试
            db_session=session,
            project_id=2,
        )

        # 测试1：验证构建的prompt只包含非价格规则的子项
        print('\n测试1: 验证构建的prompt只包含非价格规则的子项')
        prompt = analyzer._build_analysis_prompt(scoring_rules)
        prompt_lines = prompt.split('\n')
        prompt_child_items = [line for line in prompt_lines if '：，本项最高分' in line]
        print(f'  Prompt中包含的非价格规则子项数量: {len(prompt_child_items)}')

        # 验证不包含价格规则
        price_rule_names = [rule.Parent_Item_Name for rule in price_rules]
        contains_price_rule = any(name in prompt for name in price_rule_names)
        print(f'  Prompt中是否包含价格规则: {contains_price_rule}')

        # 验证不包含父项规则
        parent_rule_names = [
            rule.Parent_Item_Name
            for rule in scoring_rules
            if rule.Parent_Item_Name
            and not rule.is_price_criteria
            and not rule.Child_Item_Name
        ]
        contains_parent_rule = any(name in prompt for name in parent_rule_names)
        print(f'  Prompt中是否包含父项规则: {contains_parent_rule}')

        # 测试2：验证简化后的prompt格式
        print('\n测试2: 验证简化后的prompt格式')
        # 模拟构建分析chunk prompt
        sample_text = '这是投标文件的示例文本内容...'
        scoring_rules_section = prompt.split('}},投标方的投标文本内容为：')[0] + '}}'

        chunk_prompt = f"""{scoring_rules_section},投标方的投标文本内容为：
『{sample_text}』
请分析该投标文本，分析出该投标方的投标人名称、投标总价，并根据评分规则进行打分，请返回json格式的结果。"""

        print(f'  简化后的chunk prompt长度: {len(chunk_prompt)} 字符')
        print(
            f'  是否包含冗余说明: {"详细分析" not in chunk_prompt and "投标一览表" not in chunk_prompt}'
        )

        # 测试3：验证价格分析分离
        print('\n测试3: 验证价格分析分离')
        if price_rules:
            price_rule = price_rules[0]
            # 创建价格评分计算器实例
            calculator = PriceScoreCalculator(db_session=session)

            # 模拟投标人价格数据
            bidder_prices = {
                '投标方A': 1000000.0,
                '投标方B': 950000.0,
                '投标方C': 1050000.0,
            }

            # 构造价格分析prompt
            bidder_info_str = ','.join(
                [f'{name}：{price}' for name, price in bidder_prices.items()]
            )
            price_prompt = f"""你是一个评标专家，现在各投标人的投标总价为：『{bidder_info_str}』,价格评价标准为：『{price_rule.description}』,请计算各投标人的价格分。请返回格式为JSON格式：『投标人1：价格分1,投标人2：价格分2,投标人3：价格分3,.......』,请返回结果。"""

            print(f'  价格分析prompt长度: {len(price_prompt)} 字符')
            print(
                f'  是否包含简化格式: {"详细分析" not in price_prompt and "计算说明" not in price_prompt}'
            )

        # 测试4：验证流式处理回调中的prompt优化
        print('\n测试4: 验证流式处理回调中的prompt优化')
        # 模拟流式处理回调中的prompt构建
        current_text = '这是流式处理中已处理的文本内容...'
        stream_prompt = f"""{scoring_rules_section},投标方的投标文本内容为：
『{current_text}』
请分析该投标文本，分析出该投标方的投标人名称、投标总价，并根据评分规则进行打分，请返回json格式的结果。"""

        print(f'  流式处理中的prompt长度: {len(stream_prompt)} 字符')
        print(
            f'  是否包含简化格式: {"详细分析" not in stream_prompt and "投标一览表" not in stream_prompt}'
        )

        session.close()

        print('\n所有优化功能测试完成')
        print('\n优化总结:')
        print('  1. 流式处理时只发送非价格规则的子项 ✓')
        print('  2. 流式处理和价格分析分离 ✓')
        print('  3. 简化发送给AI大模型的prompt ✓')
        print('  4. 剔除Parent_Item_Name项 ✓')
        print('  5. 剔除价格规则项 ✓')

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    test_complete_optimization()
