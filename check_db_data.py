#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查数据库中的实际数据
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult

def check_db_data():
    """
    检查数据库中的实际数据
    """
    print("检查数据库中的实际数据")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目
        projects = session.query(TenderProject).all()
        print(f"项目数量: {len(projects)}")
        for project in projects:
            print(f"  项目ID: {project.id}, 项目代码: {project.project_code}, 名称: {project.name}")
        
        # 检查投标文档
        bid_docs = session.query(BidDocument).all()
        print(f"\n投标文档数量: {len(bid_docs)}")
        for doc in bid_docs:
            print(f"  文档ID: {doc.id}, 项目ID: {doc.project_id}, 投标方: {doc.bidder_name}")
        
        # 检查评分规则
        scoring_rules = session.query(ScoringRule).all()
        print(f"\n评分规则数量: {len(scoring_rules)}")
        for rule in scoring_rules:
            print(f"  规则ID: {rule.id}, 项目ID: {rule.project_id}")
            print(f"    父项: {rule.Parent_Item_Name}({rule.Parent_max_score}分)")
            print(f"    子项: {rule.Child_Item_Name}({rule.Child_max_score}分)")
            print(f"    是否价格规则: {rule.is_price_criteria}")
        
        # 检查分析结果
        analysis_results = session.query(AnalysisResult).all()
        print(f"\n分析结果数量: {len(analysis_results)}")
        for result in analysis_results:
            print(f"  结果ID: {result.id}, 项目ID: {result.project_id}, 文档ID: {result.bid_document_id}")
            print(f"    投标方: {result.bidder_name}")
            print(f"    总分: {result.total_score}")
            print(f"    价格分: {result.price_score}")
            print(f"    提取价格: {result.extracted_price}")
            if result.detailed_scores:
                try:
                    if isinstance(result.detailed_scores, str):
                        scores = json.loads(result.detailed_scores)
                    else:
                        scores = result.detailed_scores
                    print(f"    详细得分项数: {len(scores)}")
                    for i, score_item in enumerate(scores[:3]):  # 只显示前3项
                        print(f"      {i+1}. {score_item.get('criteria_name', 'N/A')}: {score_item.get('score', 'N/A')}")
                    if len(scores) > 3:
                        print(f"      ... 还有 {len(scores) - 3} 项")
                except Exception as e:
                    print(f"    解析详细得分时出错: {e}")
            else:
                print("    无详细得分")
        
        session.close()
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_db_data()