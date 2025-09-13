#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复数据库并重新处理投标文档
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer

def fix_and_reprocess_bids():
    """
    修复数据库并重新处理投标文档
    """
    print("修复数据库并重新处理投标文档")
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
        
        # 检查评分规则
        scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 6).all()
        print(f"\n评分规则数量: {len(scoring_rules)}")
        if not scoring_rules:
            print("错误：未找到评分规则")
            return
            
        # 检查投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        print(f"\n投标文档数量: {len(bid_docs)}")
        
        # 为每个投标文档创建分析结果（如果不存在）
        for doc in bid_docs:
            print(f"\n处理投标文档 {doc.id}: {doc.bidder_name}")
            
            # 检查是否已存在分析结果
            if not doc.analysis_result:
                print(f"  创建新的分析结果...")
                analysis_result = AnalysisResult(
                    project_id=project.id,
                    bid_document_id=doc.id,
                    bidder_name=doc.bidder_name
                )
                session.add(analysis_result)
                session.commit()
                print(f"  分析结果创建成功")
            else:
                print(f"  分析结果已存在")
        
        # 重新处理每个投标文档
        print(f"\n重新处理投标文档...")
        for doc in bid_docs:
            print(f"\n处理投标方: {doc.bidder_name}")
            
            # 检查文件是否存在
            if not os.path.exists(doc.file_path):
                print(f"  错误：文件不存在 {doc.file_path}")
                continue
                
            try:
                # 创建分析器
                analyzer = IntelligentBidAnalyzer(
                    tender_file_path=project.tender_file_path,
                    bid_file_path=doc.file_path,
                    db_session=session,
                    bid_document_id=doc.id,
                    project_id=project.id
                )
                
                print(f"  开始分析...")
                result = analyzer.analyze()
                
                if 'error' in result:
                    print(f"  分析失败: {result['error']}")
                    # 更新文档状态
                    doc.processing_status = 'error'
                    doc.error_message = result['error']
                else:
                    print(f"  分析成功，总分: {result['total_score']}")
                    # 保存分析结果
                    if doc.analysis_result:
                        doc.analysis_result.total_score = result['total_score']
                        doc.analysis_result.detailed_scores = json.dumps(result['detailed_scores'], ensure_ascii=False)
                        doc.analysis_result.price_score = next((item['score'] for item in result['detailed_scores'] if item.get('is_price_criteria', False)), 0)
                        doc.analysis_result.extracted_price = result['extracted_price']
                        doc.analysis_result.ai_model = result['ai_model']
                        doc.analysis_result.analysis_summary = result['analysis_summary']
                    
                    # 更新文档状态
                    doc.processing_status = 'completed'
                    doc.error_message = None
                    
                session.commit()
                print(f"  处理完成")
                
            except Exception as e:
                print(f"  处理文档时出错: {e}")
                doc.processing_status = 'error'
                doc.error_message = str(e)
                session.commit()
        
        # 更新项目状态
        project.status = 'completed'
        session.commit()
        print(f"\n项目状态已更新为 completed")
        
        session.close()
        print(f"\n所有投标文档处理完成!")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_and_reprocess_bids()