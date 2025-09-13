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
    测试新的评分规则处理逻辑
    """
    # 创建测试数据 - 模拟从PDF提取的规则
    # 这里创建一些有完整父子关系的规则，以及一些不完整的规则用于测试清理功能
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
    
    # 保存到数据库进行测试
    project_id = 8  # 使用新的项目ID
    
    # 关闭可能存在的数据库连接
    close_existing_connections()
    
    handler = TestDBHandler()
    success = handler.save_scoring_rules_to_db(project_id, test_rules)
    
    if success:
        print("✓ 评分规则成功保存到数据库")
        
        # 验证保存的数据
        session = SessionLocal()
        try:
            rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
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
        finally:
            session.close()
    else:
        print("✗ 评分规则保存到数据库失败")

def test_rule_cleaning():
    """
    测试规则清理功能，专门创建一些需要清理的不完整规则
    """
    print("测试规则清理功能...")
    
    session = SessionLocal()
    try:
        project_id = 9  # 新的测试项目ID
        
        # 先删除可能存在的测试数据
        session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        
        # 手动插入一些不完整的规则用于测试清理功能
        # 这些规则Parent_Item_Name不为空，但Child_Item_Name为空
        
        # 插入不完整的规则（Parent有值但Child为空）
        incomplete_rule1 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="技术部分",
            Parent_max_score=40,
            Child_Item_Name=None,
            Child_max_score=None,
            description="不完整的规则1",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        incomplete_rule2 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="商务部分",
            Parent_max_score=30,
            Child_Item_Name=None,
            Child_max_score=None,
            description="不完整的规则2",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 插入完整的规则作为对照
        complete_rule1 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="价格部分",
            Parent_max_score=30,
            Child_Item_Name="价格评分",
            Child_max_score=30,
            description="完整规则",
            is_veto=False,
            is_price_criteria=True,
            price_formula="评标基准价/投标报价×价格分值"
        )
        
        session.add_all([incomplete_rule1, incomplete_rule2, complete_rule1])
        session.commit()
        
        print(f"插入测试数据完成，共插入3条规则")
        
        # 手动执行清理操作
        handler = TestDBHandler()
        
        # 重新打开会话执行清理
        session.close()
        
        # 直接调用清理方法测试
        with handler._get_db_session() as db:
            # 获取清理前的规则数量
            before_count = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
            print(f"清理前有 {before_count} 条规则")
            
            # 执行清理
            handler._clean_incomplete_rules(db, project_id)
            db.commit()
            
            # 获取清理后的规则数量
            after_count = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
            print(f"清理后有 {after_count} 条规则")
            print(f"清理了 {before_count - after_count} 条不完整规则")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_rule_processing()
    print("\n" + "="*50 + "\n")
    test_rule_cleaning()