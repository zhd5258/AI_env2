#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:46:24
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-20 06:36:49
# 文件相对于项目的路径   : \AI_ENV2\modules\analysis_manager.py
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
import json
import codecs
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import os
import threading
import glob
import datetime
import time

from modules.workflow_status import (
    WorkflowStatus,
    AnalysisTaskStatus,
    PriceCalculationStatus,
)

from models.database import TenderProject, BidDocument, AnalysisResult, ScoringRule

# 修正导入错误，使用正确的模块名
from modules.correct_scoring_extractor import CorrectScoringExtractor
from modules.scoring_rules_manager import ScoringRulesManager
from modules.price_score_calculator import PriceScoreCalculator
from modules.enhanced_intelligent_bid_analyzer import EnhancedIntelligentBidAnalyzer
from modules.runtime_config import load_config, get_bool
from modules.batch_pdf_processor import BatchPDFProcessor

# 禁止并行处理，移除线程池
# executor = ThreadPoolExecutor(max_workers=4)

# 添加一个锁来防止并行PDF转换
pdf_conversion_lock = threading.Lock()


class AnalysisManager:
    """分析管理器，统一处理项目分析流程"""

    def __init__(self, db_session: Optional[Session] = None):
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
        if self.db is None:
            self.logger.error('数据库会话未提供')
            return False

        try:
            self.logger.info(f'开始初始化项目分析，项目ID: {project_id}')

            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            if not project:
                self.logger.error(f'项目不存在: {project_id}')
                return False

            tender_file_path = project.tender_file_path
            if not str(tender_file_path) or not os.path.exists(str(tender_file_path)):
                self.logger.error(f'招标文件不存在: {tender_file_path}')
                return False

            # 检查项目是否已经有评分规则
            existing_rules = []
            if self.db is not None:
                existing_rules = (
                    self.db.query(ScoringRule)
                    .filter(ScoringRule.project_id == project_id)
                    .all()
                )

            # 如果已经有评分规则，检查是否包含价格评分规则
            if existing_rules:
                has_price_rule = any(
                    getattr(rule, 'is_price_criteria', False) for rule in existing_rules
                )
                self.logger.info(
                    f'项目 {project_id} 已有 {len(existing_rules)} 条评分规则，包含价格规则: {has_price_rule}'
                )

                # 记录现有的评分规则详细信息
                for rule in existing_rules:
                    self.logger.info(
                        f'现有评分规则: Parent_Item_Name={getattr(rule, "Parent_Item_Name", "")}, '
                        f'Child_Item_Name={getattr(rule, "Child_Item_Name", "")}, '
                        f'Parent_max_score={getattr(rule, "Parent_max_score", 0)}, '
                        f'Child_max_score={getattr(rule, "Child_max_score", 0)}, '
                        f'is_price_criteria={getattr(rule, "is_price_criteria", False)}'
                    )

                # 如果已有评分规则，无论是否包含价格规则，都返回True
                # 价格计算将在后续流程中处理
                self.logger.info(f'项目 {project_id} 已有评分规则，初始化完成')
                return True

            self.logger.info(f'项目 {project_id} 没有评分规则，开始从招标文件提取...')

            # 使用CorrectScoringExtractor提取评分规则
            extractor = CorrectScoringExtractor(str(tender_file_path))
            scoring_rules = extractor.extract_scoring_rules()

            if scoring_rules:
                # 检查是否至少有一个定量规则
                if not any(
                    child.get('max_score', 0) > 0
                    for rule in scoring_rules
                    for child in rule.get('children', [rule])
                ):
                    self.logger.error(
                        '评分规则提取失败：未找到任何有分值的评分项。请检查招标文件中的评分表格。'
                    )
                    return False

                # 使用统一的评分规则管理器保存评分规则
                rules_manager = ScoringRulesManager(db_session=self.db)
                save_result = rules_manager.save_scoring_rules(
                    project_id, scoring_rules
                )

                if save_result:
                    self.logger.info(
                        '成功提取并保存 %s 条评分规则到数据库', len(scoring_rules)
                    )

                    # 记录提取到的评分规则详细信息，包括规则名称、总分值、是否父项或子项以及规则描述
                    for rule_data in scoring_rules:
                        criteria_name = rule_data.get('criteria_name', '未知规则')
                        max_score = rule_data.get('max_score', 0)
                        is_price_criteria = rule_data.get('is_price_criteria', False)
                        description = rule_data.get('description', '')
                        is_parent = rule_data.get('is_parent', False)
                        children = rule_data.get('children', [])

                        # 判断是父项还是子项
                        item_type = '父项' if is_parent or children else '子项'

                        self.logger.info(
                            f'评分规则: criteria_name={criteria_name}, max_score={max_score}, is_price_criteria={is_price_criteria}, type={item_type}, description={description}'
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
        from models.database import SessionLocal

        db = SessionLocal()
        bid_document = None  # 初始化bid_document变量
        try:
            # 检查必要参数
            if (
                not project_id
                or not bid_document_id
                or not tender_file_path
                or not bid_file_path
            ):
                self.logger.error('分析任务触发条件不满足：缺少必要参数')
                return

            # 获取投标文档
            bid_document = (
                db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
            )
            if not bid_document:
                self.logger.error(f'未找到投标文档: {bid_document_id}')
                return

            # 确保投标人名称不为空，如果为空则使用文件名作为默认值
            bidder_name_value = (
                str(getattr(bid_document, 'bidder_name', ''))
                if getattr(bid_document, 'bidder_name', '')
                else ''
            )
            if not bidder_name_value or not bidder_name_value.strip():
                try:
                    filename = os.path.basename(str(bid_file_path))
                    bidder_name = os.path.splitext(filename)[0]
                    # 确保投标人名称不为空
                    if not bidder_name or not bidder_name.strip():
                        bidder_name = '未知投标方'
                    setattr(bid_document, 'bidder_name', str(bidder_name))
                    self.logger.info(f'初始化投标人名称: {bidder_name}')
                    # 提交更改到数据库
                    db.commit()
                except Exception as init_e:
                    self.logger.error(f'初始化投标人名称时出错: {init_e}')
                    db.rollback()

            # 初始化result_record变量
            result_record = None

            # 更新状态为正在处理
            setattr(bid_document, 'processing_status', 'processing')
            setattr(bid_document, 'progress_current_rule', '开始分析...')
            setattr(bid_document, 'processing_phase', 'PDF处理中')  # 添加处理阶段信息
            db.commit()

            # 移除在MD转换完成后立即提取投标人名称的逻辑
            # 改为使用统一提取器在招标文件分析完成后集中处理

            # 创建智能投标分析器，传递投标人名称
            analyzer = EnhancedIntelligentBidAnalyzer(
                tender_file_path, bid_file_path, db, bid_document_id, project_id
            )
            # 确保分析器中的投标人名称与数据库中的保持一致
            # 修复：只有在分析器中的投标人名称为空时，才使用数据库中的值
            # 不应该用分析器的默认值覆盖数据库中已有的有效名称
            if (
                not hasattr(analyzer, 'bidder_name')
                or not analyzer.bidder_name
                or not str(analyzer.bidder_name).strip()
            ):
                # 分析器中没有有效的投标人名称，使用数据库中的值
                if (
                    str(bid_document.bidder_name)
                    and str(bid_document.bidder_name).strip()
                ):
                    analyzer.bidder_name = bid_document.bidder_name
                else:
                    # 数据库中也没有有效的投标人名称，使用分析器中的默认值（文件名）
                    setattr(bid_document, 'bidder_name', str(analyzer.bidder_name))
                    # 同时更新数据库中的记录
                    try:
                        db.commit()
                    except Exception as e:
                        self.logger.warning(f'更新数据库中的投标人名称时出错: {e}')
            else:
                # 分析器中已有有效的投标人名称，确保数据库中的值与之一致
                if str(bid_document.bidder_name) != str(analyzer.bidder_name):
                    setattr(bid_document, 'bidder_name', str(analyzer.bidder_name))
                    # 同时更新数据库中的记录
                    try:
                        db.commit()
                    except Exception as e:
                        self.logger.warning(f'更新数据库中的投标人名称时出错: {e}')

            # 分析投标文件
            analysis_result = analyzer.analyze_bidding_document()

            # 更新分析结果
            if analysis_result['status'] == 'success':
                bid_document.processing_status = 'completed'  # type: ignore[assignment]
                setattr(bid_document, 'progress_current_rule', '分析完成')
                bid_document.processing_phase = '分析完成'  # 更新处理阶段信息

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

                    # 修复：确保正确提取投标人名称
                    if (
                        '投标人名称' in details
                        and isinstance(details, dict)
                        and details.get('投标人名称') != '未提取'
                        and str(details.get('投标人名称')).strip()
                        and details.get('投标人名称') is not None
                    ):
                        # 只有当AI提取到有效名称时才更新
                        valid_extracted_name = str(
                            details.get('投标人名称', '')
                        ).strip()
                        # 确保名称不为空且有效
                        if (
                            valid_extracted_name
                            and len(valid_extracted_name) > 1
                            and valid_extracted_name != '未提取'
                        ):
                            setattr(bid_document, 'bidder_name', valid_extracted_name)
                            setattr(result_record, 'bidder_name', valid_extracted_name)
                            bidder_name_extracted = True
                            self.logger.info(
                                f'通过AI分析更新投标人名称: {valid_extracted_name}'
                            )
                            # 确保提交数据库更改
                            try:
                                db.commit()
                                self.logger.info(
                                    f'成功提交AI提取的投标人名称: {valid_extracted_name}'
                                )
                            except Exception as commit_e:
                                self.logger.error(f'提交数据库更改时出错: {commit_e}')
                                db.rollback()

                    # 如果AI没有提取到投标人名称，则尝试从文件中提取（但仅在数据库中当前名称为空或无效时）
                    if not bidder_name_extracted:
                        # 检查当前数据库中的名称是否有效
                        current_db_name = bid_document.bidder_name
                        is_current_name_valid = (
                            current_db_name
                            and current_db_name.strip()
                            and current_db_name != '未知投标方'
                            and current_db_name != '未提取'
                            and current_db_name != 'None'
                            and len(current_db_name.strip()) > 1
                        )

                        # 只有在当前名称无效时才尝试重新提取
                        if not bool(is_current_name_valid):
                            try:
                                from modules.bidder_name_extractor import (
                                    extract_bidder_name_from_file,
                                )

                                # 优先从MD文件提取投标人名称
                                from modules.pdf_processor import PDFProcessor

                                pdf_processor = PDFProcessor(
                                    str(bid_document.file_path)
                                )
                                md_file_path = pdf_processor.get_md_file_path()
                                if os.path.exists(md_file_path):
                                    extracted_name = extract_bidder_name_from_file(
                                        md_file_path
                                    )
                                else:
                                    extracted_name = extract_bidder_name_from_file(
                                        str(bid_document.file_path)
                                    )
                                # 确保提取到的名称不是None或空字符串
                                if (
                                    extracted_name
                                    and extracted_name.strip()
                                    and extracted_name != '未提取'
                                    and extracted_name != 'None'
                                    and len(extracted_name.strip()) > 1
                                ):
                                    valid_name = extracted_name.strip()
                                    setattr(
                                        bid_document, 'bidder_name', str(valid_name)
                                    )
                                    setattr(
                                        result_record, 'bidder_name', str(valid_name)
                                    )
                                    # 同时更新分析器中的投标人名称
                                    # setattr(self, 'analyzer', analyzer)  # 更新分析器中的投标人名称
                                    pass
                                    # self.analyzer.bidder_name = valid_name
                                    self.logger.info(
                                        f'通过文件提取更新投标人名称: {valid_name}'
                                    )
                                    # 确保提交数据库更改
                                    try:
                                        db.commit()
                                        self.logger.info(
                                            f'成功提交文件提取的投标人名称: {valid_name}'
                                        )
                                    except Exception as commit_e:
                                        self.logger.error(
                                            f'提交数据库更改时出错: {commit_e}'
                                        )
                                        db.rollback()
                                else:
                                    self.logger.warning('文件提取未获得有效投标人名称')
                            except Exception as e:
                                self.logger.warning(
                                    f'从文件中提取投标人名称时出错: {e}'
                                )
                        else:
                            self.logger.info(
                                f'保留现有有效投标人名称: {current_db_name}'
                            )

                        # 如果仍然没有有效的投标人名称，使用文件名作为备用
                        if (
                            not str(bid_document.bidder_name)
                            or not str(bid_document.bidder_name).strip()
                            or str(bid_document.bidder_name) == '未知投标方'
                            or str(bid_document.bidder_name) == 'None'
                        ):
                            try:
                                filename = os.path.basename(str(bid_document.file_path))
                                bidder_name = os.path.splitext(filename)[0]
                                # 确保投标人名称不为空
                                if not bidder_name or not bidder_name.strip():
                                    bidder_name = '未知投标方'
                                setattr(bid_document, 'bidder_name', str(bidder_name))
                                setattr(result_record, 'bidder_name', str(bidder_name))
                                self.logger.warning(
                                    f'未提取到有效投标人名称，使用文件名作为备用: {bidder_name}'
                                )
                                # 确保提交数据库更改
                                try:
                                    db.commit()
                                    self.logger.info(
                                        f'成功提交备用投标人名称: {bidder_name}'
                                    )
                                except Exception as commit_e:
                                    self.logger.error(
                                        f'提交数据库更改时出错: {commit_e}'
                                    )
                                    db.rollback()
                            except Exception as fallback_e:
                                self.logger.error(
                                    f'设置备用投标人名称时出错: {fallback_e}'
                                )
                                # 最后的兜底方案
                                setattr(bid_document, 'bidder_name', '未知投标方')
                                setattr(result_record, 'bidder_name', '未知投标方')
                                # 确保提交数据库更改
                                try:
                                    db.commit()
                                    self.logger.info(
                                        '成功提交兜底投标人名称: 未知投标方'
                                    )
                                except Exception as commit_e:
                                    self.logger.error(
                                        f'提交数据库更改时出错: {commit_e}'
                                    )
                                    db.rollback()

                    # 更新投标总价（如果AI提取到了）
                    if (
                        isinstance(details, dict)
                        and '投标总价' in details
                        and details.get('投标总价') != '未提取'
                    ):
                        # 价格提取已移到统一流程中，此处不再处理
                        pass

                    # 保存分析结果到数据库
                    try:
                        # 获取AI分析器计算的子项分数总和
                        other_scores_total = analysis_result.get(
                            'other_scores_total', 0
                        )

                        # 更新分析结果记录
                        # 初始总分设置为非价格项的总分，这是价格计算的基础
                        setattr(
                            result_record,
                            'total_score',
                            other_scores_total,
                        )
                        # 不再更新price_score字段，因为价格分将在价格计算工作流中计算
                        # 只有当analysis_result中包含price_score且数据库中还没有价格分时才更新
                        # if 'price_score' in analysis_result:
                        #     setattr(
                        #         result_record,
                        #         'price_score',
                        #         float(analysis_result.get('price_score', 0)),
                        #     )
                        # 价格分将在后续计算，此处不再强制设置为0
                        # 移除在非价格项分析阶段对extracted_price的错误处理
                        # 处理 detailed_scores 数据格式
                        detailed_scores_data = analysis_result.get(
                            'detailed_scores', []
                        )
                        # 确保detailed_scores是JSON可序列化的格式
                        if isinstance(detailed_scores_data, list):
                            # 验证列表中的每个元素都是字典
                            validated_scores = []
                            for item in detailed_scores_data:
                                if isinstance(item, dict):
                                    validated_scores.append(item)
                            detailed_scores_data = validated_scores

                        # 直接存储detailed_scores数据，让GB18030JSONType处理编码
                        setattr(result_record, 'detailed_scores', detailed_scores_data)

                        setattr(
                            result_record,
                            'analysis_summary',
                            str(analysis_result.get('analysis_summary', '')),
                        )
                        setattr(
                            result_record,
                            'ai_model',
                            str(analysis_result.get('ai_model', '')),
                        )
                        # 直接存储original_scores数据，让GB18030JSONType处理编码
                        setattr(result_record, 'original_scores', detailed_scores_data)

                        setattr(
                            result_record,
                            'last_modified_at',
                            datetime.datetime.now(),
                        )
                        setattr(result_record, 'last_modified_by', 'system')

                        # 如果还没有设置投标人名称，则使用bid_document中的名称
                        current_bidder_name = getattr(result_record, 'bidder_name', '')
                        if (
                            not current_bidder_name
                            or not str(current_bidder_name).strip()
                            or str(current_bidder_name) == 'None'
                            or str(current_bidder_name) == '未知投标方'
                            or str(current_bidder_name) == '未提取'
                        ):
                            setattr(
                                result_record,
                                'bidder_name',
                                str(bid_document.bidder_name),
                            )

                        db.commit()
                        self.logger.info(
                            f'成功保存分析结果到数据库: {bid_document.bidder_name}'
                        )
                        # 记录保存的详细评分信息
                        self.logger.info(f'保存的详细评分: {detailed_scores_data}')
                    except Exception as e:
                        self.logger.error(f'保存分析结果到数据库时出错: {e}')
                        self.logger.error(traceback.format_exc())
                        db.rollback()
                # 如果没有找到分析结果记录，则创建新的记录
                else:
                    self.logger.warning(
                        f'未找到分析结果记录，准备创建新的记录: bid_document_id={bid_document_id}'
                    )
                    try:
                        # 获取AI分析器计算的子项分数总和
                        other_scores_total = analysis_result.get(
                            'other_scores_total', 0
                        )

                        # 处理 detailed_scores 数据格式
                        detailed_scores_data = analysis_result.get(
                            'detailed_scores', []
                        )
                        # 确保detailed_scores是JSON可序列化的格式
                        if isinstance(detailed_scores_data, list):
                            # 验证列表中的每个元素都是字典
                            validated_scores = []
                            for item in detailed_scores_data:
                                if isinstance(item, dict):
                                    validated_scores.append(item)
                            detailed_scores_data = validated_scores

                        # 直接使用detailed_scores数据，让GB18030JSONType处理编码
                        detailed_scores_json = detailed_scores_data

                        # 直接使用original_scores数据，让GB18030JSONType处理编码
                        original_scores_json = detailed_scores_data

                        # 将detailed_scores转换为JSON字符串存储
                        new_result_record = AnalysisResult(
                            project_id=project_id,
                            bid_document_id=bid_document_id,
                            bidder_name=str(bid_document.bidder_name),
                            total_score=other_scores_total,  # 初始总分设为非价格项的总分
                            # 不再设置price_score，因为价格分将在价格计算工作流中计算
                            price_score=0.0,  # 价格分将在后续计算
                            extracted_price=0.0,  # 设置默认值以满足数据库非空约束
                            detailed_scores=detailed_scores_json,
                            analysis_summary=str(
                                analysis_result.get('analysis_summary', '')
                            ),
                            ai_model=str(analysis_result.get('ai_model', '')),
                            original_scores=original_scores_json,
                            last_modified_at=datetime.datetime.now(),
                            last_modified_by='system',
                            dynamic_scores={},
                        )
                        db.add(new_result_record)
                        db.commit()
                        self.logger.info(
                            f'成功创建新的分析结果记录: {bid_document.bidder_name}'
                        )
                        # 记录保存的详细评分信息
                        self.logger.info(f'保存的详细评分: {detailed_scores_data}')
                    except Exception as e:
                        self.logger.error(f'创建新的分析结果记录时出错: {e}')
                        self.logger.error(traceback.format_exc())
                        db.rollback()

                self.logger.info(f'投标文件分析完成: {bid_document.bidder_name}')

                # 更新投标文件状态为completed
                bid_document.processing_status = 'completed'
                setattr(bid_document, 'progress_current_rule', '分析完成')
                bid_document.processing_phase = '分析完成'
                db.commit()
                self.logger.info(
                    f'已将投标文件 {bid_document.bidder_name} 状态更新为 completed'
                )

                # 延迟检查项目完成状态，避免竞态条件
                self._delayed_check_and_update_project_status(
                    project_id, delay_seconds=2
                )

            elif analysis_result['status'] == 'warning':
                # 警告状态，但仍标记为完成
                bid_document.processing_status = 'completed'  # type: ignore[assignment]
                setattr(bid_document, 'progress_current_rule', '分析完成（质量警告）')
                bid_document.processing_phase = '分析完成'  # 更新处理阶段信息
                setattr(bid_document, 'error_message', str(analysis_result['message']))
                self.logger.warning(
                    f'投标文件分析完成但有警告: {analysis_result["message"]}'
                )
            else:
                bid_document.processing_status = 'error'  # type: ignore[assignment]
                setattr(bid_document, 'error_message', str(analysis_result['message']))
                setattr(bid_document, 'progress_current_rule', '分析失败')
                self.logger.error(f'投标文件分析失败: {analysis_result["message"]}')

            db.commit()
            self.logger.info(
                f'分析任务完成，已提交数据库更改: {bid_document.bidder_name}'
            )

        except Exception as e:
            self.logger.error(f'分析任务执行过程中发生意外错误: {e}', exc_info=True)
            # 确保bid_document已定义
            if 'bid_document' in locals() and bid_document is not None:
                try:
                    setattr(bid_document, 'processing_status', 'error')
                    setattr(
                        bid_document,
                        'error_message',
                        f'分析过程中发生意外错误: {str(e)}',
                    )
                    setattr(bid_document, 'progress_current_rule', '分析失败')
                    db.commit()
                    self.logger.info(
                        f'已将投标文件状态更新为error: {bid_document.bidder_name}'
                    )
                except Exception as commit_e:
                    self.logger.error(f'提交数据库更改时出错: {commit_e}')
                    db.rollback()
        finally:
            db.close()

    def _cleanup_md_files(self, project_id: int):
        """
        清理项目生成的MD文件

        Args:
            project_id: 项目ID
        """
        try:
            # 加载运行时配置
            runtime_config = load_config()
            auto_delete = get_bool('auto_delete_md_files', False)

            # 如果没有启用自动删除，则直接返回
            if not auto_delete:
                self.logger.info(f'项目 {project_id} 未启用自动删除MD文件功能')
                return

            # 获取项目信息
            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            if not project:
                self.logger.warning(f'项目 {project_id} 未找到，无法清理MD文件')
                return

            # 删除招标文件对应的MD文件
            if project.tender_file_path is not None and os.path.exists(
                str(project.tender_file_path)
            ):
                tender_md_path = os.path.join(
                    'output',
                    f'{os.path.splitext(os.path.basename(str(project.tender_file_path)))[0]}.md',
                )
                if os.path.exists(tender_md_path):
                    os.remove(tender_md_path)
                    self.logger.info(f'已删除招标文件MD文件: {tender_md_path}')

            # 删除投标文件对应的MD文件
            bid_documents = []
            if self.db is not None:
                bid_documents = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.project_id == project_id)
                    .all()
                )

            for bid_doc in bid_documents:
                if bid_doc.file_path is not None and os.path.exists(
                    str(bid_doc.file_path)
                ):
                    bid_md_path = os.path.join(
                        'output',
                        f'{os.path.splitext(os.path.basename(str(bid_doc.file_path)))[0]}.md',
                    )
                    if os.path.exists(bid_md_path):
                        os.remove(bid_md_path)
                        self.logger.info(f'已删除投标文件MD文件: {bid_md_path}')

            self.logger.info(f'项目 {project_id} 的MD文件清理完成')
        except Exception as e:
            self.logger.error(f'清理项目 {project_id} 的MD文件时出错: {e}')

    def run_analysis_and_calculate_prices(self, project_id: int, bid_files_info: list):
        """
        运行分析并计算价格分

        Args:
            project_id: 项目ID
            bid_files_info: 投标文件信息列表
        """
        self.logger.info(f'开始为项目 {project_id} 执行后台分析和价格计算任务。')

        # 检查触发条件
        # 1. 招标文件解析完成(任务状态标记为"completed")
        # 2. 价格计算子流程状态标记为"processing"
        # 3. 项目ID和投标文件信息列表必须提供
        # 4. 评分规则初始化成功
        # 5. 项目信息存在且包含招标文件路径
        # 6. 所有投标文件分析任务尚未开始

        # 检查必要参数
        if not project_id or not bid_files_info:
            self.logger.error('价格计算触发条件不满足：缺少必要参数')
            return

        # 首先提取评分规则并保存到数据库
        if not self.initialize_project_analysis(project_id):
            self.logger.error(f'项目 {project_id} 评分规则初始化失败')
            return

        # 获取项目信息
        project = None
        if self.db is not None:
            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
        if not project:
            self.logger.error(f'项目 {project_id} 未找到')
            return

        tender_file_path = project.tender_file_path

        # 步骤1: 初始化状态
        self.logger.info(f'项目 {project_id}: 初始化分析状态...')
        if self.db is not None:
            project.status = 'analyzing'
            bid_documents = (
                self.db.query(BidDocument)
                .filter(BidDocument.project_id == project_id)
                .all()
            )
            for bid_doc in bid_documents:
                bid_doc.processing_status = 'processing'
            self.db.commit()
        self.logger.info(
            f'项目 {project_id}: 状态已更新为 "analyzing"，所有投标文件状态已更新为 "processing"。'
        )

        # 检查是否需要跳过OCR处理
        # 如果所有投标文件对应的MD文件都已存在，则跳过OCR处理
        skip_ocr = True
        output_dir = 'output'
        for bid_info in bid_files_info:
            bid_file_path = bid_info['bid_file_path']
            # 获取预期的MD文件名（与PDF文件同名，但扩展名为.md）
            md_filename = os.path.splitext(os.path.basename(bid_file_path))[0] + '.md'
            md_file_path = os.path.join(output_dir, md_filename)

            # 如果任何一个MD文件不存在，则需要进行OCR处理
            if not os.path.exists(md_file_path):
                skip_ocr = False
                break

        if skip_ocr:
            self.logger.info(
                f'项目 {project_id}: 所有投标文件的MD文件已存在，跳过OCR处理'
            )
        else:
            # 步骤2: 批量处理所有投标文件的PDF转换
            self.logger.info(f'项目 {project_id}: 开始批量处理所有投标文件的PDF转换...')

            # 收集所有需要处理的投标文件路径
            bid_file_paths = [bid_info['bid_file_path'] for bid_info in bid_files_info]

            # 使用批量处理器处理所有投标文件
            batch_processor = BatchPDFProcessor()
            processed_md_files, status_info = batch_processor.process_batch_files(
                bid_file_paths, use_online=True
            )

            # 检查处理结果
            if status_info['status'] == 'success':
                self.logger.info(
                    f'项目 {project_id}: 批量PDF转换完成，成功处理 {len(processed_md_files)} 个文件'
                )
            elif status_info['status'] == 'fallback':
                self.logger.warning(
                    f'项目 {project_id}: 批量PDF转换使用回退方案完成，处理 {len(processed_md_files)} 个文件'
                )
            else:
                self.logger.error(
                    f'项目 {project_id}: 批量PDF转换失败，状态: {status_info["message"]}'
                )
                if self.db is not None:
                    project.status = 'error'
                    self.db.commit()
                return

        # 新增步骤: 在非价格项分析之前，统一提取所有投标人的名称和价格
        self.logger.info(
            f'项目 {project_id}: 开始统一提取所有投标人的信息（名称和价格）...'
        )
        if not self._extract_all_bidders_info(project_id):
            self.logger.error(
                f'项目 {project_id}: 统一提取投标人信息失败，终止分析流程。'
            )
            if self.db is not None:
                project.status = 'error'
                self.db.commit()
            return

        # 步骤3: 为每个投标文件创建并执行分析任务
        self.logger.info(f'项目 {project_id}: 开始执行所有投标文件的非价格项分析...')
        for bid_info in bid_files_info:
            try:
                self.analysis_task(
                    project_id,
                    bid_info['bid_document_id'],
                    str(tender_file_path),
                    bid_info['bid_file_path'],
                )
            except Exception as e:
                self.logger.error(
                    f'为投标文件 {bid_info["bid_document_id"]} 创建分析任务时出错: {e}'
                )

        self.logger.info(f'项目 {project_id}: 所有非价格项分析任务已启动。')

        # 步骤3: 检查并等待所有分析任务完成
        # 使用等待机制解决竞态条件问题，确保所有分析任务的状态都已正确更新到数据库
        project_name = (
            project.name
            if project and hasattr(project, 'name')
            else f'项目{project_id}'
        )

        # 使用force_continue=True允许在超时后继续处理
        analysis_completed = self._wait_for_all_analysis_completed(
            project_id, max_wait_time=10, force_continue=True
        )

        # 获取完成统计
        completed_count, total_count = self._get_analysis_completion_stats(project_id)

        if not analysis_completed:
            self.logger.error(
                f'项目 [{project_name}]: 非价格项分析步骤未全部成功完成，无法进行价格计算。'
            )
            if self.db is not None:
                project.status = 'error'
                project.error_message = (
                    f'分析任务完成率: {completed_count}/{total_count}，无法进行价格计算'
                )
                self.db.commit()
            return

        # 如果有部分任务失败但允许继续，记录警告日志
        if completed_count < total_count:
            self.logger.warning(
                f'项目 [{project_name}]: 部分分析任务({completed_count}/{total_count})完成，'
                f'将尝试继续价格计算流程'
            )

        # 新增步骤: 使用统一综合计算器执行价格分和综合分析规则的计算
        self.logger.info(
            f'项目 {project_id}: 开始执行统一综合计算（价格分和综合分析规则）...'
        )
        try:
            from modules.unified_comprehensive_calculator import (
                UnifiedComprehensiveCalculator,
            )

            unified_calculator = UnifiedComprehensiveCalculator(db_session=self.db)

            # 执行统一综合计算
            success = unified_calculator.execute_comprehensive_calculation(project_id)

            if success:
                self.logger.info(f'项目 {project_id}: 统一综合计算执行成功。')
                # 更新项目状态为完成
                if self.db is not None:
                    project.status = 'completed'
                    project.updated_at = datetime.datetime.now()
                    self.db.commit()
                    self.logger.info(f'项目 {project_id} 状态已更新为已完成')
            else:
                self.logger.error(f'项目 {project_id}: 统一综合计算执行失败。')
                if self.db is not None:
                    project.status = 'error'
                    self.db.commit()
                return
        except Exception as e:
            self.logger.error(f'项目 {project_id}: 执行统一综合计算时出错: {e}')
            if self.db is not None:
                project.status = 'error'
                self.db.commit()
            return

        # 步骤4: 清理临时文件
        self._cleanup_md_files(project_id)

    def _extract_all_bidders_info(self, project_id: int) -> bool:
        """
        在分析开始前，统一提取所有投标人的名称和价格

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否提取成功
        """
        try:
            from modules.unified_extractor import UnifiedExtractor

            if self.db is None:
                self.logger.error('数据库会话未初始化')
                return False

            unified_extractor = UnifiedExtractor(db_session=self.db)
            bidders_info = unified_extractor.extract_all_bidders_info(project_id)

            if not bidders_info:
                self.logger.warning(
                    f'项目 {project_id}: 未能从任何文件中提取到有效的投标人信息。'
                )
                # 即使没有提取到信息，也可能不是一个致命错误，流程可以继续
                return True

            self.logger.info(
                f'项目 {project_id}: 成功提取了 {len(bidders_info)} 个投标人的信息。'
            )
            return True
        except Exception as e:
            self.logger.error(
                f'项目 {project_id}: 在统一提取投标人信息时发生严重错误: {e}',
                exc_info=True,
            )
            return False

    def _log_price_calculation_failure_details(self, project_id: int):
        """记录价格分计算失败的详细信息，用于调试"""
        try:
            self.logger.info(f'=== 价格分计算失败详细信息 (项目 {project_id}) ===')

            # 检查项目是否存在
            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            if not project:
                self.logger.error(f'项目 {project_id} 不存在')
                return

            # 检查评分规则
            scoring_rules = []
            if self.db is not None:
                scoring_rules = (
                    self.db.query(ScoringRule)
                    .filter(ScoringRule.project_id == project_id)
                    .all()
                )
            price_rule = next(
                (
                    rule
                    for rule in scoring_rules
                    if getattr(rule, 'is_price_criteria', False)
                ),
                None,
            )

            if not price_rule:
                self.logger.error(f'项目 {project_id} 没有找到价格评分规则')
            else:
                self.logger.info(
                    f'找到价格评分规则: 满分 {price_rule.Child_max_score}, 公式: {price_rule.price_formula}, 描述: {price_rule.description}'
                )

            # 检查分析结果
            analysis_results = []
            if self.db is not None:
                analysis_results = (
                    self.db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .all()
                )

            if not analysis_results:
                self.logger.error(f'项目 {project_id} 没有找到分析结果')
            else:
                self.logger.info(
                    f'项目 {project_id} 找到 {len(analysis_results)} 个分析结果'
                )
                for result in analysis_results:
                    bidder_name = result.bidder_name or f'未知投标人_{result.id}'
                    price = result.extracted_price
                    self.logger.info(f'投标人 [{bidder_name}] 提取价格: {price}')

            self.logger.info('=== 价格分计算失败详细信息结束 ===')
        except Exception as e:
            self.logger.error(f'记录价格分计算失败详细信息时出错: {e}')

    def _check_all_prices_extracted(self, project_id: int) -> bool:
        """
        检查项目中所有投标人的价格是否都已成功提取且不为空

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否所有价格都已成功提取
        """
        try:
            self.logger.info(f'检查项目 {project_id} 的投标人价格提取状态')

            # 获取项目下的所有分析结果
            analysis_results = []
            if self.db is not None:
                analysis_results = (
                    self.db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .all()
                )

            if not analysis_results:
                self.logger.warning(f'项目 {project_id} 没有找到分析结果')
                return False

            # 检查每个分析结果的价格提取状态
            all_prices_extracted = True
            valid_results_count = 0

            for result in analysis_results:
                bidder_name = result.bidder_name or f'未知投标人_{result.id}'
                extracted_price = result.extracted_price

                self.logger.info(f'投标人 [{bidder_name}] 提取价格: {extracted_price}')

                # 检查价格是否成功提取且不为空
                # extracted_price是Float类型，直接检查即可
                # 价格为0是有效价格，不应被认为是未成功提取
                # 如果价格为None，尝试从数据库获取或使用默认值
                if extracted_price is None:
                    self.logger.warning(
                        f'投标人 [{bidder_name}] 的价格未成功提取，尝试修复...'
                    )
                    # 尝试修复：设置默认值0.0
                    result.extracted_price = 0.0
                    valid_results_count += 1
                    self.logger.info(
                        f'投标人 [{bidder_name}] 的价格已修复为默认值: 0.0'
                    )
                else:
                    valid_results_count += 1

            self.logger.info(
                f'项目 {project_id} 价格提取检查完成: 有效结果数 {valid_results_count}/{len(analysis_results)}'
            )

            # 如果所有结果都有效，则返回True
            return valid_results_count == len(analysis_results)

        except Exception as e:
            self.logger.error(f'检查价格提取状态时出错: {e}')
            return False

    def _wait_for_all_analysis_completed(
        self, project_id: int, max_wait_time: int = 120, force_continue: bool = True
    ):
        """
        等待所有分析任务完成

        Args:
            project_id: 项目ID
            max_wait_time: 最大等待时间（秒）
            force_continue: 超时后是否强制继续处理
        """
        try:
            # 获取项目信息用于日志记录
            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            project_name = (
                project.name
                if project and hasattr(project, 'name')
                else f'项目{project_id}'
            )

            self.logger.info(f'等待项目 [{project_name}] 所有分析任务完成')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 等待所有分析任务完成
            wait_time = 0
            check_interval = 3  # 每3秒检查一次
            progress_report_interval = 30  # 每30秒输出一次详细进度报告

            last_progress_report = 0

            while wait_time < max_wait_time:
                # 获取完成和总数
                completed_count, total_count = self._get_analysis_completion_stats(
                    project_id
                )

                # 检查是否所有分析都已完成
                if completed_count == total_count:
                    self.logger.info(
                        f'项目 [{project_name}] 所有分析任务已完成 ({completed_count}/{total_count})'
                    )
                    return True

                # 定期输出详细进度报告
                if wait_time - last_progress_report >= progress_report_interval:
                    self.logger.info(
                        f'项目 [{project_name}] 分析进度: {completed_count}/{total_count} 完成, '
                        f'已等待 {wait_time}秒, 最大等待时间 {max_wait_time}秒'
                    )
                    last_progress_report = wait_time

                # 简单进度日志
                self.logger.debug(
                    f'项目 [{project_name}] 仍有任务未完成 ({completed_count}/{total_count}), '
                    f'已等待 {wait_time}秒, 剩余 {max_wait_time - wait_time}秒'
                )

                time.sleep(check_interval)
                wait_time += check_interval

            completed_count, total_count = self._get_analysis_completion_stats(
                project_id
            )
            self.logger.warning(
                f'项目 [{project_name}] 等待超时 ({max_wait_time}秒)，'
                f'仍有分析任务未完成 ({completed_count}/{total_count})'
            )

            # 如果设置了超时后强制继续，则处理卡住的任务并继续
            if force_continue:
                from modules.project_status_manager import ProjectStatusManager

                status_manager = ProjectStatusManager(db_session=self.db)
                stuck_count = status_manager.handle_stuck_processes(project_id)

                self.logger.warning(
                    f'项目 [{project_name}] 处理了 {stuck_count} 个卡住的任务，将继续后续流程'
                )
                return True  # 返回True以继续后续流程

            # 如果没有设置强制继续，则返回失败
            return False
        except Exception as e:
            self.logger.error(f'等待分析任务完成时出错: {str(e)}')
            try:
                from modules.project_status_manager import ProjectStatusManager

                status_manager = ProjectStatusManager(db_session=self.db)
                status_manager.handle_stuck_processes(project_id)
                # 返回部分成功
                return True
            except Exception as inner_e:
                self.logger.error(f'处理卡住的任务时出错: {inner_e}')
                return False

    def _delayed_check_and_update_project_status(
        self, project_id: int, delay_seconds: int = 2
    ):
        """
        延迟检查并更新项目状态，避免竞态条件

        Args:
            project_id: 项目ID
            delay_seconds: 延迟秒数
        """
        import threading
        import time

        def delayed_check():
            time.sleep(delay_seconds)  # 等待指定秒数确保数据库操作完成

            try:
                # 创建新的数据库会话
                from models.database import SessionLocal

                check_db = SessionLocal()
                try:
                    # 刷新会话以确保获取最新数据
                    check_db.flush()

                    # 检查项目是否仍然存在
                    project = (
                        check_db.query(TenderProject)
                        .filter(TenderProject.id == project_id)
                        .first()
                    )
                    if project:
                        # 检查项目当前状态
                        current_status = project.status
                        self.logger.info(
                            f'检查项目 {project_id} 当前状态: {current_status}'
                        )

                        # 如果项目状态已经是completed，不需要再次更新
                        if current_status == 'completed':
                            self.logger.info(
                                f'项目 {project_id} 状态已经是completed，无需再次更新'
                            )
                            return

                        # 使用增强的状态管理器等待并更新状态
                        from modules.project_status_manager import ProjectStatusManager

                        status_manager = ProjectStatusManager(db_session=check_db)
                        # 增加重试机制以处理临时的数据库同步问题
                        max_retries = 3
                        for retry in range(max_retries):
                            try:
                                result = status_manager.wait_and_update_project_status_when_all_completed(
                                    project_id,
                                    max_wait_time=30,
                                    force_complete_after_timeout=True,
                                )
                                if result:
                                    break
                                elif retry < max_retries - 1:
                                    # 如果不是最后一次重试，等待一段时间后重试
                                    time.sleep(2)
                            except Exception as retry_e:
                                self.logger.warning(
                                    f'第{retry + 1}次尝试更新项目状态时出错: {retry_e}'
                                )
                                if retry < max_retries - 1:
                                    time.sleep(2)
                                else:
                                    raise
                finally:
                    check_db.close()
            except Exception as check_e:
                self.logger.error(f'延迟检查项目完成状态时出错: {check_e}')

        # 在后台线程中执行延迟检查
        check_thread = threading.Thread(target=delayed_check)
        check_thread.daemon = True
        check_thread.start()

    def _get_analysis_completion_stats(self, project_id: int) -> tuple:
        """
        获取项目分析完成情况的统计信息

        Args:
            project_id: 项目ID

        Returns:
            tuple: (已完成数量, 总数量)
        """
        try:
            # 获取项目下的所有投标文件
            bid_documents = []
            if self.db is not None:
                bid_documents = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.project_id == project_id)
                    .all()
                )

            if not bid_documents:
                self.logger.warning(f'项目 {project_id} 没有找到投标文件')
                return 0, 0

            # 统计完成和总数
            total_count = len(bid_documents)
            completed_count = 0
            processing_count = 0
            error_count = 0

            # 详细状态统计
            status_counts = {}

            for doc in bid_documents:
                status = doc.processing_status
                status_counts[status] = status_counts.get(status, 0) + 1

                if status == 'completed':
                    completed_count += 1
                elif status == 'processing':
                    processing_count += 1
                elif status == 'error':
                    error_count += 1

            # 记录详细的统计信息
            self.logger.info(
                f'项目 {project_id} 分析状态统计: 总数={total_count}, 已完成={completed_count}, '
                f'处理中={processing_count}, 错误={error_count}, 详细状态={status_counts}'
            )

            return completed_count, total_count

        except Exception as e:
            self.logger.error(f'获取分析完成统计时出错: {str(e)}')
            return 0, 0

    def _check_all_analysis_completed(self, project_id: int) -> bool:
        """
        检查项目中所有投标文件的分析是否都已完成

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否所有分析都已完成
        """
        try:
            self.logger.info(f'检查项目 {project_id} 的分析完成状态')

            # 获取完成统计
            completed_count, total_count = self._get_analysis_completion_stats(
                project_id
            )

            if total_count == 0:
                return False

            # 检查是否全部完成
            all_completed = completed_count == total_count

            if all_completed:
                self.logger.info(
                    f'项目 {project_id} 所有分析任务已完成 ({completed_count}/{total_count})'
                )
            else:
                self.logger.info(
                    f'项目 {project_id} 分析任务未全部完成 ({completed_count}/{total_count})'
                )

            return all_completed

        except Exception as e:
            self.logger.error(f'检查分析完成状态时出错: {str(e)}')
            return False

    def _update_project_status_when_all_completed(self, project_id: int):
        """
        当所有分析任务都完成时更新项目状态

        Args:
            project_id: 项目ID
        """
        try:
            self.logger.info(f'检查项目 {project_id} 是否所有任务都已完成')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return

            # 使用统一的项目状态管理器
            from modules.project_status_manager import ProjectStatusManager

            status_manager = ProjectStatusManager(db_session=self.db)
            status_manager.update_project_status_when_all_completed(project_id)

        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}')
            if self.db:
                self.db.rollback()
