#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:46:24
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-08 10:15:50
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
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import os
import threading
import glob
import datetime

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
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.runtime_config import load_config, get_bool

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
        from models.database import SessionLocal

        db = SessionLocal()
        bid_document = None  # 初始化bid_document变量
        try:
            # 检查触发条件
            # 1. 价格分数计算子流程状态标记为"completed"
            # 2. 投标文件状态更新为"processing"
            # 3. 项目ID、投标文件ID、招标文件路径和投标文件路径都必须提供
            # 4. 投标文件记录必须存在于数据库中

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

            # 检查投标文件状态是否为processing
            if bid_document.processing_status != 'processing':
                self.logger.error(
                    f'分析任务触发条件不满足：投标文件状态不是processing，当前状态为{bid_document.processing_status}'
                )
                return

            # 检查项目状态是否为"analyzing"或"completed"
            # 如果项目状态是"analyzing"，说明我们是在run_analysis_and_calculate_prices中调用的
            # 如果项目状态是"completed"，说明是其他地方调用的
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if not project:
                self.logger.error(f'未找到项目: {project_id}')
                return

            # 检查项目状态是否为"analyzing"或"completed"
            # 修复：允许在"analyzing"状态下启动分析任务
            if project.status not in ['analyzing', 'completed']:
                self.logger.error(
                    f'分析任务触发条件不满足：项目状态不是"analyzing"或"completed"，当前状态为{project.status}'
                )
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
            analyzer = IntelligentBidAnalyzer(
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
                        # 更新分析结果记录
                        setattr(
                            result_record,
                            'total_score',
                            float(analysis_result.get('total_score', 0)),
                        )
                        # 只有当analysis_result中包含price_score时才更新，否则保持数据库中的现有值
                        if 'price_score' in analysis_result:
                            setattr(
                                result_record,
                                'price_score',
                                float(analysis_result.get('price_score', 0)),
                            )
                        # 价格分将在后续计算，此处不再强制设置为0
                        extracted_price = analysis_result.get('extracted_price')
                        if extracted_price is not None:
                            setattr(
                                result_record, 'extracted_price', float(extracted_price)
                            )
                        else:
                            setattr(result_record, 'extracted_price', None)
                        setattr(
                            result_record,
                            'detailed_scores',
                            analysis_result.get('detailed_scores', []),
                        )
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
                        setattr(
                            result_record,
                            'original_scores',
                            analysis_result.get('detailed_scores', {}),
                        )
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
                    except Exception as e:
                        self.logger.error(f'保存分析结果到数据库时出错: {e}')
                        db.rollback()
                else:
                    # 如果没有找到分析结果记录，则创建新的记录
                    try:
                        new_result_record = AnalysisResult(
                            project_id=project_id,
                            bid_document_id=bid_document_id,
                            bidder_name=str(bid_document.bidder_name),
                            total_score=float(analysis_result.get('total_score', 0)),
                            # 只有当analysis_result中包含price_score时才设置，否则使用默认值0.0
                            price_score=float(
                                analysis_result.get('price_score', 0.0)
                            ),  # 价格分将在后续计算
                            extracted_price=analysis_result.get('extracted_price'),
                            detailed_scores=analysis_result.get('detailed_scores', []),
                            analysis_summary=str(
                                analysis_result.get('analysis_summary', '')
                            ),
                            ai_model=str(analysis_result.get('ai_model', '')),
                            original_scores=analysis_result.get('detailed_scores', {}),
                            last_modified_at=datetime.datetime.now(),
                            last_modified_by='system',
                            dynamic_scores={},
                        )
                        db.add(new_result_record)
                        db.commit()
                        self.logger.info(
                            f'成功创建新的分析结果记录: {bid_document.bidder_name}'
                        )
                    except Exception as e:
                        self.logger.error(f'创建新的分析结果记录时出错: {e}')
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

                # 检查是否所有分析任务都已完成，如果完成则更新项目状态
                try:
                    # 创建一个新的数据库会话来检查项目状态
                    from models.database import SessionLocal

                    check_db = SessionLocal()
                    try:
                        # 检查项目是否仍然存在
                        project = (
                            check_db.query(TenderProject)
                            .filter(TenderProject.id == project_id)
                            .first()
                        )
                        if project:
                            # 创建一个新的分析管理器实例来检查状态
                            check_manager = AnalysisManager(db_session=check_db)
                            check_manager._update_project_status_when_all_completed(
                                project_id
                            )
                    finally:
                        check_db.close()
                except Exception as check_e:
                    self.logger.error(f'检查项目完成状态时出错: {check_e}')
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
            auto_delete = get_bool(runtime_config, 'auto_delete_md_files', False)

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
                    'temp/md',
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
                        'temp/md',
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

        # 首先执行价格计算工作流
        self.logger.info(f'开始执行项目 {project_id} 的价格计算工作流')
        from modules.price_calculation_workflow import PriceCalculationWorkflow

        # 确保数据库会话存在
        if self.db is None:
            self.logger.error('数据库会话未提供')
            return

        # 创建价格计算工作流实例
        price_workflow = PriceCalculationWorkflow(db_session=self.db)

        # 执行价格计算工作流
        success = price_workflow.execute_workflow(project_id)

        if success:
            self.logger.info(f'项目 {project_id} 价格计算工作流执行成功')
            # 价格计算成功后，更新所有投标文件状态为processing
            # 因为接下来要启动规则分析流程
            if self.db is not None:
                bid_documents = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.project_id == project_id)
                    .all()
                )
                for bid_doc in bid_documents:
                    bid_doc.processing_status = 'processing'
                self.db.commit()
                self.logger.info(
                    f'已将项目 {project_id} 的所有投标文件状态更新为processing'
                )

            # 再为每个投标文件创建分析任务
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

            # 注意：不要在这里调用 _update_project_status_when_all_completed
            # 该方法应该在分析任务完成后调用（在analysis_task方法内部已完成）
        else:
            self.logger.error(f'项目 {project_id} 价格计算工作流执行失败')

        # 检查是否需要清理MD文件
        self._cleanup_md_files(project_id)

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
                f'项目 {project_id} 价格提取检查完成: {valid_results_count}/{len(analysis_results)} 个投标人价格提取成功'
            )

            return all_prices_extracted and valid_results_count == len(analysis_results)

        except Exception as e:
            self.logger.error(f'检查价格提取状态时出错: {e}')
            return False

    def _check_all_analysis_completed(self, project_id: int):
        """
        检查项目中所有分析任务是否都已完成

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否所有分析任务都已完成
        """
        try:
            self.logger.info(f'检查项目 {project_id} 的所有分析任务完成状态')

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
                return False

            # 检查每个投标文件的分析状态
            all_analysis_completed = True
            completed_count = 0

            for bid_doc in bid_documents:
                bidder_name = bid_doc.bidder_name or f'未知投标人_{bid_doc.id}'
                processing_status = bid_doc.processing_status

                self.logger.info(
                    f'投标人 [{bidder_name}] 处理状态: {processing_status}'
                )

                # 检查处理状态是否为completed
                if processing_status != 'completed':
                    self.logger.warning(
                        f'投标人 [{bidder_name}] 的分析任务未完成，当前状态为 {processing_status}'
                    )
                    all_analysis_completed = False
                else:
                    completed_count += 1

            self.logger.info(
                f'项目 {project_id} 分析任务检查完成: {completed_count}/{len(bid_documents)} 个投标文件分析完成'
            )

            return all_analysis_completed and completed_count == len(bid_documents)

        except Exception as e:
            self.logger.error(f'检查分析任务完成状态时出错: {e}')
            return False

    def _update_project_status_when_all_completed(self, project_id: int):
        """
        当所有分析任务完成时更新项目状态

        Args:
            project_id: 项目ID
        """
        try:
            from models.database import TenderProject

            # 检查所有分析任务是否完成
            if not self._check_all_analysis_completed(project_id):
                self.logger.warning(
                    f'项目 {project_id} 的分析任务尚未全部完成，暂不更新项目状态'
                )
                return False

            # 不再检查价格提取状态，因为价格分计算应该在价格计算工作流中完成
            # 项目状态更新应该只依赖于分析任务的完成状态

            # 所有任务都完成，更新项目状态
            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )

            if project:
                setattr(project, 'status', 'completed')
                project.analysis_end_time = datetime.datetime.now()
                if self.db is not None:
                    self.db.commit()
                self.logger.info(f'项目 {project_id} 状态已更新为 completed')
                return True
            else:
                self.logger.error(f'未找到项目 {project_id}')
                return False

        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}')
            if self.db is not None:
                try:
                    self.db.rollback()
                except Exception as rollback_e:
                    self.logger.error(f'数据库回滚时出错: {rollback_e}')
            return False
