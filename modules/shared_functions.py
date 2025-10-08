#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-03 12:28:33
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-08 06:18:51
# 文件相对于项目的路径   : \AI_ENV2\modules\shared_functions.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
共享函数模块，用于避免循环导入问题
"""

import logging
import json
import asyncio
import time
import threading
import traceback  # 确保导入
from typing import List, Dict, Any
from pathlib import Path

from sqlalchemy.orm import Session

from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.correct_scoring_extractor import CorrectScoringExtractor
from modules.bidder_name_extractor import extract_bidder_name_from_file_after_analysis


def _extract_price_score_from_detailed_scores(detailed_scores):
    try:
        if isinstance(detailed_scores, str):
            try:
                detailed_scores = json.loads(detailed_scores)
            except json.JSONDecodeError:
                return 0.0

        if not isinstance(detailed_scores, list):
            return 0.0

        def find_price_score(scores):
            for score in scores:
                criteria_name = score.get('criteria_name', '').lower()
                is_price_criteria = any(
                    keyword in criteria_name
                    for keyword in ['价格', 'price', '报价', '投标报价']
                ) or score.get('is_price_criteria', False)

                if is_price_criteria and 'score' in score:
                    return float(score['score'])

                if 'children' in score and score['children']:
                    child_price_score = find_price_score(score['children'])
                    if child_price_score is not None and child_price_score > 0:
                        return child_price_score

            return None

        price_score = find_price_score(detailed_scores)
        return float(price_score) if price_score is not None else 0.0

    except Exception as e:
        logging.error(f'从详细评分中提取价格分时出错: {e}')
        return 0.0


def analyze_single_bid_document(project_id: int, bid_document_id: int):
    """
    分析单个投标文件
    这个函数用于并行处理，每个投标文件独立分析
    """
    logging.info(
        f'开始分析投标文件 project_id: {project_id}, bid_document_id: {bid_document_id}'
    )

    # 为每个分析任务创建独立的数据库会话
    db = SessionLocal()
    try:
        # 获取投标文档信息
        bid_document = (
            db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        )
        if not bid_document:
            logging.error('投标文件不存在: %s', bid_document_id)
            return

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            logging.error('项目不存在: %s', project_id)
            return

        # 使用AnalysisManager类中的analysis_task方法
        from modules.analysis_manager import AnalysisManager

        analysis_manager = AnalysisManager(db_session=db)
        analysis_manager.analysis_task(
            project_id,
            bid_document_id,
            str(project.tender_file_path),
            str(bid_document.file_path),
        )
        logging.info(
            f'完成分析投标文件 project_id: {project_id}, bid_document_id: {bid_document_id}'
        )
    except Exception as e:
        logging.error(
            f'分析投标文件时出错 project_id: {project_id}, bid_document_id: {bid_document_id}: {e}'
        )
    finally:
        db.close()
