#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:39:34
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-10 21:39:37
# 文件相对于项目的路径   : \AI_env2\final_scoring_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终评分规则提取测试程序
用于测试整个招标文件的评分规则提取，并正确处理中文字符
"""

import sys
import os
import json
import logging

# 设置日志编码
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

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


def analyze_full_pdf_scoring_rules(pdf_file_path):
    """分析完整PDF招标文件的评分规则"""
    print(f'开始分析完整PDF招标文件: {pdf_file_path}')

    if not os.path.exists(pdf_file_path):
        print(f'错误: 文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('正在处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 显示文件基本信息
        total_chars = sum(len(page) for page in pages_text)
        print(f'总字符数: {total_chars}')

        # 创建一个包含所有页面的评分提取器实例
        print('\n使用整个文件进行评分规则提取...')
        extractor = IntelligentScoringExtractor(pages_text)

        # 提取评分规则
        print('提取评分规则...')
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

            # 保存结果到JSON文件，确保使用UTF-8编码
            output_file = pdf_file_path.replace('.pdf', '_final_scoring_rules.json')
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


def create_summary_report(rules, pdf_file_path):
    """创建评分规则摘要报告"""
    if not rules:
        print('没有评分规则可报告')
        return

    print(f'\n{"=" * 60}')
    print('评分规则摘要报告')
    print(f'{"=" * 60}')

    # 统计信息
    total_rules = len(rules)
    price_rules = [r for r in rules if r.get('is_price_criteria', False)]
    tech_rules = [r for r in rules if not r.get('is_price_criteria', False)]

    print(f'总评分规则数: {total_rules}')
    print(f'价格评分规则数: {len(price_rules)}')
    print(f'技术评分规则数: {len(tech_rules)}')

    # 总分
    total_score = sum(rule['max_score'] for rule in rules)
    print(f'总分: {total_score}分')

    # 详细规则列表
    print('\n详细评分规则:')
    print_scoring_rules(rules)

    # 生成报告文件
    report_file = pdf_file_path.replace('.pdf', '_scoring_summary.txt')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('评分规则摘要报告\n')
        f.write('=' * 60 + '\n')
        f.write(f'总评分规则数: {total_rules}\n')
        f.write(f'价格评分规则数: {len(price_rules)}\n')
        f.write(f'技术评分规则数: {len(tech_rules)}\n')
        f.write(f'总分: {total_score}分\n\n')

        f.write('详细评分规则:\n')
        for rule in rules:
            f.write(f'- {rule["criteria_name"]}: {rule["max_score"]}分\n')
            if rule.get('description'):
                desc = rule['description']
                if len(desc) > 100:
                    desc = desc[:100] + '...'
                f.write(f'  描述: {desc}\n')
            if rule.get('is_price_criteria'):
                f.write('  (价格评分规则)\n')
            f.write('\n')

    print(f'\n摘要报告已保存到: {report_file}')


if __name__ == '__main__':
    # 指定PDF文件路径
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    # 如果通过命令行参数指定了文件路径，则使用该路径
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]

    # 分析完整PDF文件
    print('开始进行最终评分规则提取测试...')
    rules = analyze_full_pdf_scoring_rules(pdf_file_path)

    # 创建摘要报告
    create_summary_report(rules, pdf_file_path)

    print('\n测试完成!')
