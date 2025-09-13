#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试分析逻辑的核心功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def test_analysis_logic():
    """
    测试分析逻辑的核心功能
    """
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
    
    print("开始测试分析逻辑核心功能")
    print("=" * 80)
    
    try:
        # 1. 创建测试项目
        session = SessionLocal()
        
        # 创建测试项目
        project = TenderProject(
            name="旧油漆线改造项目测试",
            project_code="ZB2025-001",
            tender_file_path=tender_file_path
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id
        
        print(f"创建测试项目，项目ID: {project_id}")
        
        # 2. 提取并保存评分规则
        print("\n2. 提取评分规则...")
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(tender_file_path)
        
        if rules:
            print(f"   成功提取到 {len(rules)} 条评分规则")
            
            # 保存到数据库
            handler = TestDBHandler()
            success = handler.save_scoring_rules_to_db(project_id, rules)
            
            if success:
                print("   ✓ 评分规则成功保存到数据库")
                
                # 验证保存的规则
                db_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
                print(f"   数据库中保存了 {len(db_rules)} 条评分规则")
                
                # 统计子项规则
                child_rules = [r for r in db_rules if r.Child_Item_Name is not None]
                price_rules = [r for r in db_rules if r.is_price_criteria]
                print(f"   子项规则数: {len(child_rules)}")
                print(f"   价格规则数: {len(price_rules)}")
                
                # 显示子项规则示例
                print("\n   子项规则示例:")
                for i, rule in enumerate(child_rules[:3]):  # 只显示前3个
                    print(f"     {i+1}. {rule.Child_Item_Name} (满分: {rule.Child_max_score})")
                    if rule.description:
                        print(f"         描述: {rule.description[:50]}...")
                
                # 显示价格规则
                if price_rules:
                    price_rule = price_rules[0]
                    print(f"\n   价格规则:")
                    print(f"     名称: {price_rule.Parent_Item_Name}")
                    print(f"     满分: {price_rule.Parent_max_score}")
                    if price_rule.description:
                        print(f"     描述: {price_rule.description}")
            else:
                print("   ✗ 评分规则保存到数据库失败")
        else:
            print("   ✗ 未能提取到评分规则")
            
        session.close()
        
        print("\n" + "=" * 80)
        print("测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 关闭数据库会话
        try:
            session.close()
        except:
            pass

if __name__ == "__main__":
    test_analysis_logic()