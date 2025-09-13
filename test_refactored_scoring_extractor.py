#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试重构后的评分规则提取功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.scoring_extractor import IntelligentScoringExtractor, ScoringRuleParser


def test_scoring_rule_parser():
    """测试评分规则解析器"""
    print("测试评分规则解析器...")
    
    # 创建解析器实例
    parser = ScoringRuleParser()
    
    # 测试数据
    test_tables = [
        {
            "headers": ["评价项目", "", "评价标准"],
            "rows": [
                {
                    "评价项目": "商务部分(18分)",
                    "": "企业证书，认证体系（5分）",
                    "评价标准": "响应人须具备有效的质量管理体系、环境管理体系、职业健康管理体系认证证书，具备一项得1分，最多得5分。（复印件加盖公章）"
                },
                {
                    "评价项目": "",
                    "": "标书的完整性(5分）",
                    "评价标准": "标书的完整性好得5分，有偏差项每项扣1分，该项分值扣完为止。"
                },
                {
                    "评价项目": "价格分（40分）",
                    "": "满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分。其他投标人的价格分统一按照下列公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100",
                    "评价标准": ""
                }
            ]
        }
    ]
    
    # 解析评分规则
    rules = parser.parse_scoring_rules_from_table_data(test_tables)
    
    print(f"解析到 {len(rules)} 条评分规则:")
    for i, rule in enumerate(rules):
        print(f"  {i+1}. {rule['criteria_name']} (满分: {rule['max_score']})")
        if rule.get('description'):
            print(f"      描述: {rule['description']}")
        if rule.get('is_price_criteria'):
            print(f"      价格公式: {rule.get('price_formula', '')}")
    
    return rules


def test_new_extractor():
    """测试新的评分提取器"""
    print("\n测试新的评分提取器...")
    
    # 创建提取器实例
    extractor = IntelligentScoringExtractor()
    
    # 检查是否有方法
    methods = [
        'extract',
        'generate_scoring_template'
    ]
    
    print("检查方法存在性:")
    for method in methods:
        if hasattr(extractor, method):
            print(f"  ✓ {method}")
        else:
            print(f"  ✗ {method}")



if __name__ == "__main__":
    print("开始测试重构后的评分规则提取功能...")
    
    # 测试评分规则解析器
    rules = test_scoring_rule_parser()
    
    # 测试新的评分提取器
    test_new_extractor()
    
    print("\n测试完成!")