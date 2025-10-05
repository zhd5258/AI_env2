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
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:30:00
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-26 18:30:00
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
from concurrent.futures import ProcessPoolExecutor
import os

from modules.database import TenderProject, BidDocument, AnalysisResult
from modules.intelligent_scoring_extractor import IntelligentScoringExtractor
from modules.scoring_rules_manager import ScoringRulesManager
from modules.price_score_calculator import PriceScoreCalculator
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer

# 创建一个进程池
executor = ProcessPoolExecutor(max_workers=os.cpu_count())


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
            self.logger.info(f'开始初始化项目分析，项目ID: {project_id}')

            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if not project:
                self.logger.error(f'项目不存在: {project_id}')
                return False

            tender_file_path = project.tender_file_path
            if not tender_file_path or not os.path.exists(tender_file_path):
                self.logger.error(f'招标文件不存在: {tender_file_path}')
                return False

            self.logger.info(f'项目 {project_id} 没有评分规则，开始从招标文件提取...')

            # 使用TenderAnalyzer提取评分规则
            from modules.tender_analyzer import TenderAnalyzer
            analyzer = TenderAnalyzer(tender_file_path, self.db, project_id)
            scoring_rules = analyzer.extract_scoring_rules()

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
                            f'评分规则: criteria_name={rule_data.get("criteria_name")}, max_score={rule_data.get("max_score")}, is_price_criteria={rule_data.get("is_price_criteria")}'
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
            self.logger.error(f'初始化项目分析时出错: {e}', exc_info=True)
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

        db = SessionLocal()
        try:
            # 获取投标文档
            bid_document = (
                db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
            )
            if not bid_document:
                self.logger.error(f'未找到投标文档: {bid_document_id}')
                return

            # 更新状态为正在处理
            bid_document.processing_status = 'processing'  # type: ignore[assignment]
            bid_document.progress_current_rule = '开始分析...'
            db.commit()

            # 创建智能投标分析器
            analyzer = IntelligentBidAnalyzer(
                tender_file_path, bid_file_path, db, bid_document_id, project_id
            )

            # 分析投标文件
            analysis_result = analyzer.analyze_bidding_document()

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
                    bidder_name_extracted = False
                    if '投标人名称' in details and details['投标人名称'] != '未提取':
                        bid_document.bidder_name = details['投标人名称']
                        result_record.bidder_name = details['投标人名称']
                        bidder_name_extracted = True

                    # 如果AI没有提取到投标人名称，则尝试从文件中提取
                    if not bidder_name_extracted:
                        try:
                            from modules.bidder_name_extractor import extract_bidder_name_from_file
                            # 优先从MD文件提取投标人名称
                            pdf_processor = PDFProcessor(bid_document.file_path)
                            md_file_path = pdf_processor.get_md_file_path()
                            if os.path.exists(md_file_path):
                                extracted_name = extract_bidder_name_from_file(md_file_path)
                            else:
                                extracted_name = extract_bidder_name_from_file(bid_document.file_path)
                            if extracted_name and extracted_name != '未提取':
                                bid_document.bidder_name = extracted_name
                                result_record.bidder_name = extracted_name
                        except Exception as e:
                            self.logger.warning(f'从文件中提取投标人名称时出错: {e}')
                    
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
                                f'无法解析投标总价: {details["投标总价"]}, 错误: {e}'
                            )
                self.logger.info(f'投标文件分析完成: {bid_document.bidder_name}')
            else:
                bid_document.processing_status = 'error'  # type: ignore[assignment]
                bid_document.error_message = analysis_result['message']
                bid_document.progress_current_rule = '分析失败'
                self.logger.error(f'投标文件分析失败: {analysis_result["message"]}')

            db.commit()

        except Exception as e:
            self.logger.error(f'分析任务执行过程中发生意外错误: {e}', exc_info=True)
            if bid_document:
                bid_document.processing_status = 'error'  # type: ignore[assignment]
                bid_document.error_message = f'分析过程中发生意外错误: {str(e)}'
                bid_document.progress_current_rule = '分析失败'
                db.commit()
        finally:
            db.close()

    def run_analysis_and_calculate_prices(self, project_id: int, bid_files_info: list):
        """
        运行分析并计算价格分

        Args:
            project_id: 项目ID
            bid_files_info: 投标文件信息列表
        """
        self.logger.info(f'开始为项目 {project_id} 执行后台分析和价格计算任务。')

        # 首先提取评分规则并保存到数据库
        if not self.initialize_project_analysis(project_id):
            self.logger.error(f'项目 {project_id} 评分规则初始化失败')

        # 获取项目信息
        project = (
            self.db.query(TenderProject).filter(TenderProject.id == project_id).first()
        )
        if not project:
            self.logger.error(f'项目 {project_id} 未找到')
            return

        tender_file_path = project.tender_file_path

        # 为每个投标文件创建分析任务
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        futures = []
        for bid_info in bid_files_info:
            try:
                future = loop.run_in_executor(
                    executor,
                    self.analysis_task,
                    project_id,
                    bid_info['id'],
                    tender_file_path,
                    bid_info['bid_file_path'],  # 修复键名
                )
                futures.append(future)
            except Exception as e:
                self.logger.error(
                    f'为投标文件 {bid_info["id"]} 创建分析任务时出错: {e}'
                )

        # 等待所有分析任务完成
        if futures:
            try:
                loop.run_until_complete(
                    asyncio.gather(*futures, return_exceptions=True)
                )
                self.logger.info(f'项目 {project_id} 的所有分析任务已完成。')
            except Exception as e:
                self.logger.error(f'等待项目 {project_id} 的分析任务完成时出错: {e}')
        else:
            self.logger.warning(f'项目 {project_id} 没有需要分析的投标文件。')

        loop.close()

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
