#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
评分规则提取器测试程序
用于测试 IntelligentScoringExtractor 类的功能
"""

import sys
import os
import json

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.intelligent_scoring_extractor import IntelligentScoringExtractor
from modules.pdf_processor import PDFProcessor


def create_test_data():
    """创建测试用的招标文件内容"""
    return [
        """
第一章 招标公告
本次招标项目为XX系统建设项目，欢迎符合条件的投标人参与投标。

第二章 投标人须知
投标人须知中包含了投标的基本要求和注意事项。

第三章 评标办法
3.1 评标方法
本次评标采用综合评估法，满分100分。

3.2 技术评分标准（60分）
3.2.1 技术方案完整性 20分
3.2.2 技术方案可行性 20分
3.2.3 技术团队实力 10分
3.2.4 项目实施计划 10分

3.3 商务评分标准（30分）
3.3.1 企业资质 10分
3.3.2 业绩经验 10分
3.3.3 服务承诺 10分

3.4 价格评分标准（10分）
投标报价得分=（评标基准价/投标报价）×价格分值
评标基准价为满足招标文件要求且投标价格最低的投标报价。

第四章 合同条款
合同条款详细规定了双方的权利和义务。
        """,
        """
评标办法
采用综合评分法，总分100分，具体评分标准如下：

一、技术部分（50分）
1.1 技术方案（25分）
包括技术路线的先进性、可行性等
1.2 项目管理（15分）
包括进度安排、质量控制等
1.3 技术团队（10分）
包括团队构成、人员资质等

二、商务部分（30分）
2.1 企业实力（15分）
包括注册资本、资质等级等
2.2 项目经验（15分）
包括类似项目业绩等

三、价格部分（20分）
价格分计算公式：价格得分=（最低评标价/投标报价）×20
        """,
        """
第四章 评标办法
4.1 评分标准
本次评标满分100分，具体标准如下：

技术评分标准（65分）
技术方案完整性（20分）
技术方案可行性（20分）
技术创新性（15分）
项目实施计划（10分）

商务评分标准（25分）
企业资质等级（10分）
类似项目业绩（10分）
售后服务承诺（5分）

价格评分标准（10分）
采用最低价优先法，即满足招标文件要求且投标价格最低的投标报价为评标基准价，
其价格分为满分，其他投标人的价格分按以下公式计算：
投标报价得分=（评标基准价/投标报价）×10

4.2 评分程序
评标委员会按照评分标准进行独立评分。
        """,
    ]


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


def test_scoring_extractor():
    """测试评分规则提取功能"""
    print('=== 评分规则提取器测试 ===\n')

    # 创建测试数据
    test_data_list = create_test_data()

    for i, test_data in enumerate(test_data_list, 1):
        print(f'--- 测试案例 {i} ---')
        print('输入文本长度:', len(test_data), '字符')

        # 创建评分提取器实例
        extractor = IntelligentScoringExtractor([test_data])

        # 提取评分规则
        print('\n开始提取评分规则...')
        rules = extractor.extract_scoring_rules()

        # 输出结果
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
        else:
            print('❌ 未能提取到评分规则')

        print('\n' + '=' * 50 + '\n')


def test_pdf_file(pdf_file_path):
    """测试PDF文件的评分规则提取"""
    print(f'=== 测试PDF文件: {pdf_file_path} ===\n')

    if not os.path.exists(pdf_file_path):
        print(f'❌ 文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print('开始处理PDF文件...')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 如果页面太多，分段处理
        if len(pages_text) > 10:
            print('文件较长，将分段处理...')
            # 每10页为一段进行处理
            segment_size = 10
            all_rules = []

            for i in range(0, len(pages_text), segment_size):
                segment_pages = pages_text[i : i + segment_size]
                segment_text = '\n'.join(segment_pages)

                print(
                    f'\n--- 处理段落 {i // segment_size + 1} (页 {i + 1}-{min(i + segment_size, len(pages_text))}) ---'
                )
                print(f'段落文本长度: {len(segment_text)} 字符')

                # 创建评分提取器实例
                extractor = IntelligentScoringExtractor(segment_pages)

                # 提取评分规则
                print('开始提取评分规则...')
                rules = extractor.extract_scoring_rules()

                if rules:
                    print(f'成功提取到 {len(rules)} 条评分规则:')
                    print_scoring_rules(rules)
                    all_rules.extend(rules)
                else:
                    print('未能提取到评分规则')

            # 合并所有规则并去重
            if all_rules:
                print('\n=== 合并结果 ===')
                print(f'总共提取到 {len(all_rules)} 条评分规则')
                # 这里可以添加规则合并逻辑
                print_scoring_rules(all_rules)
            else:
                print('未能从任何段落中提取到评分规则')
        else:
            # 页面较少，一次性处理
            print('开始提取评分规则...')
            extractor = IntelligentScoringExtractor(pages_text)
            rules = extractor.extract_scoring_rules()

            if rules:
                print(f'成功提取到 {len(rules)} 条主要评分规则:')
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
            else:
                print('❌ 未能提取到评分规则')

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()


def test_edge_cases():
    """测试边界情况"""
    print('=== 边界情况测试 ===\n')

    # 测试空内容
    print('--- 测试空内容 ---')
    extractor = IntelligentScoringExtractor([''])
    rules = extractor.extract_scoring_rules()
    print(f'空内容测试结果: 提取到 {len(rules)} 条规则')

    # 测试无评分规则内容
    print('\n--- 测试无评分规则内容 ---')
    no_rules_content = ['这是一份没有评分规则的普通文档内容。']
    extractor = IntelligentScoringExtractor(no_rules_content)
    rules = extractor.extract_scoring_rules()
    print(f'无评分规则内容测试结果: 提取到 {len(rules)} 条规则')

    # 测试只有价格规则的内容
    print('\n--- 测试只有价格规则的内容 ---')
    price_only_content = [
        """
价格评分标准（100分）
投标报价得分=（评标基准价/投标报价）×价格分值
评标基准价为满足招标文件要求且投标价格最低的投标报价。
    """
    ]
    extractor = IntelligentScoringExtractor(price_only_content)
    rules = extractor.extract_scoring_rules()
    print(f'价格规则内容测试结果: 提取到 {len(rules)} 条规则')
    if rules:
        total_score = sum(rule['max_score'] for rule in rules)
        print(f'总分: {total_score}分')

    print('\n' + '=' * 50 + '\n')


if __name__ == '__main__':
    # 检查命令行参数
    if len(sys.argv) > 1:
        pdf_file_path = sys.argv[1]
        test_pdf_file(pdf_file_path)
    else:
        # 运行默认测试
        test_scoring_extractor()
        test_edge_cases()

    print('测试完成!')
