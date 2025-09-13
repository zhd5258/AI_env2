#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
设置测试项目并提取评分规则
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

def setup_test_project():
    """
    设置测试项目并提取评分规则
    """
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
    
    print("开始设置测试项目并提取评分规则")
    print("=" * 80)
    
    try:
        # 1. 创建测试项目
        session = SessionLocal()
        
        # 检查是否已存在测试项目
        existing_project = session.query(TenderProject).filter(TenderProject.project_code == "ZB2025-006").first()
        if existing_project:
            project_id = existing_project.id
            print(f"使用现有测试项目，项目ID: {project_id}")
        else:
            # 创建测试项目
            project = TenderProject(
                name="旧油漆线改造项目测试",
                project_code="ZB2025-006",  # 使用不同的项目代码
                tender_file_path=tender_file_path
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            project_id = project.id
            
            print(f"创建测试项目，项目ID: {project_id}")
        
        # 2. 提取并保存评分规则
        scoring_rules_count = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
        if scoring_rules_count == 0:
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
                else:
                    print("   ✗ 评分规则保存到数据库失败")
            else:
                print("   ✗ 未能提取到评分规则")
        else:
            print(f"\n2. 评分规则已存在，共 {scoring_rules_count} 条")
            
        # 3. 显示评分规则详情
        print("\n3. 评分规则详情...")
        scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
        
        for i, rule in enumerate(scoring_rules):
            print(f"   规则 {i+1}:")
            print(f"     大项名称: {rule.Parent_Item_Name}")
            print(f"     大项分数: {rule.Parent_max_score}")
            print(f"     子项名称: {rule.Child_Item_Name}")
            print(f"     子项分数: {rule.Child_max_score}")
            print(f"     描述: {rule.description[:50] if rule.description else 'N/A'}{'...' if rule.description and len(rule.description) > 50 else ''}")
            print(f"     是否价格规则: {rule.is_price_criteria}")
            print()
        
        session.close()
        
        print("=" * 80)
        print("测试项目设置和评分规则提取完成!")
        
    except Exception as e:
        print(f"设置过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 关闭数据库会话
        try:
            session.close()
        except:
            pass

if __name__ == "__main__":
    setup_test_project()