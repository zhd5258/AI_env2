#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查项目6的招标文件处理情况
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
from modules.scoring_extractor.core import IntelligentScoringExtractor

def check_tender_processing():
    """
    检查项目6的招标文件处理情况
    """
    print("检查项目6的招标文件处理情况")
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
        
        # 检查招标文件是否存在
        if not os.path.exists(project.tender_file_path):
            print(f"错误：招标文件不存在 {project.tender_file_path}")
            return
            
        # 尝试提取评分规则
        print(f"\n尝试提取评分规则:")
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(project.tender_file_path)
        print(f"  提取到 {len(rules)} 条评分规则")
        
        for i, rule in enumerate(rules):
            print(f"    规则 {i+1}:")
            print(f"      父项名称: {rule.get('Parent_Item_Name', 'N/A')}")
            print(f"      父项分数: {rule.get('Parent_max_score', 'N/A')}")
            print(f"      子项名称: {rule.get('Child_Item_Name', 'N/A')}")
            print(f"      子项分数: {rule.get('Child_max_score', 'N/A')}")
            print(f"      是否价格规则: {rule.get('is_price_criteria', False)}")
            if rule.get('is_price_criteria', False):
                print(f"      价格规则描述: {rule.get('description', 'N/A')}")
        
        session.close()
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_tender_processing()