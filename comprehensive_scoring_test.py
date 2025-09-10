#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:36:35
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-09-10 21:37:44
#文件相对于项目的路径   : \AI_env2\comprehensive_scoring_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
综合评分规则提取测试程序
用于测试整个招标文件的评分规则提取，包括合并所有段落的结果
"""

import sys
import os
import json
from collections import defaultdict

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.intelligent_scoring_extractor import IntelligentScoringExtractor
from modules.pdf_processor import PDFProcessor


def merge_scoring_rules(all_segment_results):
    """合并所有段落的评分规则"""
    # 收集所有规则
    all_rules = []
    price_rules = []

    for result in all_segment_results:
        rules = result.get('rules', [])
        for rule in rules:
            # 检查是否为价格规则
            if (
                rule.get('is_price_criteria', False)
                or '价格' in rule.get('criteria_name', '')
                or '报价' in rule.get('criteria_name', '')
            ):
                price_rules.append(rule)
            else:
                all_rules.append(rule)

    # 合并价格规则（通常只需要一个）
    if price_rules:
        # 选择最完整的那个价格规则
        best_price_rule = max(price_rules, key=lambda r: len(r.get('description', '')))
        all_rules.append(best_price_rule)

    return all_rules


def print_scoring_rules(rules, level=0):
    """打印评分规则的层级结构"""
    indent = '  ' * level
    for rule in rules:
        print(f'{indent}- {rule["criteria_name"]}: {rule["max_score"]}分')
        if rule.get('description'):
            print(f'{indent}  描述: {rule["description"]}')
        if rule.get('is_price_criteria'):
            print(f'{indent}  (价格评分规则)')
        if rule.get('children'):
            print_scoring_rules(rule['children'], level + 1)


def adjust_scores_to_100(rules):
    """调整评分规则总分为100分"""
    total_score = sum(rule['max_score'] for rule in rules)

    if abs(total_score - 100.0) > 0.1 and total_score > 0:
        # 计算缩放因子
        scale_factor = 100.0 / total_score
        # 调整每个规则的分数
        for rule in rules:
            rule['max_score'] *= scale_factor

    return rules


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

            # 保存结果到JSON文件
            output_file = pdf_file_path.replace('.pdf', '_full_scoring_rules.json')
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


def analyze_segmented_pdf_scoring_rules(pdf_file_path):
    """分段分析PDF招标文件的评分规则"""
    print(f'开始分段分析PDF招标文件: {pdf_file_path}')

    if not os.path.exists(pdf_file_path):
        print(f'错误: 文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('正在处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 如果页面太多，分段处理
        segment_size = 10  # 每段10页
        if len(pages_text) > segment_size:
            print(f'\n文件较长 ({len(pages_text)} 页)，将分段处理...')

            # 分段处理所有页面
            all_segment_results = []
            for i in range(0, len(pages_text), segment_size):
                segment_pages = pages_text[i : i + segment_size]
                segment_start = i + 1
                segment_end = min(i + segment_size, len(pages_text))

                print(
                    f'\n--- 分析段落 {i // segment_size + 1} (页 {segment_start}-{segment_end}) ---'
                )

                # 创建评分提取器实例
                extractor = IntelligentScoringExtractor(segment_pages)

                # 提取评分规则
                print('提取评分规则...')
                rules = extractor.extract_scoring_rules()

                if rules:
                    print(f'成功提取到 {len(rules)} 条评分规则:')
                    print_scoring_rules(rules)

                    # 计算总分
                    total_score = sum(rule['max_score'] for rule in rules)
                    print(f'总分: {total_score}分')

                    # 检查是否有价格评分规则
                    has_price_rule = any(
                        rule.get('is_price_criteria', False) for rule in rules
                    )
                    if has_price_rule:
                        print('✓ 包含价格评分规则')
                    else:
                        print('⚠ 未找到价格评分规则')

                    all_segment_results.append(
                        {
                            'segment': i // segment_size + 1,
                            'start_page': segment_start,
                            'end_page': segment_end,
                            'rules_count': len(rules),
                            'total_score': total_score,
                            'has_price_rule': has_price_rule,
                            'rules': rules,
                        }
                    )
                else:
                    print('未能提取到评分规则')
                    all_segment_results.append(
                        {
                            'segment': i // segment_size + 1,
                            'start_page': segment_start,
                            'end_page': segment_end,
                            'rules_count': 0,
                            'total_score': 0,
                            'has_price_rule': False,
                            'rules': [],
                        }
                    )

            # 合并所有段落的结果
            print(f'\n{"=" * 60}')
            print('合并分析结果:')
            print(f'{"=" * 60}')

            # 合并所有规则
            merged_rules = merge_scoring_rules(all_segment_results)

            # 调整总分为100分
            adjusted_rules = adjust_scores_to_100(merged_rules)

            print(f'合并后共有 {len(adjusted_rules)} 条评分规则:')
            print_scoring_rules(adjusted_rules)

            # 计算调整后的总分
            final_total_score = sum(rule['max_score'] for rule in adjusted_rules)
            print(f'\n调整后总分: {final_total_score}分')

            # 保存合并结果到JSON文件
            output_file = pdf_file_path.replace('.pdf', '_merged_scoring_rules.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(adjusted_rules, f, ensure_ascii=False, indent=2)
            print(f'\n合并后的评分规则已保存到: {output_file}')

            return adjusted_rules

        else:
            # 页面较少，直接调用完整分析函数
            return analyze_full_pdf_scoring_rules(pdf_file_path)

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()
        return []


def compare_extraction_methods(pdf_file_path):
    """比较不同提取方法的结果"""
    print(f'{"=" * 60}')
    print('比较不同评分规则提取方法的结果')
    print(f'{"=" * 60}')

    # 方法1: 完整文件分析
    print('\n方法1: 完整文件分析')
    full_rules = analyze_full_pdf_scoring_rules(pdf_file_path)

    # 方法2: 分段分析后合并
    print('\n方法2: 分段分析后合并')
    merged_rules = analyze_segmented_pdf_scoring_rules(pdf_file_path)

    # 比较结果
    print(f'\n{"=" * 60}')
    print('结果比较:')
    print(f'{"=" * 60}')
    print(f'完整文件分析提取到 {len(full_rules)} 条规则')
    print(f'分段分析合并后提取到 {len(merged_rules)} 条规则')

    # 检查是否有价格规则
    full_has_price = any(rule.get('is_price_criteria', False) for rule in full_rules)
    merged_has_price = any(
        rule.get('is_price_criteria', False) for rule in merged_rules
    )

    print(f'完整文件分析包含价格规则: {"是" if full_has_price else "否"}')
    print(f'分段分析合并包含价格规则: {"是" if merged_has_price else "否"}')


if __name__ == '__main__':
    # 指定PDF文件路径
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    # 如果通过命令行参数指定了文件路径，则使用该路径
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]

    # 比较不同提取方法的结果
    compare_extraction_methods(pdf_file_path)
