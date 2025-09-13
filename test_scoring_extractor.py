#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试评分规则提取器
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.scoring_extractor.core import IntelligentScoringExtractor

def test_scoring_extractor():
    """
    测试评分规则提取器
    """
    pdf_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"错误：找不到PDF文件 {pdf_path}")
        return
    
    print(f"正在从PDF文件提取评分规则: {pdf_path}")
    print("=" * 80)
    
    try:
        # 使用评分提取器提取规则
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(pdf_path)
        
        print(f"成功提取到 {len(rules)} 条评分规则:\n")
        
        # 打印提取到的规则
        for i, rule in enumerate(rules, 1):
            print(f"规则 {i}:")
            print(f"  名称: {rule.get('criteria_name', 'N/A')}")
            print(f"  最高分值: {rule.get('max_score', 'N/A')}")
            print(f"  描述: {rule.get('description', 'N/A')}")
            print(f"  是否价格评分标准: {rule.get('is_price_criteria', False)}")
            if rule.get('price_formula'):
                print(f"  价格计算公式: {rule.get('price_formula')}")
            
            # 打印子项（如果有）
            if 'children' in rule and rule['children']:
                print("  子项:")
                for j, child in enumerate(rule['children'], 1):
                    print(f"    子项 {j}:")
                    print(f"      名称: {child.get('criteria_name', 'N/A')}")
                    print(f"      最高分值: {child.get('max_score', 'N/A')}")
                    print(f"      描述: {child.get('description', 'N/A')}")
                    print(f"      是否价格评分标准: {child.get('is_price_criteria', False)}")
                    if child.get('price_formula'):
                        print(f"      价格计算公式: {child.get('price_formula')}")
            print()
            
        # 保存为JSON格式便于查看
        output_file = "extracted_scoring_rules.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print(f"提取的评分规则已保存到 {output_file}")
        
        # 特别检查价格规则
        print("=" * 80)
        print("价格规则验证:")
        if rules and rules[-1].get('is_price_criteria', False):
            price_rule = rules[-1]
            print(f"  价格规则名称: {price_rule.get('criteria_name')}")
            print(f"  价格规则分值: {price_rule.get('max_score')}")
            print(f"  价格规则描述: {price_rule.get('description')}")
            print(f"  是否有子项: {'是' if price_rule.get('children', []) else '否'}")
            if not price_rule.get('children', []):
                print("  ✓ 价格规则处理正确：没有子项")
            else:
                print("  ✗ 价格规则处理错误：仍有子项")
        else:
            print("  未找到价格规则")
        
    except Exception as e:
        print(f"提取评分规则时出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scoring_extractor()