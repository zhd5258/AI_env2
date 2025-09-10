#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:34:26
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-10 21:34:32
# 文件相对于项目的路径   : \AI_env2\test_pdf_scoring.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门用于测试PDF招标文件评分规则提取的脚本
使用指定的PDF文件进行测试
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
            print(f'{indent}  描述: {rule["description"]}')
        if rule.get('is_price_criteria'):
            print(f'{indent}  (价格评分规则)')
        if rule.get('children'):
            print_scoring_rules(rule['children'], level + 1)


def analyze_pdf_scoring_rules(pdf_file_path):
    """分析PDF招标文件的评分规则"""
    print(f'开始分析PDF招标文件: {pdf_file_path}')

    if not os.path.exists(pdf_file_path):
        print(f'错误: 文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('正在处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 显示每页的文本长度
        for i, page_text in enumerate(pages_text):
            print(f'  第 {i + 1} 页: {len(page_text)} 字符')

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

            # 汇总所有段落的结果
            print(f'\n{"=" * 60}')
            print('汇总分析结果:')
            print(f'{"=" * 60}')

            total_rules_extracted = sum(
                result['rules_count'] for result in all_segment_results
            )
            print(
                f'总共分析了 {len(pages_text)} 页，分 {len(all_segment_results)} 段处理'
            )
            print(f'总共提取到 {total_rules_extracted} 条评分规则')

            # 显示各段落的结果
            for result in all_segment_results:
                print(
                    f'\n段落 {result["segment"]} (页 {result["start_page"]}-{result["end_page"]}):'
                )
                print(f'  提取规则数: {result["rules_count"]}')
                print(f'  总分: {result["total_score"]}')
                print(f'  包含价格规则: {"是" if result["has_price_rule"] else "否"}')

        else:
            # 页面较少，一次性处理
            print('\n文件较短，一次性处理所有页面...')

            # 创建评分提取器实例
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
                has_price_rule = any(
                    rule.get('is_price_criteria', False) for rule in rules
                )
                if has_price_rule:
                    print('✓ 包含价格评分规则')
                else:
                    print('⚠ 未找到价格评分规则')

                # 保存结果到JSON文件
                output_file = pdf_file_path.replace('.pdf', '_scoring_rules.json')
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(rules, f, ensure_ascii=False, indent=2)
                print(f'\n评分规则已保存到: {output_file}')
            else:
                print('❌ 未能提取到评分规则')

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    # 指定PDF文件路径
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    # 如果通过命令行参数指定了文件路径，则使用该路径
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]

    analyze_pdf_scoring_rules(pdf_file_path)
