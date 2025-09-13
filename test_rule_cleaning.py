#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试规则清理功能
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

def test_rule_cleaning():
    """
    测试规则清理功能
    """
    print("测试规则清理功能")
    print("=" * 50)
    
    # 手动创建一些规则用于测试清理功能
    session = SessionLocal()
    project_id = 13  # 新的测试项目ID
    
    try:
        # 先清理可能存在的测试数据
        session.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
        session.commit()
        
        # 创建各种类型的规则用于测试
        
        # 1. 完整的父子项规则（应该保留）
        complete_rule1 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="技术部分",
            Parent_max_score=50,
            Child_Item_Name="技术方案",
            Child_max_score=25,
            description="完整规则1",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 2. 另一个完整的父子项规则（应该保留）
        complete_rule2 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="商务部分",
            Parent_max_score=30,
            Child_Item_Name="企业资质",
            Child_max_score=15,
            description="完整规则2",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 3. 不完整的规则 - 有父项但没有子项（应该被清理）
        # 这种规则Child_Item_Name和Child_max_score都为空，表明它应该是子项但缺少必要信息
        incomplete_rule1 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="价格部分",
            Parent_max_score=40,
            Child_Item_Name=None,      # 没有子项名称
            Child_max_score=None,      # 没有子项分数
            description="不完整规则1",
            is_veto=False,
            is_price_criteria=True,
            price_formula="评标基准价/投标报价×价格分值"
        )
        
        # 4. 另一个不完整的规则（应该被清理）
        incomplete_rule2 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="服务部分",
            Parent_max_score=20,
            Child_Item_Name=None,      # 没有子项名称
            Child_max_score=None,      # 没有子项分数
            description="不完整规则2",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 5. 真正仅有父项的规则（应该保留）
        # 这种规则Child_Item_Name为空，但Child_max_score也为空，Parent_max_score有值
        # 表示这是一个独立的父项规则，不是缺少子项信息的不完整规则
        parent_only_rule = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="总则部分",
            Parent_max_score=10,
            Child_Item_Name=None,
            Child_max_score=None,
            description="仅有父项的规则",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 6. 模拟从PDF提取的规则，Parent有值但Child为空和0分（应该被清理）
        # 这种规则表示本应有子项但子项信息缺失
        incomplete_rule3 = ScoringRule(
            project_id=project_id,
            Parent_Item_Name="质量部分",
            Parent_max_score=15,
            Child_Item_Name=None,
            Child_max_score=None,
            description="本应有子项但缺失",
            is_veto=False,
            is_price_criteria=False,
            price_formula=None
        )
        
        # 添加所有规则到数据库
        session.add_all([
            complete_rule1, 
            complete_rule2, 
            incomplete_rule1, 
            incomplete_rule2,
            parent_only_rule,
            incomplete_rule3
        ])
        session.commit()
        
        print(f"初始规则数量: {session.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()} 条")
        print("初始规则列表:")
        rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
        for rule in rules:
            print(f"  - ID: {rule.id}")
            print(f"    Parent: {rule.Parent_Item_Name} ({rule.Parent_max_score})")
            print(f"    Child: {rule.Child_Item_Name} ({rule.Child_max_score})")
            print(f"    Description: {rule.description}")
            print()
        
        # 执行清理操作
        handler = TestDBHandler()
        with handler._get_db_session() as db:
            print("执行清理操作...")
            handler._clean_incomplete_rules(db, project_id)
            db.commit()
            
            # 检查清理后的结果
            remaining_count = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
            print(f"\n清理后规则数量: {remaining_count} 条")
            print("清理后的规则列表:")
            remaining_rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
            for rule in remaining_rules:
                print(f"  - ID: {rule.id}")
                print(f"    Parent: {rule.Parent_Item_Name} ({rule.Parent_max_score})")
                print(f"    Child: {rule.Child_Item_Name} ({rule.Child_max_score})")
                print(f"    Description: {rule.description}")
                print()
                
            # 分析哪些规则被保留，哪些被清理
            complete_rules = [r for r in remaining_rules if r.Child_Item_Name is not None]
            parent_only_rules = [r for r in remaining_rules if r.Child_Item_Name is None]
            
            print(f"分析结果:")
            print(f"  - 完整父子项规则: {len(complete_rules)} 条 (应保留)")
            print(f"  - 仅有父项的规则: {len(parent_only_rules)} 条 (应保留)")
            
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

def explain_cleaning_logic():
    """
    解释规则清理逻辑
    """
    print("规则清理逻辑说明:")
    print("=" * 50)
    print("根据需求，需要清理满足以下条件的规则:")
    print("1. Parent_Item_Name 不为空或 None")
    print("2. Child_Item_Name 为空或 None")
    print()
    print("但需要注意区分两种情况:")
    print("情况A: 真正的父子项结构，但子项信息缺失 -> 应该清理")
    print("情况B: 独立的父项规则，本身就不需要子项 -> 应该保留")
    print()
    print("为了区分这两种情况，我们增加了判断条件:")
    print("- 如果 Child_max_score 也为空，则认为是情况A，应该清理")
    print("- 如果 Child_max_score 不为空，则认为是情况B，应该保留")
    print()

if __name__ == "__main__":
    explain_cleaning_logic()
    test_rule_cleaning()