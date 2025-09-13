#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
验证价格分计算结果
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult

def verify_price_scores():
    """
    验证价格分计算结果
    """
    print("验证价格分计算结果")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目6
        project = session.query(TenderProject).filter(TenderProject.id == 6).first()
        if not project:
            print("错误：项目6不存在")
            return
            
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  状态: {project.status}")
        
        # 检查投标文档和分析结果
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        print(f"\n投标文档数量: {len(bid_docs)}")
        
        for doc in bid_docs:
            print(f"\n投标文档 {doc.id}: {doc.bidder_name}")
            print(f"  处理状态: {doc.processing_status}")
            print(f"  错误信息: {doc.error_message}")
            
            analysis_result = doc.analysis_result
            if analysis_result:
                print(f"  分析结果ID: {analysis_result.id}")
                print(f"  总分: {analysis_result.total_score}")
                print(f"  价格分: {analysis_result.price_score}")
                print(f"  提取价格: {analysis_result.extracted_price}")
                
                # 检查详细评分
                if analysis_result.detailed_scores:
                    try:
                        scores = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                        price_scores = [s for s in scores if s.get('is_price_criteria', False)]
                        print(f"  价格评分项数量: {len(price_scores)}")
                        for ps in price_scores:
                            print(f"    价格评分项: {ps}")
                    except Exception as e:
                        print(f"  解析详细得分时出错: {e}")
            else:
                print(f"  无分析结果")
        
        session.close()
        print(f"\n验证完成!")
        
    except Exception as e:
        print(f"验证过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_price_scores()