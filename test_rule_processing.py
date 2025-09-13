#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修改后的评分规则处理逻辑
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.scoring_extractor.db_handler import DBHandlerMixin
from modules.database import SessionLocal, ScoringRule
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def close_existing_connections():
    """关闭可能存在的数据库连接"""
    try:
        # 等待一段时间确保其他连接释放
        time.sleep(1)
    except:
        pass

def test_rule_processing():
    """
    测试评分规则处理逻辑
    """
    # 创建测试数据 - 模拟从PDF提取的规则
    test_rules = [
        {
            "criteria_name": "技术部分",
            "max_score": 40,
            "description": "技术评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "技术方案",
                    "max_score": 20,
                    "description": "技术方案评价",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "技术团队",
                    "max_score": 20,
                    "description": "技术团队评价",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        },
        {
            "criteria_name": "",  # 空的父项名称，应该继承上一个父项名称
            "max_score": 0,       # 空的父项分数，应该继承上一个父项分数
            "description": "商务评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "企业资质",
                    "max_score": 10,
                    "description": "企业资质评价",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        },
        {
            "criteria_name": "价格部分",
            "max_score": 30,
            "description": "价格评分标准",
            "is_veto": False,
            "is_price_criteria": True,
            "price_formula": "评标基准价/投标报价×价格分值",
            "children": []
        }
    ]
    
    # 测试规则处理
    handler = TestDBHandler()
    processed_rules = handler._process_scoring_rules(test_rules)
    
    print("处理后的评分规则:")
    for i, rule in enumerate(processed_rules):
        print(f"  规则 {i+1}:")
        print(f"    名称: {rule.get('criteria_name')}")
        print(f"    分数: {rule.get('max_score')}")
        print(f"    描述: {rule.get('description')}")
        if 'children' in rule and rule['children']:
            print("    子项:")
            for j, child in enumerate(rule['children']):
                print(f"      子项 {j+1}: {child.get('criteria_name')} ({child.get('max_score')}分)")
        print()
    
    # 保存到数据库进行测试
    project_id = 4  # 使用新的项目ID
    
    # 关闭可能存在的数据库连接
    close_existing_connections()
    
    session = SessionLocal()
    try:
        # 删除现有测试数据
        session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        session.commit()
        
        # 保存处理后的规则
        success = handler.save_scoring_rules_to_db(project_id, test_rules)
        
        if success:
            print("✓ 评分规则成功保存到数据库")
            
            # 验证保存的数据
            rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
            print(f"✓ 共保存了 {len(rules)} 条评分规则")
            
            print("\n数据库中的评分规则:")
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
        else:
            print("✗ 评分规则保存到数据库失败")
            
    except Exception as e:
        print(f"✗ 处理评分规则时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

def test_rule_inheritance():
    """
    单独测试规则继承逻辑
    """
    print("测试规则继承逻辑...")
    
    # 创建测试数据
    test_rules = [
        {
            "criteria_name": "技术部分",
            "max_score": 40,
            "description": "技术评分标准",
            "children": [
                {"criteria_name": "技术方案", "max_score": 20},
                {"criteria_name": "技术团队", "max_score": 20}
            ]
        },
        {
            "criteria_name": "",  # 空的父项名称
            "max_score": 0,       # 空的父项分数
            "description": "商务评分标准",
            "children": [
                {"criteria_name": "企业资质", "max_score": 10}
            ]
        }
    ]
    
    handler = TestDBHandler()
    processed_rules = handler._process_scoring_rules(test_rules)
    
    print("处理前:")
    print(f"  规则1: {test_rules[0]['criteria_name']} ({test_rules[0]['max_score']}分)")
    print(f"  规则2: '{test_rules[1]['criteria_name']}' ({test_rules[1]['max_score']}分)")
    
    print("\n处理后:")
    print(f"  规则1: {processed_rules[0]['criteria_name']} ({processed_rules[0]['max_score']}分)")
    print(f"  规则2: {processed_rules[1]['criteria_name']} ({processed_rules[1]['max_score']}分)")

if __name__ == "__main__":
    test_rule_inheritance()
    print("\n" + "="*50 + "\n")
    test_rule_processing()