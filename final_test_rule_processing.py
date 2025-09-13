#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最终测试评分规则处理逻辑，验证完整的三步处理流程
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

def test_complete_processing():
    """
    测试完整的三步处理流程：
    1. 正常提取并存储全部规则
    2. 更新父项信息继承
    3. 清理不完整规则
    """
    print("测试完整的评分规则处理流程...")
    
    # 创建测试数据
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
            "criteria_name": "",  # 空的父项名称
            "max_score": 0,       # 空的父项分数
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
        }
    ]
    
    project_id = 10  # 新的测试项目ID
    
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
            
            print("\n最终数据库中的评分规则:")
            for rule in rules:
                print(f"  - ID: {rule.id}")
                print(f"    Parent_Item_Name: {rule.Parent_Item_Name}")
                print(f"    Parent_max_score: {rule.Parent_max_score}")
                print(f"    Child_Item_Name: {rule.Child_Item_Name}")
                print(f"    Child_max_score: {rule.Child_max_score}")
                print(f"    Description: {rule.description[:50]}..." if rule.description and len(rule.description) > 50 else f"    Description: {rule.description}")
                print()
                
            # 验证处理结果是否符合预期
            # 1. 检查父项信息继承是否正确
            parent_names = [rule.Parent_Item_Name for rule in rules]
            parent_scores = [rule.Parent_max_score for rule in rules]
            
            if all(name == "技术部分" for name in parent_names):
                print("✓ 父项名称继承正确")
            else:
                print("✗ 父项名称继承存在问题")
                
            if all(score == 40 for score in parent_scores):
                print("✓ 父项分数继承正确")
            else:
                print("✗ 父项分数继承存在问题")
                
            # 2. 检查是否保留了完整的父子项结构
            complete_rules = [rule for rule in rules if rule.Child_Item_Name is not None]
            if len(complete_rules) == len(rules):
                print("✓ 所有规则都具有完整的父子项结构")
            else:
                print("✗ 存在不完整的规则")
                
        finally:
            session.close()
    else:
        print("✗ 评分规则处理流程执行失败")

if __name__ == "__main__":
    test_complete_processing()