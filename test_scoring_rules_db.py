#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试评分规则是否能正确保存到新的数据库结构中
"""

import sys
import os
import sqlite3

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor

def test_scoring_rules_db():
    """
    测试评分规则数据库操作
    """
    # 创建测试数据
    test_rules = [
        {
            "criteria_name": "商务评分标准",
            "max_score": 30,
            "description": "商务部分评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "企业资质",
                    "max_score": 10,
                    "description": "企业相关资质认证情况",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "业绩情况",
                    "max_score": 20,
                    "description": "类似项目业绩情况",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        },
        {
            "criteria_name": "价格评分标准",
            "max_score": 40,
            "description": "价格评分计算方法",
            "is_veto": False,
            "is_price_criteria": True,
            "price_formula": "投标报价得分=评标基准价/投标报价×100",
        }
    ]
    
    # 保存到数据库
    session = SessionLocal()
    try:
        project_id = 1
        
        # 删除现有测试数据
        session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        
        # 保存父项
        for rule in test_rules:
            parent_rule = ScoringRule(
                project_id=project_id,
                Parent_Item_Name=rule["criteria_name"][:20],
                Parent_max_score=int(rule["max_score"]),
                description=rule["description"][:100],
                is_veto=rule["is_veto"],
                is_price_criteria=rule["is_price_criteria"],
                price_formula=rule["price_formula"][:100] if rule["price_formula"] else None
            )
            session.add(parent_rule)
            session.flush()
            
            # 保存子项
            if "children" in rule:
                for child in rule["children"]:
                    child_rule = ScoringRule(
                        project_id=project_id,
                        Child_Item_Name=child["criteria_name"][:20],
                        Child_max_score=int(child["max_score"]),
                        description=child["description"][:100],
                        is_veto=child["is_veto"],
                        is_price_criteria=child["is_price_criteria"],
                        price_formula=child["price_formula"][:100] if child["price_formula"] else None
                    )
                    session.add(child_rule)
        
        session.commit()
        print("✓ 评分规则成功保存到数据库")
        
        # 验证保存的数据
        rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
        print(f"✓ 共保存了 {len(rules)} 条评分规则")
        
        for rule in rules:
            print(f"  - ID: {rule.id}")
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
        print(f"✗ 保存评分规则时出错: {e}")
    finally:
        session.close()

def test_pdf_scoring_rules_extraction():
    """
    测试从PDF文件提取评分规则并保存到数据库
    """
    pdf_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"✗ PDF文件不存在: {pdf_path}")
        return False
    
    try:
        # 提取评分规则
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(pdf_path)
        
        if not scoring_rules:
            print("✗ 未能从PDF中提取到评分规则")
            return False
        
        print(f"✓ 成功从PDF中提取到 {len(scoring_rules)} 条评分规则")
        
        # 显示提取的规则
        print("\n提取的评分规则:")
        for i, rule in enumerate(scoring_rules):
            print(f"  {i+1}. {rule.get('criteria_name', '未知')} (分值: {rule.get('max_score', 0)})")
            if 'children' in rule and rule['children']:
                for j, child in enumerate(rule['children']):
                    print(f"     - {child.get('criteria_name', '未知')} (分值: {child.get('max_score', 0)})")
        
        # 保存到数据库
        session = SessionLocal()
        try:
            project_id = 2  # 使用不同的项目ID
            
            # 删除现有测试数据
            session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
            
            # 保存父项和子项
            save_rules_recursive(session, project_id, scoring_rules, None)
            
            session.commit()
            print("\n✓ PDF评分规则成功保存到数据库")
            
            # 验证保存的数据
            rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
            print(f"✓ 共保存了 {len(rules)} 条评分规则")
            
            for rule in rules:
                print(f"  - ID: {rule.id}")
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
            print(f"✗ 保存PDF评分规则时出错: {e}")
            return False
        finally:
            session.close()
            
        return True
    except Exception as e:
        print(f"✗ 提取PDF评分规则时出错: {e}")
        return False

def save_rules_recursive(session, project_id, rules, parent_id):
    """
    递归保存评分规则到数据库
    """
    for rule in rules:
        try:
            # 创建评分规则对象
            scoring_rule = ScoringRule(
                project_id=project_id,
                Parent_Item_Name=rule['criteria_name'][:20] if parent_id is None else None,
                Parent_max_score=int(rule['max_score']) if parent_id is None else None,
                Child_Item_Name=rule['criteria_name'][:20] if parent_id is not None else None,
                Child_max_score=int(rule['max_score']) if parent_id is not None else None,
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

def verify_db_structure():
    """
    验证数据库表结构
    """
    conn = sqlite3.connect('tender_evaluation.db')
    cursor = conn.cursor()
    
    try:
        # 获取表结构信息
        cursor.execute("PRAGMA table_info(scoring_rule)")
        columns = cursor.fetchall()
        
        print("scoring_rule表结构:")
        print("列名\t\t\t类型\t\t是否可为空\t默认值\t\t主键")
        print("-" * 80)
        for col in columns:
            cid, name, type_, notnull, default_value, pk = col
            print(f"{name}\t\t\t{type_}\t\t{notnull}\t\t{default_value}\t\t{pk}")
            
    except Exception as e:
        print(f"验证表结构时出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("验证数据库表结构...")
    verify_db_structure()
    
    print("\n测试评分规则保存...")
    test_scoring_rules_db()
    
    print("\n测试从PDF文件提取评分规则...")
    test_pdf_scoring_rules_extraction()