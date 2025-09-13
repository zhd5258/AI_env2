#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查所有项目的分析结果情况
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, AnalysisResult, ScoringRule

def check_all_projects_analysis():
    """
    检查所有项目的分析结果情况
    """
    print("检查所有项目的分析结果情况")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查所有项目
        projects = session.query(TenderProject).all()
        print(f"项目总数: {len(projects)}")
        
        for project in projects:
            print(f"\n项目信息:")
            print(f"  ID: {project.id}")
            print(f"  名称: {project.name}")
            print(f"  项目代码: {project.project_code}")
            print(f"  状态: {project.status}")
            print(f"  描述: {project.description}")
            
            # 检查评分规则
            scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project.id).all()
            print(f"  评分规则数量: {len(scoring_rules)}")
            
            # 检查投标文件
            bid_documents = session.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            print(f"  投标文件数量: {len(bid_documents)}")
            
            if bid_documents:
                for i, bid_doc in enumerate(bid_documents):
                    print(f"    投标文件 {i+1}:")
                    print(f"      ID: {bid_doc.id}")
                    print(f"      投标方名称: {bid_doc.bidder_name}")
                    print(f"      处理状态: {bid_doc.processing_status}")
                    print(f"      错误信息: {bid_doc.error_message}")
                    
                    # 检查分析结果
                    if bid_doc.analysis_result:
                        print(f"      分析结果存在: 是")
                        print(f"        总分: {bid_doc.analysis_result.total_score}")
                        print(f"        价格分: {bid_doc.analysis_result.price_score}")
                        print(f"        提取价格: {bid_doc.analysis_result.extracted_price}")
                        if bid_doc.analysis_result.detailed_scores:
                            try:
                                detailed_scores = json.loads(bid_doc.analysis_result.detailed_scores)
                                print(f"        详细评分数量: {len(detailed_scores)}")
                            except Exception as e:
                                print(f"        详细评分解析失败: {e}")
                        else:
                            print(f"        详细评分: 无")
                    else:
                        print(f"      分析结果存在: 否")
            
        session.close()
        
    except Exception as e:
        print(f"检查过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_all_projects_analysis()