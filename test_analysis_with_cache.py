#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试在智能分析过程中PDF文本缓存功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def test_analysis_with_cache():
    """
    测试在智能分析过程中PDF文本缓存功能
    """
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\广东创智智能装备有限公司投标文件.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
        
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("开始测试在智能分析过程中PDF文本缓存功能")
    print("=" * 80)
    
    try:
        # 1. 创建测试项目和投标文档
        session = SessionLocal()
        
        # 检查是否已存在测试项目
        existing_project = session.query(TenderProject).filter(TenderProject.project_code == "ZB2025-004").first()
        if existing_project:
            project_id = existing_project.id
            print(f"使用现有测试项目，项目ID: {project_id}")
        else:
            # 创建测试项目
            project = TenderProject(
                name="旧油漆线改造项目测试",
                project_code="ZB2025-004",  # 使用不同的项目代码
                tender_file_path=tender_file_path
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            project_id = project.id
            
            print(f"创建测试项目，项目ID: {project_id}")
        
        # 检查是否已存在测试投标文档
        existing_bid_doc = session.query(BidDocument).filter(
            BidDocument.project_id == project_id,
            BidDocument.bidder_name == "广东创智智能装备有限公司"
        ).first()
        
        if existing_bid_doc:
            bid_document_id = existing_bid_doc.id
            print(f"使用现有测试投标文档，文档ID: {bid_document_id}")
        else:
            # 创建测试投标文档
            bid_doc = BidDocument(
                project_id=project_id,
                bidder_name="广东创智智能装备有限公司",
                file_path=bid_file_path
            )
            session.add(bid_doc)
            session.commit()
            session.refresh(bid_doc)
            bid_document_id = bid_doc.id
            
            print(f"创建测试投标文档，文档ID: {bid_document_id}")
        
        # 2. 提取并保存评分规则（如果尚未保存）
        scoring_rules_count = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
        if scoring_rules_count == 0:
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
                else:
                    print("   ✗ 评分规则保存到数据库失败")
            else:
                print("   ✗ 未能提取到评分规则")
        else:
            print(f"\n2. 评分规则已存在，共 {scoring_rules_count} 条")
            
        # 3. 执行智能分析（使用缓存）
        print("\n3. 执行智能分析（使用缓存）...")
        
        analyzer = IntelligentBidAnalyzer(
            tender_file_path=tender_file_path,
            bid_file_path=bid_file_path,
            db_session=session,
            bid_document_id=bid_document_id,
            project_id=project_id
        )
        
        # 为了测试缓存效果，我们先模拟分析一部分规则
        print("   模拟分析部分规则以触发缓存...")
        
        # 获取所有子项规则（非价格规则且有Child_Item_Name的规则）
        child_rules = session.query(ScoringRule).filter(
            ScoringRule.project_id == project_id,
            ScoringRule.is_price_criteria.is_(False),
            ScoringRule.Child_Item_Name.isnot(None)
        ).all()
        
        if child_rules:
            # 只分析前3个规则来测试缓存
            test_rules = child_rules[:3]
            print(f"   分析前 {len(test_rules)} 个规则以测试缓存...")
            
            for i, rule in enumerate(test_rules):
                print(f"   分析规则 {i+1}/{len(test_rules)}: {rule.Child_Item_Name}")
                
                # 这会触发PDF文本提取并缓存
                # 我们不实际调用AI，只是触发PDF处理过程
                from modules.pdf_processor import PDFProcessor
                bid_processor = PDFProcessor(bid_file_path)
                bid_pages = bid_processor.process_pdf_per_page()
                
                if bid_pages and any(bid_pages):
                    print(f"     ✓ 成功提取并缓存PDF文本 ({len(bid_pages)} 页)")
                else:
                    print("     ✗ 未能提取PDF文本")
        
        # 4. 验证缓存是否存在
        print("\n4. 验证缓存是否存在...")
        import hashlib
        hash_md5 = hashlib.md5()
        with open(bid_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        file_hash = hash_md5.hexdigest()
        
        cache_dir = "temp_pdf_cache"
        cache_filename = f"{file_hash}.json"
        cache_path = os.path.join(cache_dir, cache_filename)
        
        if os.path.exists(cache_path):
            print("   ✓ PDF文本缓存文件存在")
            # 检查缓存文件内容
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    pages_count = cached_data.get('pages_count', 0)
                    print(f"   缓存包含 {pages_count} 页文本")
            except Exception as e:
                print(f"   读取缓存文件时出错: {e}")
        else:
            print("   ✗ PDF文本缓存文件不存在")
        
        # 5. 再次执行PDF处理以验证使用缓存
        print("\n5. 再次执行PDF处理以验证使用缓存...")
        from modules.pdf_processor import PDFProcessor
        processor = PDFProcessor(bid_file_path)
        pages = processor.process_pdf_per_page()
        
        if pages and any(pages):
            print(f"   ✓ 成功提取PDF文本 ({len(pages)} 页)")
        else:
            print("   ✗ 未能提取PDF文本")
            
        session.close()
        
        print("\n" + "=" * 80)
        print("在智能分析过程中PDF文本缓存功能测试完成!")
        
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
    test_analysis_with_cache()