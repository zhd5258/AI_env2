#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试项目7的评分规则提取
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject
from modules.scoring_extractor import IntelligentScoringExtractor

def test_project7_rule_extraction():
    """
    测试项目7的评分规则提取
    """
    print("测试项目7的评分规则提取")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目7是否存在
        project = session.query(TenderProject).filter(TenderProject.id == 7).first()
        if not project:
            print("错误：项目7不存在")
            return
        
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  状态: {project.status}")
        print(f"  描述: {project.description}")
        print(f"  招标文件路径: {project.tender_file_path}")
        
        # 检查招标文件是否存在
        if not os.path.exists(project.tender_file_path):
            print(f"错误：招标文件不存在 {project.tender_file_path}")
            return
            
        # 尝试提取评分规则
        print(f"\n开始提取评分规则...")
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(project.tender_file_path)
        
        print(f"提取到 {len(scoring_rules)} 条评分规则:")
        if scoring_rules:
            for i, rule in enumerate(scoring_rules):
                print(f"\n评分规则 {i+1}:")
                print(f"  名称: {rule.get('criteria_name', 'N/A')}")
                print(f"  分数: {rule.get('max_score', 'N/A')}")
                print(f"  描述: {rule.get('description', 'N/A')}")
                if 'children' in rule and rule['children']:
                    print(f"  子项数量: {len(rule['children'])}")
                    for j, child in enumerate(rule['children']):
                        print(f"    子项 {j+1}: {child.get('criteria_name', 'N/A')} ({child.get('max_score', 'N/A')}分)")
        else:
            print("未能提取到评分规则")
            
        session.close()
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_project7_rule_extraction()