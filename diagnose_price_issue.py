#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
诊断项目6的价格提取和计算问题
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager

def diagnose_price_issue():
    """
    诊断项目6的价格提取和计算问题
    """
    print("诊断项目6的价格提取和计算问题")
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
        
        # 检查投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        print(f"\n投标文档数量: {len(bid_docs)}")
        for doc in bid_docs:
            print(f"  文档ID: {doc.id}")
            print(f"    投标方: {doc.bidder_name}")
            print(f"    文件路径: {doc.file_path}")
            print(f"    处理状态: {doc.processing_status}")
            
            # 检查分析结果
            analysis_result = doc.analysis_result
            if analysis_result:
                print(f"    分析结果ID: {analysis_result.id}")
                print(f"      总分: {analysis_result.total_score}")
                print(f"      价格分: {analysis_result.price_score}")
                print(f"      提取价格: {analysis_result.extracted_price}")
                if analysis_result.detailed_scores:
                    try:
                        scores = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                        price_scores = [s for s in scores if s.get('is_price_criteria', False)]
                        print(f"      价格评分项数: {len(price_scores)}")
                        for ps in price_scores:
                            print(f"        价格评分项: {ps}")
                    except Exception as e:
                        print(f"      解析详细得分时出错: {e}")
            else:
                print(f"    无分析结果")
        
        # 检查评分规则
        scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 6).all()
        print(f"\n评分规则数量: {len(scoring_rules)}")
        price_rules = [r for r in scoring_rules if r.is_price_criteria]
        print(f"  价格规则数量: {len(price_rules)}")
        for rule in price_rules:
            print(f"    规则ID: {rule.id}")
            print(f"      父项名称: {rule.Parent_Item_Name}")
            print(f"      父项分数: {rule.Parent_max_score}")
            print(f"      描述: {rule.description}")
        
        # 尝试重新提取价格
        print(f"\n尝试重新提取价格:")
        price_manager = PriceManager()
        for doc in bid_docs:
            if not os.path.exists(doc.file_path):
                print(f"  错误：投标文件不存在 {doc.file_path}")
                continue
                
            print(f"  处理投标方: {doc.bidder_name}")
            processor = PDFProcessor(doc.file_path)
            pages = processor.process_pdf_per_page()
            print(f"    提取到 {len(pages)} 页文本")
            
            if pages and any(pages):
                prices = price_manager.extract_prices_from_content(pages)
                print(f"    提取到 {len(prices)} 个价格")
                for i, price_info in enumerate(prices[:5]):  # 显示前5个
                    print(f"      价格 {i+1}: {price_info['value']} (置信度: {price_info['confidence']})")
                
                best_price = price_manager.select_best_price(prices, pages)
                print(f"    最佳价格: {best_price}")
            else:
                print(f"    未能提取到文本内容")
        
        session.close()
        
    except Exception as e:
        print(f"诊断过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    diagnose_price_issue()