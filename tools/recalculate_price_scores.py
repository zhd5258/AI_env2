#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-20 22:03:06
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-20 22:03:09
# 文件相对于项目的路径   : \AI_ENV2\tools\recalculate_price_scores.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
重新计算项目价格分的工具脚本
提取数据库最后一个项目的评分规则和output目录下的全部MD文件，
重新提取价格，并发给AI重新计算价格分，更新数据库中最后一个项目的价格分
"""

import os
import sys
import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.database import (
    SessionLocal,
    TenderProject,
    ScoringRule,
    AnalysisResult,
    BidDocument,
)
from modules.unified_extractor import UnifiedExtractor
from modules.price_score_calculator import PriceScoreCalculator
from modules.price_calculation_workflow import PriceCalculationWorkflow

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_last_project(db: Session) -> Optional[TenderProject]:
    """
    获取数据库中最后一个项目

    Args:
        db: 数据库会话

    Returns:
        TenderProject: 最后一个项目，如果不存在则返回None
    """
    try:
        project = db.query(TenderProject).order_by(TenderProject.id.desc()).first()
        return project
    except Exception as e:
        logger.error(f'获取最后一个项目时出错: {e}')
        return None


def get_project_scoring_rules(db: Session, project_id: int) -> List[ScoringRule]:
    """
    获取项目的所有评分规则

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        List[ScoringRule]: 评分规则列表
    """
    try:
        scoring_rules = (
            db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
        )
        return scoring_rules
    except Exception as e:
        logger.error(f'获取项目评分规则时出错: {e}')
        return []


def get_project_analysis_results(db: Session, project_id: int) -> List[AnalysisResult]:
    """
    获取项目的所有分析结果

    Args:
        db: 数据库会话
        project_id: 项目ID

    Returns:
        List[AnalysisResult]: 分析结果列表
    """
    try:
        analysis_results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )
        return analysis_results
    except Exception as e:
        logger.error(f'获取项目分析结果时出错: {e}')
        return []


def re_extract_all_prices(project_id: int, db: Session) -> bool:
    """
    重新提取项目中所有投标人的价格

    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        bool: 是否成功重新提取所有价格
    """
    try:
        logger.info(f'开始重新提取项目 {project_id} 的所有投标人价格')

        # 创建价格计算工作流实例
        workflow = PriceCalculationWorkflow(db_session=db)

        # 重新提取所有投标人的信息
        bidders_info = workflow._extract_all_bidders_info(project_id)
        if not bidders_info:
            logger.error(f'项目 {project_id} 未提取到任何投标人信息')
            return False

        logger.info(f'成功重新提取到 {len(bidders_info)} 个投标人的信息')
        return True
    except Exception as e:
        logger.error(f'重新提取投标人价格时出错: {e}')
        return False


def recalculate_price_scores(project_id: int, db: Session) -> bool:
    """
    重新计算项目的价格分

    Args:
        project_id: 项目ID
        db: 数据库会话

    Returns:
        bool: 是否成功重新计算价格分
    """
    try:
        logger.info(f'开始重新计算项目 {project_id} 的价格分')

        # 创建价格分计算器实例
        price_calculator = PriceScoreCalculator(db_session=db)

        # 计算项目价格分
        success = price_calculator.calculate_project_price_scores(project_id)

        if success:
            logger.info(f'项目 {project_id} 的价格分重新计算成功')
        else:
            logger.error(f'项目 {project_id} 的价格分重新计算失败')

        return success
    except Exception as e:
        logger.error(f'重新计算价格分时出错: {e}')
        return False


def main():
    """主函数"""
    logger.info('开始执行重新计算价格分工具')

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 1. 获取数据库中最后一个项目
        project = get_last_project(db)
        if not project:
            logger.error('数据库中没有找到任何项目')
            return

        project_id = project.id
        logger.info(f'找到最后一个项目: {project.name} (ID: {project_id})')

        # 2. 获取项目的评分规则
        scoring_rules = get_project_scoring_rules(db, project_id)
        logger.info(f'项目 {project_id} 共有 {len(scoring_rules)} 个评分规则')

        # 查找价格评分规则
        price_rule = None
        for rule in scoring_rules:
            if getattr(rule, 'is_price_criteria', False):
                price_rule = rule
                break

        if not price_rule:
            logger.error(f'项目 {project_id} 没有找到价格评分规则')
            return

        logger.info(
            f'找到价格评分规则: 满分 {price_rule.Child_max_score}, 描述: {price_rule.description}'
        )

        # 3. 重新提取所有投标人的价格
        logger.info('步骤1: 重新提取所有投标人的价格')
        if not re_extract_all_prices(project_id, db):
            logger.error('重新提取投标人价格失败')
            return

        # 4. 重新计算价格分并更新数据库
        logger.info('步骤2: 重新计算价格分并更新数据库')
        if not recalculate_price_scores(project_id, db):
            logger.error('重新计算价格分失败')
            return

        # 5. 验证结果
        logger.info('步骤3: 验证计算结果')
        analysis_results = get_project_analysis_results(db, project_id)
        logger.info(f'项目 {project_id} 共有 {len(analysis_results)} 个分析结果')

        for result in analysis_results:
            bidder_name = result.bidder_name or f'未知投标人_{result.id}'
            price_score = getattr(result, 'price_score', 0.0)
            extracted_price = getattr(result, 'extracted_price', 0.0)
            logger.info(
                f'投标人 [{bidder_name}] 提取价格: {extracted_price}, 价格分: {price_score}'
            )

        logger.info('价格分重新计算工具执行完成!')

    except Exception as e:
        logger.error(f'执行过程中出错: {e}')
    finally:
        # 关闭数据库会话
        db.close()


if __name__ == '__main__':
    main()
