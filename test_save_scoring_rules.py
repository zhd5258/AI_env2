#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试评分规则保存到数据库的功能
"""

import sys
import os
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

def test_save_scoring_rules():
    """
    测试评分规则保存到数据库的功能
    """
    print("测试评分规则保存到数据库的功能")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目6是否存在
        project = session.query(TenderProject).filter(TenderProject.id == 6).first()
        if not project:
            print("错误：项目6不存在")
            return
            
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  招标文件路径: {project.tender_file_path}")
        print(f"  状态: {project.status}")
        
        # 尝试提取评分规则
        print(f"\n尝试提取评分规则:")
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(project.tender_file_path)
        print(f"  提取到 {len(rules)} 条评分规则")
        
        # 显示提取到的规则
        for i, rule in enumerate(rules):
            print(f"    规则 {i+1}: {rule}")
        
        # 尝试保存到数据库
        print(f"\n尝试保存评分规则到数据库:")
        handler = TestDBHandler()
        success = handler.save_scoring_rules_to_db(project.id, rules)
        
        if success:
            print("  评分规则保存成功")
            
            # 检查数据库中的规则
            db_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project.id).all()
            print(f"  数据库中现在有 {len(db_rules)} 条评分规则")
            for rule in db_rules:
                print(f"    规则: {rule.Parent_Item_Name} - {rule.Child_Item_Name}")
        else:
            print("  评分规则保存失败")
        
        session.close()
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_save_scoring_rules()