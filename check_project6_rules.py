#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查项目6的评分规则情况
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, ScoringRule

def check_project6_rules():
    """
    检查项目6的评分规则情况
    """
    print("检查项目6的评分规则情况")
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
        print(f"  状态: {project.status}")
        print(f"  描述: {project.description}")
        
        # 检查项目6的评分规则
        scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 6).all()
        print(f"\n项目6的评分规则数量: {len(scoring_rules)}")
        
        if scoring_rules:
            for i, rule in enumerate(scoring_rules):
                print(f"\n评分规则 {i+1}:")
                print(f"  父项名称: {rule.Parent_Item_Name}")
                print(f"  父项分数: {rule.Parent_max_score}")
                print(f"  子项名称: {rule.Child_Item_Name}")
                print(f"  子项分数: {rule.Child_max_score}")
                print(f"  描述: {rule.description}")
                print(f"  是否价格规则: {rule.is_price_criteria}")
                if rule.is_price_criteria:
                    print(f"  价格公式: {rule.price_formula}")
        else:
            print("项目6没有评分规则")
            
        session.close()
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_project6_rules()