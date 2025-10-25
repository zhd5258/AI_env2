#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析数据库中的分析结果，找出项目未分析的原因
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
from sqlalchemy import text

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/database_analysis.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def analyze_database_results():
    """分析数据库中的分析结果"""
    logger.info('开始分析数据库中的分析结果...')

    db = SessionLocal()
    try:
        # 1. 检查所有项目
        projects = db.query(TenderProject).all()
        logger.info(f'数据库中共有 {len(projects)} 个项目')

        for project in projects:
            logger.info(f'\n=== 项目 {project.id}: {project.name} ===')
            logger.info(f'项目状态: {project.status}')
            logger.info(f'创建时间: {project.created_at}')
            # 检查是否有updated_at字段
            if hasattr(project, 'updated_at'):
                logger.info(f'更新时间: {project.updated_at}')
            else:
                logger.info('更新时间: 无此字段')

            # 检查项目的投标文件
            bid_documents = (
                db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            )
            logger.info(f'投标文件数量: {len(bid_documents)}')

            for bid_doc in bid_documents:
                logger.info(f'  - 投标人: {bid_doc.bidder_name}')
                logger.info(f'    文件路径: {bid_doc.file_path}')
                logger.info(f'    处理状态: {bid_doc.processing_status}')
                logger.info(f'    处理阶段: {bid_doc.processing_phase}')
                logger.info(
                    f'    进度: {bid_doc.progress_completed_rules}/{bid_doc.progress_total_rules}'
                )

                # 检查分析结果
                analysis_result = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_doc.id)
                    .first()
                )

                if analysis_result:
                    logger.info(f'    分析结果ID: {analysis_result.id}')
                    logger.info(f'    总分: {analysis_result.total_score}')
                    logger.info(f'    价格分: {analysis_result.price_score}')
                    logger.info(f'    提取价格: {analysis_result.extracted_price}')
                    logger.info(f'    分析摘要: {analysis_result.analysis_summary}')
                    logger.info(f'    否决项检查: {analysis_result.veto_items_checked}')
                    logger.info(f'    否决项通过: {analysis_result.veto_items_passed}')
                else:
                    logger.warning('    ⚠️ 没有分析结果记录')

            # 检查项目的评分规则
            scoring_rules = (
                db.query(ScoringRule).filter(ScoringRule.project_id == project.id).all()
            )
            logger.info(f'评分规则数量: {len(scoring_rules)}')

            if scoring_rules:
                qualitative_count = len([r for r in scoring_rules if r.is_qualitative])
                quantitative_count = len(
                    [r for r in scoring_rules if r.is_quantitative]
                )
                price_count = len([r for r in scoring_rules if r.is_price_criteria])
                logger.info(f'  - 定性规则: {qualitative_count}')
                logger.info(f'  - 定量规则: {quantitative_count}')
                logger.info(f'  - 价格规则: {price_count}')

        # 2. 统计未分析的项目
        logger.info('\n=== 未分析项目统计 ===')
        unanalyzed_projects = []

        for project in projects:
            if project.status in ['pending', 'analyzing']:
                unanalyzed_projects.append(project)
                logger.info(
                    f'项目 {project.id} ({project.name}) 状态: {project.status}'
                )

        logger.info(f'未分析项目数量: {len(unanalyzed_projects)}')

        # 3. 检查分析结果缺失的情况
        logger.info('\n=== 分析结果缺失检查 ===')
        missing_analysis_count = 0

        for project in projects:
            bid_documents = (
                db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            )
            for bid_doc in bid_documents:
                analysis_result = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_doc.id)
                    .first()
                )

                if not analysis_result:
                    missing_analysis_count += 1
                    logger.warning(
                        f'项目 {project.id} 的投标文件 {bid_doc.id} ({bid_doc.bidder_name}) 缺少分析结果'
                    )

        logger.info(f'缺少分析结果的投标文件数量: {missing_analysis_count}')

        # 4. 检查状态不一致的情况
        logger.info('\n=== 状态不一致检查 ===')
        inconsistent_count = 0

        for project in projects:
            bid_documents = (
                db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            )
            for bid_doc in bid_documents:
                analysis_result = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_doc.id)
                    .first()
                )

                # 检查状态不一致
                if bid_doc.processing_status == 'completed' and not analysis_result:
                    inconsistent_count += 1
                    logger.warning(
                        f'投标文件 {bid_doc.id} 状态为completed但缺少分析结果'
                    )
                elif (
                    bid_doc.processing_status == 'processing'
                    and analysis_result
                    and analysis_result.total_score > 0
                ):
                    inconsistent_count += 1
                    logger.warning(
                        f'投标文件 {bid_doc.id} 状态为processing但已有分析结果'
                    )

        logger.info(f'状态不一致的投标文件数量: {inconsistent_count}')

        return {
            'total_projects': len(projects),
            'unanalyzed_projects': len(unanalyzed_projects),
            'missing_analysis_count': missing_analysis_count,
            'inconsistent_count': inconsistent_count,
        }

    except Exception as e:
        logger.error(f'分析数据库结果时出错: {e}')
        import traceback

        logger.error(traceback.format_exc())
        return None
    finally:
        db.close()


