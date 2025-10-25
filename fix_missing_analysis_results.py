#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复缺失的分析结果
"""

import sys
import os
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.enhanced_intelligent_bid_analyzer import EnhancedIntelligentBidAnalyzer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/fix_missing_analysis.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def fix_missing_analysis_results():
    """修复缺失的分析结果"""
    logger.info('开始修复缺失的分析结果...')
    
    db = SessionLocal()
    try:
        # 1. 查找缺少分析结果的投标文件
        missing_analysis_bids = []
        
        all_bid_documents = db.query(BidDocument).all()
        for bid_doc in all_bid_documents:
            analysis_result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == bid_doc.id)
                .first()
            )
            
            if not analysis_result:
                missing_analysis_bids.append(bid_doc)
                logger.info(f'发现缺少分析结果的投标文件: {bid_doc.id} ({bid_doc.bidder_name})')
        
        logger.info(f'总共发现 {len(missing_analysis_bids)} 个缺少分析结果的投标文件')
        
        if not missing_analysis_bids:
            logger.info('没有发现缺少分析结果的投标文件')
            return True
        
        # 2. 为每个缺少分析结果的投标文件创建分析结果记录
        created_count = 0
        for bid_doc in missing_analysis_bids:
            try:
                logger.info(f'为投标文件 {bid_doc.id} 创建分析结果记录...')
                
                # 创建基础的分析结果记录
                analysis_result = AnalysisResult(
                    project_id=bid_doc.project_id,
                    bid_document_id=bid_doc.id,
                    bidder_name=bid_doc.bidder_name,
                    total_score=0.0,
                    price_score=0.0,
                    extracted_price=0.0,
                    detailed_scores={},
                    analysis_summary='',
                    ai_model='',
                    original_scores={},
                    last_modified_at=datetime.now(),
                    last_modified_by='system_fix',
                )
                
                db.add(analysis_result)
                db.commit()
                created_count += 1
                
                logger.info(f'成功为投标文件 {bid_doc.id} 创建分析结果记录')
                
            except Exception as e:
                logger.error(f'为投标文件 {bid_doc.id} 创建分析结果记录时出错: {e}')
                db.rollback()
                continue
        
        logger.info(f'成功创建 {created_count} 个分析结果记录')
        
        # 3. 尝试重新分析这些投标文件
        logger.info('开始重新分析缺少分析结果的投标文件...')
        
        analyzed_count = 0
        for bid_doc in missing_analysis_bids:
            try:
                logger.info(f'开始分析投标文件: {bid_doc.bidder_name}')
                
                # 获取项目信息
                project = db.query(TenderProject).filter(TenderProject.id == bid_doc.project_id).first()
                if not project:
                    logger.error(f'项目 {bid_doc.project_id} 不存在，跳过分析')
                    continue
                
                # 创建分析器
                analyzer = EnhancedIntelligentBidAnalyzer(
                    tender_file_path=str(project.tender_file_path),
                    bid_file_path=str(bid_doc.file_path),
                    db_session=db,
                    bid_document_id=bid_doc.id,
                    project_id=bid_doc.project_id,
                )
                
                # 执行分析
                result = analyzer.analyze()
                
                if result:
                    logger.info(f'投标文件 {bid_doc.bidder_name} 分析成功')
                    analyzed_count += 1
                else:
                    logger.warning(f'投标文件 {bid_doc.bidder_name} 分析失败')
                
            except Exception as e:
                logger.error(f'分析投标文件 {bid_doc.bidder_name} 时出错: {e}')
                import traceback
                logger.error(traceback.format_exc())
                continue
        
        logger.info(f'成功分析 {analyzed_count} 个投标文件')
        
        return True
        
    except Exception as e:
        logger.error(f'修复缺失分析结果时出错: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        db.close()


def verify_analysis_results():
    """验证分析结果修复情况"""
    logger.info('验证分析结果修复情况...')
    
    db = SessionLocal()
    try:
        # 统计所有投标文件和分析结果
        total_bid_documents = db.query(BidDocument).count()
        total_analysis_results = db.query(AnalysisResult).count()
        
        logger.info(f'总投标文件数: {total_bid_documents}')
        logger.info(f'总分析结果数: {total_analysis_results}')
        
        # 检查是否还有缺少分析结果的投标文件
        missing_count = 0
        all_bid_documents = db.query(BidDocument).all()
        for bid_doc in all_bid_documents:
            analysis_result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == bid_doc.id)
                .first()
            )
            
            if not analysis_result:
                missing_count += 1
                logger.warning(f'投标文件 {bid_doc.id} ({bid_doc.bidder_name}) 仍然缺少分析结果')
        
        if missing_count == 0:
            logger.info('所有投标文件都有对应的分析结果记录')
            return True
        else:
            logger.warning(f'仍有 {missing_count} 个投标文件缺少分析结果')
            return False
        
    except Exception as e:
        logger.error(f'验证分析结果时出错: {e}')
        return False
    finally:
        db.close()


if __name__ == '__main__':
    logger.info('开始修复缺失的分析结果...')
    
    # 修复缺失的分析结果
    if fix_missing_analysis_results():
        logger.info('修复缺失分析结果完成')
        
        # 验证修复结果
        if verify_analysis_results():
            logger.info('所有分析结果修复验证通过')
        else:
            logger.warning('部分分析结果修复验证失败')
    else:
        logger.error('修复缺失分析结果失败')
    
    logger.info('修复缺失分析结果任务完成')
