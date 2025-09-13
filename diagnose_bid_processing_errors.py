#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
深入诊断投标文档处理失败的原因
"""

import sys
import os
import json
import traceback

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
from modules.pdf_processor import PDFProcessor
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer

def diagnose_bid_processing_errors():
    """
    深入诊断投标文档处理失败的原因
    """
    print("深入诊断投标文档处理失败的原因")
    print("=" * 60)
    
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
        
        for doc in bid_docs:
            print(f"\n检查投标文档 {doc.id}:")
            print(f"  投标方: {doc.bidder_name}")
            print(f"  文件路径: {doc.file_path}")
            print(f"  处理状态: {doc.processing_status}")
            print(f"  错误信息: {doc.error_message}")
            
            # 检查文件是否存在
            if not os.path.exists(doc.file_path):
                print(f"  错误：文件不存在 {doc.file_path}")
                continue
                
            # 检查文件大小
            try:
                file_size = os.path.getsize(doc.file_path)
                print(f"  文件大小: {file_size} 字节")
            except Exception as e:
                print(f"  检查文件大小时出错: {e}")
                
            # 尝试手动处理文档
            print(f"  尝试手动处理文档...")
            try:
                analyzer = IntelligentBidAnalyzer(
                    tender_file_path=project.tender_file_path,
                    bid_file_path=doc.file_path,
                    db_session=session,
                    bid_document_id=doc.id,
                    project_id=project.id
                )
                
                print(f"    初始化分析器成功")
                
                # 尝试分析
                result = analyzer.analyze()
                print(f"    分析结果: {result}")
                
                if 'error' in result:
                    print(f"    分析失败: {result['error']}")
                else:
                    print(f"    分析成功，总分: {result['total_score']}")
                    
            except Exception as e:
                print(f"    处理文档时出错: {e}")
                print(f"    错误详情:")
                traceback.print_exc()
        
        session.close()
        
    except Exception as e:
        print(f"诊断过程中出错: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_bid_processing_errors()