#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:48:55
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-09-10 21:49:08
#文件相对于项目的路径   : \AI_env2\improved_table_scoring_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:50:00
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-10 21:50:00
# 文件相对于项目的路径   : \AI_env2\improved_table_scoring_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进后的表格评分规则提取功能
专门针对第14-16页的表格格式评分规则进行测试
"""

import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.intelligent_scoring_extractor import IntelligentScoringExtractor
from modules.pdf_processor import PDFProcessor


def print_scoring_rules(rules, level=0):
    """打印评分规则的层级结构"""
    indent = '  ' * level
    for rule in rules:
        print(f'{indent}- {rule["criteria_name"]}: {rule["max_score"]}分')
        if rule.get('description'):
            # 限制描述长度以避免输出过长
            desc = rule['description']
            if len(desc) > 100:
                desc = desc[:100] + '...'
            print(f'{indent}  描述: {desc}')
        if rule.get('is_price_criteria'):
            print(f'{indent}  (价格评分规则)')
        if rule.get('children'):
            print_scoring_rules(rule['children'], level + 1)


def test_improved_table_scoring_extraction():
    """测试改进后的表格评分规则提取功能"""
    print('开始测试改进后的表格评分规则提取功能...')

    # 读取PDF文件的第14-16页内容
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    if not os.path.exists(pdf_file_path):
        print(f'文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('正在处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 提取第14-16页的内容
        table_pages = pages_text[13:16]  # 第14-16页（索引13-15）
        table_text = '\n'.join(table_pages)

        print(f'表格区域文本长度: {len(table_text)} 字符')
        print('表格区域内容预览:')
        print('=' * 50)
        lines = table_text.split('\n')
        for i, line in enumerate(lines[:30]):  # 显示前30行
            if line.strip():
                print(f'{i + 1:2d}. {line[:100]}{"..." if len(line) > 100 else ""}')
        print('=' * 50)

        # 创建评分提取器实例，只使用表格区域的内容
        extractor = IntelligentScoringExtractor(table_pages)

        # 提取评分规则
        print('\n开始提取评分规则...')
        rules = extractor.extract_scoring_rules()

        if rules:
            print(f'\n成功提取到 {len(rules)} 条主要评分规则:')
            print_scoring_rules(rules)

            # 计算总分
            total_score = sum(rule['max_score'] for rule in rules)
            print(f'\n总分: {total_score}分')

            # 检查是否有价格评分规则
            has_price_rule = any(rule.get('is_price_criteria', False) for rule in rules)
            if has_price_rule:
                print('✓ 包含价格评分规则')
            else:
                print('⚠ 未找到价格评分规则')

            # 保存结果到JSON文件
            output_file = 'improved_table_scoring_rules_test.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            print(f'\n评分规则已保存到: {output_file}')

            return rules
        else:
            print('❌ 未能提取到评分规则')
            return []

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()
        return []


def test_full_document_with_improvements():
    """测试完整文档的评分规则提取（使用改进后的功能）"""
    print('\n' + '=' * 60)
    print('开始测试完整文档评分规则提取（改进版）...')
    print('=' * 60)

    # 读取完整的PDF文件
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    if not os.path.exists(pdf_file_path):
        print(f'文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('正在处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 创建评分提取器实例，使用完整文档
        extractor = IntelligentScoringExtractor(pages_text)

        # 提取评分规则
        print('开始提取评分规则...')
        rules = extractor.extract_scoring_rules()

        if rules:
            print(f'\n成功提取到 {len(rules)} 条主要评分规则:')
            print_scoring_rules(rules)

            # 计算总分
            total_score = sum(rule['max_score'] for rule in rules)
            print(f'\n总分: {total_score}分')

            # 检查是否有价格评分规则
            has_price_rule = any(rule.get('is_price_criteria', False) for rule in rules)
            if has_price_rule:
                print('✓ 包含价格评分规则')
            else:
                print('⚠ 未找到价格评分规则')

            # 保存结果到JSON文件
            output_file = 'improved_full_document_scoring_rules_test.json'
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, ensure_ascii=False, indent=2)
            print(f'\n评分规则已保存到: {output_file}')

            return rules
        else:
            print('❌ 未能提取到评分规则')
            return []

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()
        return []


if __name__ == '__main__':
    print('开始进行改进版评分规则提取测试...')

    # 测试表格区域的评分规则提取
    table_rules = test_improved_table_scoring_extraction()

    # 测试完整文档的评分规则提取
    full_rules = test_full_document_with_improvements()

    # 比较结果
    print('\n' + '=' * 60)
    print('测试结果比较:')
    print('=' * 60)
    print(f'表格区域提取到 {len(table_rules)} 条规则')
    print(f'完整文档提取到 {len(full_rules)} 条规则')

    # 检查是否包含价格规则
    table_has_price = any(rule.get('is_price_criteria', False) for rule in table_rules)
    full_has_price = any(rule.get('is_price_criteria', False) for rule in full_rules)

    print(f'表格区域包含价格规则: {"是" if table_has_price else "否"}')
    print(f'完整文档包含价格规则: {"是" if full_has_price else "否"}')

    print('\n测试完成!')
