#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试评分规则保存到数据库功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin
from modules.database import SessionLocal, ScoringRule
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def test_save_rules_to_db():
    """
    测试评分规则保存到数据库功能
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
        
        print(f"成功提取到 {len(rules)} 条评分规则")
        
        # 保存到数据库
        project_id = 15  # 使用新的项目ID
        handler = TestDBHandler()
        success = handler.save_scoring_rules_to_db(project_id, rules)
        
        if success:
            print("✓ 评分规则成功保存到数据库")
            
            # 验证保存的数据
            session = SessionLocal()
            try:
                db_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
                print(f"✓ 数据库中保存了 {len(db_rules)} 条评分规则")
                
                print("\n数据库中的评分规则:")
                for rule in db_rules:
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
                    
                # 特别检查价格规则
                print("=" * 50)
                print("价格规则验证:")
                price_rules = [r for r in db_rules if r.is_price_criteria]
                if price_rules:
                    price_rule = price_rules[0]
                    print(f"  价格规则名称: {price_rule.Parent_Item_Name}")
                    print(f"  价格规则分值: {price_rule.Parent_max_score}")
                    print(f"  价格规则描述: {price_rule.description}")
                    print(f"  价格计算公式: {price_rule.price_formula}")
                    if price_rule.Child_Item_Name is None and price_rule.Child_max_score is None:
                        print("  ✓ 价格规则数据库存储正确：没有子项字段")
                    else:
                        print("  ✗ 价格规则数据库存储错误：仍有子项字段")
                else:
                    print("  未找到价格规则")
                    
            finally:
                session.close()
        else:
            print("✗ 评分规则保存到数据库失败")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_save_rules_to_db()