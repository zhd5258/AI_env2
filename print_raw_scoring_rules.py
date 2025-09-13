#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
打印从招标文件中提取的未经清洗和整理的评分规则
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.database import SessionLocal, ScoringRule

def print_raw_scoring_rules():
    """
    打印从招标文件中提取的未经清洗和整理的评分规则
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
        raw_rules = extractor.extract(pdf_path)
        
        print(f"成功提取到 {len(raw_rules)} 条原始评分规则:\n")
        
        # 打印原始规则
        for i, rule in enumerate(raw_rules, 1):
            print(f"规则 {i}:")
            print(f"  名称: {rule.get('criteria_name', 'N/A')}")
            print(f"  最高分值: {rule.get('max_score', 'N/A')}")
            print(f"  描述: {rule.get('description', 'N/A')}")
            print(f"  是否否决项: {rule.get('is_veto', False)}")
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
                    print(f"      是否否决项: {child.get('is_veto', False)}")
                    print(f"      是否价格评分标准: {child.get('is_price_criteria', False)}")
                    if child.get('price_formula'):
                        print(f"      价格计算公式: {child.get('price_formula')}")
            print()
            
        # 也保存为JSON格式便于查看
        output_file = "raw_scoring_rules.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(raw_rules, f, ensure_ascii=False, indent=2)
        print(f"原始评分规则已保存到 {output_file}")
        
        # 保存到数据库（不进行清洗）
        save_raw_rules_to_db(raw_rules)
        
    except Exception as e:
        print(f"提取评分规则时出错: {e}")
        import traceback
        traceback.print_exc()

def save_raw_rules_to_db(raw_rules):
    """
    将原始规则保存到数据库，不进行任何清洗和整理
    """
    print("\n" + "=" * 80)
    print("将原始规则保存到数据库（不进行清洗）")
    
    project_id = 11  # 使用新的项目ID
    
    try:
        session = SessionLocal()
        
        # 删除该项目已有的评分规则
        session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        
        # 递归保存规则到数据库
        save_rules_recursive(session, project_id, raw_rules, None)
        
        session.commit()
        print("原始规则已保存到数据库")
        
        # 打印数据库中的规则
        print("\n数据库中的原始规则:")
        rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
        print(f"共 {len(rules)} 条规则:")
        
        for rule in rules:
            print(f"  ID: {rule.id}")
            print(f"    Parent_Item_Name: {rule.Parent_Item_Name}")
            print(f"    Parent_max_score: {rule.Parent_max_score}")
            print(f"    Child_Item_Name: {rule.Child_Item_Name}")
            print(f"    Child_max_score: {rule.Child_max_score}")
            print(f"    Description: {rule.description}")
            print(f"    Is_veto: {rule.is_veto}")
            print(f"    Is_price_criteria: {rule.is_price_criteria}")
            print(f"    Price_formula: {rule.price_formula}")
            print()
            
    except Exception as e:
        session.rollback()
        print(f"保存原始规则到数据库时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

def save_rules_recursive(session, project_id, rules, parent_id):
    """
    递归保存规则到数据库
    """
    for rule in rules:
        try:
            # 确定父项和子项名称
            criteria_name = rule['criteria_name']
            max_score = rule['max_score']
            
            # 创建评分规则对象
            scoring_rule = ScoringRule(
                project_id=project_id,
                Parent_Item_Name=criteria_name[:20] if parent_id is None else None,
                Parent_max_score=int(max_score) if parent_id is None and max_score else None,
                Child_Item_Name=criteria_name[:20] if parent_id is not None else None,
                Child_max_score=int(max_score) if parent_id is not None and max_score else None,
                description=rule.get('description', '')[:100],
                is_veto=rule.get('is_veto', False),
                is_price_criteria=rule.get('is_price_criteria', False),
                price_formula=rule.get('price_formula', None)[:100] if rule.get('price_formula') else None
            )
            
            # 添加到数据库会话
            session.add(scoring_rule)
            session.flush()  # 刷新以获取ID
            
            # 递归处理子项
            if 'children' in rule and rule['children']:
                save_rules_recursive(session, project_id, rule['children'], scoring_rule.id)
        except Exception as e:
            print(f"保存评分规则 '{rule.get('criteria_name', 'Unknown')}' 时出错: {e}")
            continue

if __name__ == "__main__":
    print_raw_scoring_rules()