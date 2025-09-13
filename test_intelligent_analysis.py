#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试修改后的智能分析功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def test_intelligent_analysis():
    """
    测试修改后的智能分析功能
    """
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\广东创智智能装备有限公司投标文件.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
        
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("开始测试智能分析功能")
    print("=" * 80)
    
    try:
        # 1. 创建测试项目和投标文档
        session = SessionLocal()
        
        # 创建测试项目
        project = TenderProject(
            project_name="旧油漆线改造项目测试",
            project_number="ZB2025-001",
            tender_documents_path=tender_file_path
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id
        
        print(f"创建测试项目，项目ID: {project_id}")
        
        # 创建测试投标文档
        bid_doc = BidDocument(
            project_id=project_id,
            bidder_name="广东创智智能装备有限公司",
            bid_documents_path=bid_file_path
        )
        session.add(bid_doc)
        session.commit()
        session.refresh(bid_doc)
        bid_document_id = bid_doc.id
        
        print(f"创建测试投标文档，文档ID: {bid_document_id}")
        
        # 2. 提取并保存评分规则
        print("\n2. 提取评分规则...")
        extractor = IntelligentScoringExtractor()
        rules = extractor.extract(tender_file_path)
        
        if rules:
            print(f"   成功提取到 {len(rules)} 条评分规则")
            
            # 保存到数据库
            handler = TestDBHandler()
            success = handler.save_scoring_rules_to_db(project_id, rules)
            
            if success:
                print("   ✓ 评分规则成功保存到数据库")
                
                # 验证保存的规则
                db_rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
                print(f"   数据库中保存了 {len(db_rules)} 条评分规则")
                
                # 统计子项规则
                child_rules = [r for r in db_rules if r.Child_Item_Name is not None]
                price_rules = [r for r in db_rules if r.is_price_criteria]
                print(f"   子项规则数: {len(child_rules)}")
                print(f"   价格规则数: {len(price_rules)}")
            else:
                print("   ✗ 评分规则保存到数据库失败")
        else:
            print("   ✗ 未能提取到评分规则")
            
        # 3. 执行智能分析
        print("\n3. 执行智能分析...")
        analyzer = IntelligentBidAnalyzer(
            tender_file_path=tender_file_path,
            bid_file_path=bid_file_path,
            db_session=session,
            bid_document_id=bid_document_id,
            project_id=project_id
        )
        
        analysis_result = analyzer.analyze()
        
        if 'error' in analysis_result:
            print(f"   ✗ 分析失败: {analysis_result['error']}")
        else:
            print("   ✓ 智能分析完成")
            print(f"   总分: {analysis_result['total_score']}")
            print(f"   提取到的价格: {analysis_result['extracted_price']}")
            
            # 显示详细评分
            print("\n   详细评分:")
            for score_item in analysis_result['detailed_scores']:
                print(f"     - {score_item['criteria_name']}: {score_item['score']}/{score_item['max_score']}")
                print(f"       理由: {score_item['reason']}")
                
            # 保存分析结果到数据库
            print("\n4. 保存分析结果到数据库...")
            analysis_result_record = {
                'project_id': project_id,
                'bid_document_id': bid_document_id,
                'total_score': analysis_result['total_score'],
                'detailed_scores': analysis_result['detailed_scores'],
                'analysis_summary': analysis_result['analysis_summary'],
                'ai_model': analysis_result['ai_model'],
                'extracted_price': analysis_result['extracted_price']
            }
            
            # 更新投标文档
            bid_doc.total_score = analysis_result['total_score']
            bid_doc.detailed_scores = analysis_result['detailed_scores']
            session.commit()
            
            print("   ✓ 分析结果已保存到数据库")
            
        session.close()
        
        print("\n" + "=" * 80)
        print("测试完成!")
        
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
    test_intelligent_analysis()