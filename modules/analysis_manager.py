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
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import os
import threading
import glob
import datetime

from modules.database import TenderProject, BidDocument, AnalysisResult, ScoringRule

# 修正导入错误，使用正确的模块名
from modules.correct_scoring_extractor import CorrectScoringExtractor
from modules.scoring_rules_manager import ScoringRulesManager
from modules.price_score_calculator import PriceScoreCalculator
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.runtime_config import load_config, get_bool

# 创建一个线程池而不是进程池，避免并行PDF转换导致的问题
executor = ThreadPoolExecutor(max_workers=4)

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
        from modules.database import SessionLocal

        db = SessionLocal()
        bid_document = None  # 初始化bid_document变量
        try:
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

            # 在MD转换完成后首先解析投标人名称
            try:
                from modules.bidder_name_extractor import extract_bidder_name_from_file
                from modules.pdf_processor import PDFProcessor

                # 使用锁确保PDF转换不会并行执行
                with pdf_conversion_lock:
                    # 获取MD文件路径
                    pdf_processor = PDFProcessor(bid_file_path, file_type='bid')
                    md_file_path = pdf_processor.get_md_file_path()

                    # 优先从MD文件提取投标人名称
                    if os.path.exists(md_file_path):
                        extracted_name = extract_bidder_name_from_file(md_file_path)
                    else:
                        # 如果MD文件不存在，则处理PDF文件并提取
                        pdf_processor.process_pdf_to_md()
                        md_file_path = pdf_processor.get_md_file_path()
                        if os.path.exists(md_file_path):
                            extracted_name = extract_bidder_name_from_file(md_file_path)
                        else:
                            # 如果处理后仍然没有MD文件，则直接从PDF文件提取
                            extracted_name = extract_bidder_name_from_file(
                                bid_file_path
                            )

                # 初始化result_record变量
                result_record = None

                # 更新投标人名称
                # 确保提取到的名称有效
                valid_name = None
                if (
                    extracted_name
                    and extracted_name.strip()
                    and extracted_name != '未提取'
                    and len(extracted_name.strip()) > 1
                ):
                    valid_name = extracted_name.strip()

                # 如果未提取到有效名称，使用文件名作为备用
                if not valid_name:
                    filename = os.path.basename(bid_file_path)
                    bidder_name = os.path.splitext(filename)[0]
                    # 确保投标人名称不为空
                    if not bidder_name or not bidder_name.strip():
                        bidder_name = '未知投标方'
                    valid_name = bidder_name
                    self.logger.warning(
                        f'未提取到投标人名称，使用文件名作为备用: {bidder_name}'
                    )

                # 更新数据库中的投标人名称
                setattr(bid_document, 'bidder_name', valid_name)
                # 同时更新分析结果中的投标人名称
                result_record = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_document_id)
                    .first()
                )
                if result_record:
                    setattr(result_record, 'bidder_name', valid_name)
                # 确保提交数据库更改
                try:
                    db.commit()
                    self.logger.info(f'成功更新数据库中的投标人名称: {valid_name}')
                except Exception as commit_e:
                    self.logger.error(f'提交数据库更改时出错: {commit_e}')
                    db.rollback()
                self.logger.info(f'设置投标人名称: {valid_name}')
            except Exception as e:
                self.logger.warning(f'提取投标人名称时出错: {e}')
                # 出错时使用文件名作为备用
                try:
                    filename = os.path.basename(bid_file_path)
                    bidder_name = os.path.splitext(filename)[0]
                    # 确保投标人名称不为空
                    if not bidder_name or not bidder_name.strip():
                        bidder_name = '未知投标方'
                    setattr(bid_document, 'bidder_name', str(bidder_name))
                    result_record = (
                        db.query(AnalysisResult)
                        .filter(AnalysisResult.bid_document_id == bid_document_id)
                        .first()
                    )
                    if result_record:
                        setattr(result_record, 'bidder_name', str(bidder_name))
                    # 确保提交数据库更改
                    try:
                        db.commit()
                        self.logger.info(
                            f'成功更新数据库中的投标人名称（备用）: {bidder_name}'
                        )
                    except Exception as commit_e:
                        self.logger.error(f'提交数据库更改时出错: {commit_e}')
                        db.rollback()
                    self.logger.warning(
                        f'提取投标人名称出错，使用文件名作为备用: {bidder_name}'
                    )
                except Exception as fallback_e:
                    self.logger.error(f'设置备用投标人名称时出错: {fallback_e}')
                    # 最后的兜底方案
                    setattr(bid_document, 'bidder_name', '未知投标方')
                    if result_record is not None:
                        setattr(result_record, 'bidder_name', '未知投标方')
                    # 确保提交数据库更改
                    try:
                        db.commit()
                        self.logger.info(
                            '成功更新数据库中的投标人名称（兜底方案）: 未知投标方'
                        )
                    except Exception as commit_e:
                        self.logger.error(f'提交数据库更改时出错: {commit_e}')
                        db.rollback()
            # 注意：这里需要正确结束try-except块，确保下面的代码不在异常处理范围内

            # 创建智能投标分析器，传递投标人名称
            analyzer = IntelligentBidAnalyzer(
                tender_file_path, bid_file_path, db, bid_document_id, project_id
            )
            # 确保分析器中的投标人名称与数据库中的保持一致
            # 修复：如果数据库中的投标人名称为空，则使用分析器初始化时设置的文件名默认值
            if str(bid_document.bidder_name) and str(bid_document.bidder_name).strip():
                # 数据库中有有效的投标人名称，使用数据库中的值
                analyzer.bidder_name = bid_document.bidder_name
            else:
                # 数据库中没有有效的投标人名称，使用分析器中的默认值（文件名）
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
                    if (
                        '投标人名称' in details
                        and isinstance(details, dict)
                        and details.get('投标人名称') != '未提取'
                        and str(details.get('投标人名称')).strip()
                    ):
                        # 只有当AI提取到有效名称时才更新
                        valid_extracted_name = str(
                            details.get('投标人名称', '')
                        ).strip()
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
                        try:
                            # 尝试保存投标总价到数据库
                            price_str = str(details.get('投标总价', ''))
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
                                f'无法解析投标总价: {details.get("投标总价", "")}, 错误: {e}'
                            )

                    # 保存分析结果到数据库
                    try:
                        # 更新分析结果记录
                        setattr(
                            result_record,
                            'total_score',
                            float(analysis_result.get('total_score', 0)),
                        )
                        setattr(
                            result_record, 'price_score', float(0)
                        )  # 价格分将在后续计算
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
                            analysis_result.get('detailed_scores', {}),
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
                            datetime.datetime.utcnow(),
                        )
                        setattr(result_record, 'last_modified_by', 'system')

                        # 如果还没有设置投标人名称，则使用bid_document中的名称
                        current_bidder_name = getattr(result_record, 'bidder_name', '')
                        if (
                            not current_bidder_name
                            or not str(current_bidder_name).strip()
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
                            price_score=float(0),  # 价格分将在后续计算
                            extracted_price=analysis_result.get('extracted_price'),
                            detailed_scores=analysis_result.get('detailed_scores', {}),
                            analysis_summary=str(
                                analysis_result.get('analysis_summary', '')
                            ),
                            ai_model=str(analysis_result.get('ai_model', '')),
                            original_scores=analysis_result.get('detailed_scores', {}),
                            last_modified_at=datetime.datetime.utcnow(),
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

        # 首先提取评分规则并保存到数据库
        if not self.initialize_project_analysis(project_id):
            self.logger.error(f'项目 {project_id} 评分规则初始化失败')

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

        # 为每个投标文件创建分析任务，但使用串行方式处理PDF转换以避免垃圾信息
        for bid_info in bid_files_info:
            try:
                self.analysis_task(
                    project_id,
                    bid_info['id'],
                    str(tender_file_path),
                    bid_info['bid_file_path'],  # 修复键名
                )
            except Exception as e:
                self.logger.error(
                    f'为投标文件 {bid_info["id"]} 创建分析任务时出错: {e}'
                )

        # 确保所有分析任务完成后，再计算价格分
        self.logger.info(f'等待所有分析任务完成后再计算项目 {project_id} 的价格分。')

        # 添加一个小的延迟确保数据库操作完成
        import time

        time.sleep(1)

        # 计算价格分
        try:
            self.logger.info(f'开始为项目 {project_id} 计算价格分。')
            calculator = PriceScoreCalculator(db_session=self.db)
            price_scores_result = calculator.calculate_project_price_scores(project_id)

            if price_scores_result:
                # 重新获取分析结果以计算更新了多少个投标人
                analysis_results = []
                if self.db is not None:
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
                # 记录详细信息以便调试
                self._log_price_calculation_failure_details(project_id)

            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            if project is not None:
                has_errors = False
                if self.db is not None:
                    has_errors = (
                        self.db.query(BidDocument)
                        .filter(
                            BidDocument.project_id == project_id,
                            BidDocument.processing_status == 'error',
                        )
                        .count()
                        > 0
                    )

                if project is not None:
                    setattr(
                        project,
                        'status',
                        'completed_with_errors' if has_errors else 'completed',
                    )
                # 设置分析结束时间
                from datetime import datetime

                project.analysis_end_time = datetime.utcnow()
                if self.db is not None:
                    self.db.commit()
                self.logger.info(
                    '项目 %s 的状态已更新为 %s。', project_id, project.status
                )

                # 检查是否需要清理MD文件
                self._cleanup_md_files(project_id)

        except Exception as e:
            self.logger.error(f'为项目 {project_id} 计算价格分时出错: {e}')
            self.logger.error(traceback.format_exc())
            # 即使价格分计算出错，也要更新项目状态
            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            if project is not None:
                if project is not None:
                    setattr(project, 'status', 'completed_with_errors')
                from datetime import datetime

                project.analysis_end_time = datetime.utcnow()
                if self.db is not None:
                    self.db.commit()

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
