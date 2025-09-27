#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:46:24
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-26 18:48:27
# 文件相对于项目的路径   : \AI_env2\modules\analysis_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
"""
分析管理器模块
统一处理项目分析流程，包括评分规则提取、投标文件分析和价格分计算
"""

import logging
import asyncio
import traceback
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
import os

from modules.database import TenderProject, BidDocument, AnalysisResult
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_rules_manager import ScoringRulesManager
from modules.price_score_calculator import PriceScoreCalculator
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer


class AnalysisManager:
    """分析管理器，统一处理项目分析流程"""

    def __init__(self, db_session: Session = None):
        self.db = db_session
        self.logger = logging.getLogger(__name__)

    def initialize_project_analysis(self, project_id: int) -> bool:
        """
        初始化项目分析，处理招标文件并提取评分规则

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否初始化成功
        """
        if not self.db:
            self.logger.error('数据库会话未提供')
            return False

        try:
            self.logger.info('开始初始化项目分析，项目ID: %d', project_id)

            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if not project:
                self.logger.error('项目不存在: %d', project_id)
                return False

            tender_file_path = project.tender_file_path
            if not tender_file_path or not os.path.exists(tender_file_path):
                self.logger.error('招标文件不存在: %s', tender_file_path)
                return False

            self.logger.info('项目 %d 没有评分规则，开始从招标文件提取...', project_id)

            # 从招标文件中提取评分规则
            extractor = IntelligentScoringExtractor()
            scoring_rules = extractor.extract(tender_file_path)

            if scoring_rules:
                # 使用统一的评分规则管理器保存评分规则
                rules_manager = ScoringRulesManager(db_session=self.db)
                save_result = rules_manager.save_scoring_rules(
                    project_id, scoring_rules
                )

                if save_result:
                    self.logger.info(
                        '成功提取并保存 %s 条评分规则到数据库', len(scoring_rules)
                    )

                    # 记录提取到的评分规则详细信息
                    for rule_data in scoring_rules:
                        self.logger.info(
                            '评分规则: criteria_name=%s, max_score=%s, is_price_criteria=%s',
                            rule_data.get('criteria_name'),
                            rule_data.get('max_score'),
                            rule_data.get('is_price_criteria'),
                        )

                    return True
                else:
                    self.logger.error('保存评分规则到数据库失败')
                    return False
            else:
                self.logger.error(
                    '提取评分规则失败：未从招标文件解析出评分规则（严格禁止使用默认规则）。'
                )
                return False

        except Exception as e:
            self.logger.error('初始化项目分析时出错: %s', e, exc_info=True)
            self.db.rollback()
            return False

    def analysis_task(
        self,
        project_id: int,
        bid_document_id: int,
        tender_file_path: str,
        bid_file_path: str,
    ):
        """
        分析单个投标文件的任务

        Args:
            project_id: 项目ID
            bid_document_id: 投标文件ID
            tender_file_path: 招标文件路径
            bid_file_path: 投标文件路径
        """
        from modules.database import SessionLocal

        # 在线程中创建新的日志记录器
        import logging

        logger = logging.getLogger(f'{__name__}.analysis_task')
        logger.info('=== 开始执行analysis_task ===')
        logger.info(
            '项目ID: %d, 投标文件ID: %d, 文件路径: %s',
            project_id,
            bid_document_id,
            bid_file_path,
        )
        logger.info('开始分析投标文件: %s', bid_file_path)

        db = SessionLocal()
        try:
            # 获取投标文档
            bid_document = (
                db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
            )
            if not bid_document:
                self.logger.error('未找到投标文档: %d', bid_document_id)
                return

            # 更新状态为正在处理
            bid_document.processing_status = 'processing'  # type: ignore[assignment]
            bid_document.progress_current_rule = '开始分析...'
            db.commit()

            # 创建智能投标分析器
            self.logger.info('开始创建智能投标分析器，投标文件: %s', bid_file_path)
            analyzer = IntelligentBidAnalyzer(
                tender_file_path, bid_file_path, db, bid_document_id, project_id
            )
            self.logger.info('智能投标分析器创建成功')

            # 分析投标文件
            self.logger.info('开始分析投标文件: %s', bid_file_path)
            analysis_result = analyzer.analyze_bidding_document()
            self.logger.info(
                '投标文件分析完成，结果: %s', analysis_result.get('status', 'unknown')
            )

            # 更新分析结果
            if analysis_result['status'] == 'success':
                bid_document.processing_status = 'completed'  # type: ignore[assignment]
                bid_document.progress_current_rule = '分析完成'

                # 更新分析结果记录
                result_record = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_document_id)
                    .first()
                )
                if result_record:
                    # 更新投标人名称（如果AI提取到了）
                    details = analysis_result.get('details', {})
                    if '投标人名称' in details and details['投标人名称'] != '未提取':
                        bid_document.bidder_name = details['投标人名称']
                        result_record.bidder_name = details['投标人名称']

                    # 更新投标总价（如果AI提取到了）
                    if '投标总价' in details and details['投标总价'] != '未提取':
                        try:
                            # 尝试保存投标总价到数据库
                            price_str = str(details['投标总价'])
                            # 使用统一的价格提取管理器提取价格
                            from modules.price_extraction_manager import (
                                PriceExtractionManager,
                            )

                            price_manager = PriceExtractionManager()
                            pages = [price_str]  # 将价格字符串转换为页面列表格式
                            price_value = price_manager.extract_and_select_price(pages)
                            if price_value is not None:
                                # 价格信息将在AnalysisResult中保存
                                pass
                        except (ValueError, TypeError) as e:
                            self.logger.warning(
                                '无法解析投标总价: %s, 错误: %s', details['投标总价'], e
                            )
                self.logger.info('投标文件分析完成: %s', bid_document.bidder_name)
            else:
                bid_document.processing_status = 'error'  # type: ignore[assignment]
                bid_document.error_message = analysis_result['message']
                bid_document.progress_current_rule = '分析失败'
                self.logger.error('投标文件分析失败: %s', analysis_result['message'])

            db.commit()

        except Exception as e:
            logger.error('分析任务执行过程中发生意外错误: %s', e, exc_info=True)
            if 'bid_document' in locals() and bid_document:
                bid_document.processing_status = 'error'  # type: ignore[assignment]
                bid_document.error_message = f'分析过程中发生意外错误: {str(e)}'  # type: ignore[assignment]
                bid_document.progress_current_rule = '分析失败'
                db.commit()
        finally:
            logger.info('=== analysis_task 执行结束 ===')
            db.close()

    def run_analysis_and_calculate_prices(self, project_id: int, bid_files_info: list):
        """
        运行分析并计算价格分

        Args:
            project_id: 项目ID
            bid_files_info: 投标文件信息列表
        """
        self.logger.info('开始为项目 %d 执行后台分析和价格计算任务。', project_id)

        # 首先提取评分规则并保存到数据库
        if not self.initialize_project_analysis(project_id):
            self.logger.error('项目 %d 评分规则初始化失败', project_id)

        # 获取项目信息
        project = (
            self.db.query(TenderProject).filter(TenderProject.id == project_id).first()
        )
        if not project:
            self.logger.error('项目 %d 未找到', project_id)
            return

        tender_file_path = project.tender_file_path

        # 为每个投标文件创建分析任务
        self.logger.info('开始为 %d 个投标文件创建分析任务', len(bid_files_info))
        for i, bid_info in enumerate(bid_files_info):
            self.logger.info(
                '投标文件 %d: ID=%d, 路径=%s', i, bid_info['id'], bid_info['path']
            )

        # 使用线程池而不是进程池，避免序列化问题
        executor = ThreadPoolExecutor(max_workers=min(len(bid_files_info), 4))
        try:
            futures = []
            for i, bid_info in enumerate(bid_files_info):
                try:
                    self.logger.info(
                        '正在为第 %d 个投标文件 (ID=%d, 路径=%s) 创建分析任务',
                        i + 1,
                        bid_info['id'],
                        bid_info['path'],
                    )
                    future = executor.submit(
                        self.analysis_task,
                        project_id,
                        bid_info['id'],
                        tender_file_path,
                        bid_info['path'],
                    )
                    futures.append(future)
                    self.logger.info('第 %d 个投标文件的分析任务创建成功', i + 1)
                except Exception as e:
                    self.logger.error(
                        '为第 %d 个投标文件 (ID=%d) 创建分析任务时出错: %s',
                        i + 1,
                        bid_info['id'],
                        e,
                        exc_info=True,
                    )

            # 等待所有分析任务完成
            self.logger.info('开始等待 %d 个分析任务完成', len(futures))
            if futures:
                try:
                    # 等待所有任务完成
                    for i, future in enumerate(futures):
                        try:
                            self.logger.info('正在等待第 %d 个分析任务完成...', i + 1)
                            result = future.result()  # 这会阻塞直到任务完成
                            self.logger.info('第 %d 个分析任务执行成功', i + 1)
                        except Exception as e:
                            self.logger.error(
                                '第 %d 个分析任务执行失败: %s', i + 1, e, exc_info=True
                            )
                    self.logger.info(
                        '项目 %d 的所有 %d 个分析任务已完成。', project_id, len(futures)
                    )
                except Exception as e:
                    self.logger.error(
                        '等待项目 %d 的分析任务完成时出错: %s',
                        project_id,
                        e,
                        exc_info=True,
                    )
            else:
                self.logger.warning('项目 %d 没有需要分析的投标文件。', project_id)
        finally:
            # 确保线程池被正确关闭
            executor.shutdown(wait=True)

        # 计算价格分
        try:
            self.logger.info(f'开始为项目 {project_id} 计算价格分。')
            calculator = PriceScoreCalculator(db_session=self.db)
            price_scores_result = calculator.calculate_project_price_scores(project_id)

            if price_scores_result:
                # 重新获取分析结果以计算更新了多少个投标人
                analysis_results = (
                    self.db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .all()
                )
                self.logger.info(
                    '项目 %s 价格分计算完成，更新了 %s 个投标方。',
                    project_id,
                    len(analysis_results),
                )
            else:
                self.logger.warning('项目 %s 未能计算出任何价格分。', project_id)

            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if project is not None:
                has_errors = (
                    self.db.query(BidDocument)
                    .filter(
                        BidDocument.project_id == project_id,
                        BidDocument.processing_status == 'error',
                    )
                    .count()
                    > 0
                )

                project.status = 'completed_with_errors' if has_errors else 'completed'
                self.db.commit()
                self.logger.info(
                    '项目 %s 的状态已更新为 %s。', project_id, project.status
                )

        except Exception as e:
            self.logger.error(f'为项目 {project_id} 计算价格分时出错: {e}')
            self.logger.error(traceback.format_exc())
