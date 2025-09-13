#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
真实投标文件智能分析测试脚本
使用扬州琼花涂装工程技术有限公司的投标文件进行完整测试
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_real_bid_analysis():
    """
    测试真实投标文件的智能分析功能
    """
    # 招标文件路径（使用已有的项目）
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    # 真实投标文件路径
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\扬州琼花涂装工程技术有限公司集装箱投标文件.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
        
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("开始测试真实投标文件的智能分析功能")
    print("=" * 80)
    
    try:
        # 1. 连接数据库并查找项目
        session = SessionLocal()
        
        # 查找已存在的测试项目（使用新创建的项目代码）
        project = session.query(TenderProject).filter(TenderProject.project_code == "ZB2025-006").first()
        if not project:
            print("错误：未找到测试项目，请先运行评分规则提取测试")
            session.close()
            return
            
        project_id = project.id
        print(f"使用测试项目，项目ID: {project_id}")
        
        # 检查是否已存在该投标人的投标文档
        existing_bid_doc = session.query(BidDocument).filter(
            BidDocument.project_id == project_id,
            BidDocument.bidder_name == "扬州琼花涂装工程技术有限公司"
        ).first()
        
        if existing_bid_doc:
            bid_document_id = existing_bid_doc.id
            print(f"使用现有投标文档，文档ID: {bid_document_id}")
        else:
            # 创建新的投标文档
            bid_doc = BidDocument(
                project_id=project_id,
                bidder_name="扬州琼花涂装工程技术有限公司",
                file_path=bid_file_path
            )
            session.add(bid_doc)
            session.commit()
            session.refresh(bid_doc)
            bid_document_id = bid_doc.id
            print(f"创建新的投标文档，文档ID: {bid_document_id}")
        
        # 2. 检查评分规则是否存在
        scoring_rules_count = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
        if scoring_rules_count == 0:
            print("错误：未找到评分规则，请先运行评分规则提取测试")
            session.close()
            return
            
        print(f"评分规则已存在，共 {scoring_rules_count} 条")
        
        # 3. 执行智能分析
        print("\n3. 执行智能分析...")
        
        analyzer = IntelligentBidAnalyzer(
            tender_file_path=tender_file_path,
            bid_file_path=bid_file_path,
            db_session=session,
            bid_document_id=bid_document_id,
            project_id=project_id
        )
        
        print("   开始分析...")
        analysis_result = analyzer.analyze()
        
        if 'error' in analysis_result:
            print(f"   ✗ 分析失败: {analysis_result['error']}")
        else:
            print("   ✓ 智能分析完成")
            print(f"   总分: {analysis_result['total_score']}")
            print(f"   提取到的价格: {analysis_result['extracted_price']}")
            
            # 显示详细评分
            print("\n   详细评分:")
            for i, score_item in enumerate(analysis_result['detailed_scores']):
                print(f"     {i+1}. {score_item['criteria_name']}: {score_item['score']}/{score_item['max_score']}")
                # 只显示前几个规则的详细理由，避免输出过长
                if i < 5:
                    print(f"        理由: {score_item['reason'][:100]}{'...' if len(score_item['reason']) > 100 else ''}")
                    
            if len(analysis_result['detailed_scores']) > 5:
                print(f"        ... 还有 {len(analysis_result['detailed_scores']) - 5} 个评分项")
                
            # 保存分析结果到数据库
            print("\n4. 保存分析结果到数据库...")
            bid_doc = session.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
            bid_doc.total_score = analysis_result['total_score']
            bid_doc.detailed_scores = analysis_result['detailed_scores']
            bid_doc.extracted_price = analysis_result['extracted_price']
            session.commit()
            
            print("   ✓ 分析结果已保存到数据库")
            
        session.close()
        
        print("\n" + "=" * 80)
        print("真实投标文件智能分析测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 关闭数据库会话
        try:
            session.close()
        except:
            pass

if __name__ == "__main__":
    test_real_bid_analysis()