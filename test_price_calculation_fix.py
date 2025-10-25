#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试价格分计算修复
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
from modules.price_score_calculator import PriceScoreCalculator
from modules.unified_comprehensive_calculator import UnifiedComprehensiveCalculator

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/price_calculation_test.log', encoding='utf-8'),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def test_price_calculation_for_project(project_id: int):
    """测试特定项目的价格分计算"""
    logger.info(f'开始测试项目 {project_id} 的价格分计算...')

    db = SessionLocal()
    try:
        # 1. 检查项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            logger.error(f'项目 {project_id} 不存在')
            return False

        logger.info(f'项目名称: {project.name}')
        logger.info(f'项目状态: {project.status}')

        # 2. 检查投标文件和分析结果
        bid_documents = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )
        logger.info(f'投标文件数量: {len(bid_documents)}')

        analysis_results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )
        logger.info(f'分析结果数量: {len(analysis_results)}')

        # 3. 检查价格提取情况
        logger.info('=== 价格提取情况 ===')
        for result in analysis_results:
            logger.info(f'投标人: {result.bidder_name}')
            logger.info(f'  提取价格: {result.extracted_price}')
            logger.info(f'  当前价格分: {result.price_score}')
            logger.info(f'  总分: {result.total_score}')

        # 4. 检查价格评分规则
        price_rules = (
            db.query(ScoringRule)
            .filter(
                ScoringRule.project_id == project_id,
                ScoringRule.is_price_criteria == True,
            )
            .all()
        )

        logger.info(f'价格评分规则数量: {len(price_rules)}')
        for rule in price_rules:
            logger.info(f'  规则名称: {rule.Child_Item_Name}')
            logger.info(f'  满分: {rule.Child_max_score}')
            logger.info(f'  描述: {rule.description}')

        # 5. 尝试重新计算价格分
        if price_rules and analysis_results:
            logger.info('=== 开始重新计算价格分 ===')

            # 使用统一综合计算器
            calculator = UnifiedComprehensiveCalculator(db_session=db)
            success = calculator._calculate_price_scores(project_id, analysis_results)

            if success:
                logger.info('价格分计算成功')

                # 检查更新后的结果
                db.commit()  # 确保数据已提交
                updated_results = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .all()
                )

                logger.info('=== 更新后的结果 ===')
                for result in updated_results:
                    logger.info(f'投标人: {result.bidder_name}')
                    logger.info(f'  提取价格: {result.extracted_price}')
                    logger.info(f'  价格分: {result.price_score}')
                    logger.info(f'  总分: {result.total_score}')
            else:
                logger.error('价格分计算失败')
                return False
        else:
            logger.warning('缺少价格评分规则或分析结果，无法计算价格分')
            return False

        return True

    except Exception as e:
        logger.error(f'测试价格分计算时出错: {e}')
        import traceback

        logger.error(traceback.format_exc())
        return False
    finally:
        db.close()


def test_all_projects_price_calculation():
    """测试所有项目的价格分计算"""
    logger.info('开始测试所有项目的价格分计算...')

    db = SessionLocal()
    try:
        # 获取所有有分析结果的项目
        projects = (
            db.query(TenderProject)
            .filter(
                TenderProject.id.in_(db.query(AnalysisResult.project_id).distinct())
            )
            .all()
        )

        logger.info(f'找到 {len(projects)} 个有分析结果的项目')

        success_count = 0
        for project in projects:
            logger.info(f'\n=== 测试项目 {project.id}: {project.name} ===')
            if test_price_calculation_for_project(project.id):
                success_count += 1
                logger.info(f'项目 {project.id} 价格分计算成功')
            else:
                logger.error(f'项目 {project.id} 价格分计算失败')

        logger.info('\n=== 测试总结 ===')
        logger.info(f'总项目数: {len(projects)}')
        logger.info(f'成功项目数: {success_count}')
        logger.info(f'失败项目数: {len(projects) - success_count}')

        return success_count == len(projects)

    except Exception as e:
        logger.error(f'测试所有项目价格分计算时出错: {e}')
        import traceback

        logger.error(traceback.format_exc())
        return False
    finally:
        db.close()


if __name__ == '__main__':
    logger.info('开始价格分计算测试...')

    # 测试所有项目
    success = test_all_projects_price_calculation()

    if success:
        logger.info('所有项目价格分计算测试通过')
    else:
        logger.error('部分项目价格分计算测试失败')

    logger.info('价格分计算测试完成')
