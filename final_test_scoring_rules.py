#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整测试评分规则提取和保存功能
"""

import sys
import os
import json

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

def final_test():
    """
    完整测试评分规则提取和保存功能
    """
    pdf_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"错误：找不到PDF文件 {pdf_path}")
        return
    
    print("开始完整测试评分规则提取和保存功能")
    print("=" * 80)
    
    try:
        # 1. 使用评分提取器提取规则
        print("1. 提取评分规则...")
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(pdf_path)
        
        print(f"   成功提取到 {len(rules)} 条评分规则")
        
        # 保存提取结果到文件
        with open('final_extracted_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
        print("   提取结果已保存到 final_extracted_rules.json")
        
        # 2. 验证提取结果
        print("\n2. 验证提取结果...")
        if rules:
            # 检查规则数量
            print(f"   总规则数: {len(rules)}")
            
            # 检查价格规则
            price_rule = rules[-1] if rules and rules[-1].get('is_price_criteria', False) else None
            if price_rule:
                print("   价格规则检查:")
                print(f"     名称: {price_rule.get('criteria_name')}")
                print(f"     分值: {price_rule.get('max_score')}")
                print(f"     描述: {price_rule.get('description')}")
                print(f"     是否有子项: {'是' if price_rule.get('children', []) else '否'}")
                if not price_rule.get('children', []):
                    print("     ✓ 价格规则处理正确")
                else:
                    print("     ✗ 价格规则处理错误")
            else:
                print("   未找到价格规则")
                
            # 检查其他规则
            non_price_rules = [r for r in rules if not r.get('is_price_criteria', False)]
            print(f"   非价格规则数: {len(non_price_rules)}")
            
        # 3. 保存到数据库
        print("\n3. 保存到数据库...")
        project_id = 16  # 使用新的项目ID
        handler = TestDBHandler()
        success = handler.save_scoring_rules_to_db(project_id, rules)
        
        if success:
            print("   ✓ 评分规则成功保存到数据库")
            
            # 4. 验证数据库保存结果
            print("\n4. 验证数据库保存结果...")
            session = SessionLocal()
            try:
                db_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.id).all()
                print(f"   数据库中保存了 {len(db_rules)} 条评分规则")
                
                # 统计各类规则
                parent_rules = [r for r in db_rules if r.Parent_Item_Name and not r.Child_Item_Name]
                child_rules = [r for r in db_rules if r.Child_Item_Name]
                price_rules = [r for r in db_rules if r.is_price_criteria]
                
                print(f"   父项规则数: {len(parent_rules)}")
                print(f"   子项规则数: {len(child_rules)}")
                print(f"   价格规则数: {len(price_rules)}")
                
                # 验证价格规则
                if price_rules:
                    price_rule = price_rules[0]
                    print("   价格规则数据库验证:")
                    print(f"     名称: {price_rule.Parent_Item_Name}")
                    print(f"     分值: {price_rule.Parent_max_score}")
                    print(f"     描述: {price_rule.description}")
                    print(f"     子项名称: {price_rule.Child_Item_Name}")
                    print(f"     子项分值: {price_rule.Child_max_score}")
                    if price_rule.Child_Item_Name is None and price_rule.Child_max_score is None:
                        print("     ✓ 价格规则数据库存储正确")
                    else:
                        print("     ✗ 价格规则数据库存储错误")
                else:
                    print("   数据库中未找到价格规则")
                    
                # 验证清理功能
                incomplete_rules = [r for r in db_rules 
                                 if r.Parent_Item_Name is not None 
                                 and r.Child_Item_Name is None 
                                 and r.Child_max_score is None
                                 and not r.is_price_criteria]
                if not incomplete_rules:
                    print("   ✓ 规则清理功能正常")
                else:
                    print(f"   ✗ 仍有 {len(incomplete_rules)} 条不完整规则未被清理")
                    
            finally:
                session.close()
        else:
            print("   ✗ 评分规则保存到数据库失败")
            
        print("\n" + "=" * 80)
        print("测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    final_test()