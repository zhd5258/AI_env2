#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试包含父子项结构的评分规则处理
"""

import sys
import os

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

def test_parent_child_rules():
    """
    测试包含父子项结构的评分规则处理
    """
    print("测试包含父子项结构的评分规则处理")
    print("=" * 50)
    
    # 创建包含父子项结构的测试数据
    test_rules = [
        {
            "criteria_name": "技术部分",
            "max_score": 50,
            "description": "技术评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "技术方案",
                    "max_score": 25,
                    "description": "技术方案评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "技术团队",
                    "max_score": 15,
                    "description": "技术团队评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "项目经验",
                    "max_score": 10,
                    "description": "类似项目经验评价标准",
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
                    "max_score": 20,
                    "description": "企业资质评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "财务状况",
                    "max_score": 10,
                    "description": "财务状况评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        },
        {
            "criteria_name": "价格部分",
            "max_score": 40,
            "description": "价格评分标准",
            "is_veto": False,
            "is_price_criteria": True,
            "price_formula": "评标基准价/投标报价×价格分值",
            "children": []
        }
    ]
    
    project_id = 12  # 使用新的项目ID
    
    # 执行完整处理流程
    handler = TestDBHandler()
    success = handler.save_scoring_rules_to_db(project_id, test_rules)
    
    if success:
        print("✓ 评分规则处理流程执行成功")
        
        # 验证最终结果
        session = SessionLocal()
        try:
            rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
            print(f"✓ 最终保存了 {len(rules)} 条评分规则")
            
            print("\n处理后的评分规则:")
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
                
            # 验证处理结果
            parent_names = [rule.Parent_Item_Name for rule in rules if rule.Parent_Item_Name]
            if all(name == "技术部分" for name in parent_names):
                print("✓ 父项名称继承正确")
            else:
                print("✗ 父项名称继承存在问题")
                print(f"  实际父项名称: {parent_names}")
                
            parent_scores = [rule.Parent_max_score for rule in rules if rule.Parent_max_score]
            if all(score == 50 for score in parent_scores):
                print("✓ 父项分数继承正确")
            else:
                print("✗ 父项分数继承存在问题")
                print(f"  实际父项分数: {parent_scores}")
                
        finally:
            session.close()
    else:
        print("✗ 评分规则处理流程执行失败")

def show_before_processing():
    """
    显示处理前的规则结构
    """
    print("处理前的评分规则结构:")
    print("=" * 50)
    
    test_rules = [
        {
            "criteria_name": "技术部分",
            "max_score": 50,
            "description": "技术评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "技术方案",
                    "max_score": 25,
                    "description": "技术方案评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                },
                {
                    "criteria_name": "技术团队",
                    "max_score": 15,
                    "description": "技术团队评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        },
        {
            "criteria_name": "",  # 空的父项名称
            "max_score": 0,       # 空的父项分数
            "description": "商务评分标准",
            "is_veto": False,
            "is_price_criteria": False,
            "price_formula": None,
            "children": [
                {
                    "criteria_name": "企业资质",
                    "max_score": 20,
                    "description": "企业资质评价标准",
                    "is_veto": False,
                    "is_price_criteria": False,
                    "price_formula": None
                }
            ]
        }
    ]
    
    for i, rule in enumerate(test_rules, 1):
        print(f"规则 {i}:")
        print(f"  父项名称: '{rule['criteria_name']}'")
        print(f"  父项分数: {rule['max_score']}")
        print(f"  描述: {rule['description']}")
        if rule['children']:
            print("  子项:")
            for j, child in enumerate(rule['children'], 1):
                print(f"    子项 {j}:")
                print(f"      名称: {child['criteria_name']}")
                print(f"      分数: {child['max_score']}")
                print(f"      描述: {child['description']}")
        print()

if __name__ == "__main__":
    show_before_processing()
    test_parent_child_rules()