def fix_analysis_issues():
    """修复分析问题"""
    logger.info('开始修复分析问题...')

    db = SessionLocal()
    try:
        # 1. 修复状态不一致的问题
        logger.info('修复状态不一致问题...')

        # 查找状态为completed但缺少分析结果的投标文件
        inconsistent_docs = (
            db.query(BidDocument)
            .join(TenderProject)
            .filter(BidDocument.processing_status == 'completed')
            .all()
        )

        fixed_count = 0
        for bid_doc in inconsistent_docs:
            analysis_result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == bid_doc.id)
                .first()
            )

            if not analysis_result:
                # 将状态重置为pending，等待重新分析
                bid_doc.processing_status = 'pending'
                bid_doc.processing_phase = '待分析'
                fixed_count += 1
                logger.info(f'重置投标文件 {bid_doc.id} 状态为pending')

        if fixed_count > 0:
            db.commit()
            logger.info(f'已修复 {fixed_count} 个状态不一致的投标文件')

        # 2. 清理无效的分析结果
        logger.info('清理无效的分析结果...')

        # 查找没有对应投标文件的分析结果
        orphaned_results = (
            db.query(AnalysisResult)
            .filter(~AnalysisResult.bid_document_id.in_(db.query(BidDocument.id)))
            .all()
        )

        if orphaned_results:
            for result in orphaned_results:
                db.delete(result)
            db.commit()
            logger.info(f'已清理 {len(orphaned_results)} 个无效的分析结果')

        return True

    except Exception as e:
        logger.error(f'修复分析问题时出错: {e}')
        import traceback

        logger.error(traceback.format_exc())
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == '__main__':
    logger.info('开始数据库分析结果检查...')

    # 分析数据库结果
    analysis_result = analyze_database_results()

    if analysis_result:
        logger.info('\n=== 分析总结 ===')
        logger.info(f'总项目数: {analysis_result["total_projects"]}')
        logger.info(f'未分析项目数: {analysis_result["unanalyzed_projects"]}')
        logger.info(f'缺少分析结果数: {analysis_result["missing_analysis_count"]}')
        logger.info(f'状态不一致数: {analysis_result["inconsistent_count"]}')

        # 如果有问题，尝试修复
        if (
            analysis_result['unanalyzed_projects'] > 0
            or analysis_result['missing_analysis_count'] > 0
            or analysis_result['inconsistent_count'] > 0
        ):
            logger.info('\n发现分析问题，开始修复...')
            if fix_analysis_issues():
                logger.info('修复完成')
            else:
                logger.error('修复失败')
        else:
            logger.info('未发现分析问题')
    else:
        logger.error('数据库分析失败')

    logger.info('数据库分析结果检查完成')
