#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试评分规则提取和处理流程
"""

import sys
import os
import json

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.table_analyzer import TableAnalyzer
from modules.scoring_extractor import IntelligentScoringExtractor
from modules.database import SessionLocal, ScoringRule, TenderProject


def test_scoring_extraction(pdf_path, output_path="test_scoring_rules.json"):
    """
    测试评分规则提取流程
    
    Args:
        pdf_path: PDF文件路径
        output_path: 输出文件路径
    """
    print("开始测试评分规则提取流程...")
    
    # 1. 使用新的提取器直接从PDF提取规则
    print("1. 使用 IntelligentScoringExtractor 从PDF提取规则...")
    extractor = IntelligentScoringExtractor()
    scoring_rules = extractor.extract(pdf_path)
    
    # 2. 保存评分规则
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(scoring_rules, f, ensure_ascii=False, indent=2)
    print(f"评分规则已保存到 {output_path}")
    
    # 3. 显示评分规则摘要
    print("\n评分规则摘要:")
    def print_rules(rules, level=0):
        indent = "  " * level
        for rule in rules:
            print(f"{indent}- {rule['criteria_name']} (满分: {rule['max_score']})")
            if 'children' in rule and rule['children']:
                print_rules(rule['children'], level + 1)
    
    if scoring_rules:
        print_rules(scoring_rules)
    else:
        print("未能提取任何评分规则。")
    
    return scoring_rules



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_scoring_extraction.py <pdf文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # 测试评分规则提取
    scoring_rules = test_scoring_extraction(pdf_path)
    
    print("\n测试完成!")