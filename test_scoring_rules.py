#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试评分规则提取功能
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


def test_scoring_rules_extraction(pdf_path):
    """
    测试评分规则提取功能
    
    Args:
        pdf_path: PDF文件路径
    """
    print(f"开始测试评分规则提取功能，PDF路径: {pdf_path}")
    
    if not os.path.exists(pdf_path):
        print(f"错误: 文件 {pdf_path} 不存在")
        return
    
    try:
        # 1. 使用新的提取器直接从PDF提取规则
        print("1. 使用 IntelligentScoringExtractor 从PDF提取规则...")
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(pdf_path)
        
        # 2. 保存评分规则
        with open("scoring_rules.json", "w", encoding="utf-8") as f:
            json.dump(scoring_rules, f, ensure_ascii=False, indent=2)
        print("   评分规则已保存到 scoring_rules.json")
        
        # 3. 显示结果摘要
        print("\n2. 结果摘要:")
        if scoring_rules:
            print(f"   提取到 {len(scoring_rules)} 个评分规则项")
            
            def print_rules(rules, level=0):
                indent = "  " * level
                for rule in rules:
                    print(f"{indent}- {rule['criteria_name']} (满分: {rule['max_score']})")
                    if 'children' in rule and rule['children']:
                        print_rules(rule['children'], level + 1)
            
            print_rules(scoring_rules)
        else:
            print("   未能提取任何评分规则。")
        
        print("\n测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()



if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_scoring_rules.py <pdf文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    test_scoring_rules_extraction(pdf_path)