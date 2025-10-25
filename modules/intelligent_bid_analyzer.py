#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
智能投标分析器模块
负责分析投标文件并生成评分
"""

import json
import re
import logging
import traceback
import os
from typing import List, Dict, Any, Optional
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.pdf_processor import PDFProcessor
from models.database import BidDocument, ScoringRule, AnalysisResult
from modules.bid_analyzer_helpers import BidAnalyzerHelpers


class IntelligentBidAnalyzer(BidAnalyzerHelpers):
    def __init__(
        self,
        tender_file_path: str,
        bid_file_path: str,
        db_session=None,
        bid_document_id=None,
        project_id=None,
        extracted_text: Optional[List[str]] = None,
    ):
        super().__init__()
        self.tender_file_path = tender_file_path
        self.bid_file_path = bid_file_path
        self.db = db_session
        self.bid_document_id = bid_document_id
        self.project_id = project_id
        self.ai_analyzer = LocalAIAnalyzer()
        # 移除价格管理器，价格提取将在统一流程中处理
        # self.price_manager = PriceManager()
        self.logger = logging.getLogger(__name__)
        self.total_rules_to_analyze = 0  # 初始化实例变量

        if self.db is not None and self.bid_document_id is not None:
            try:
                bid_doc = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                # 修复：确保即使数据库中没有投标人名称，也使用文件名作为默认值
                if bid_doc and bid_doc.bidder_name and bid_doc.bidder_name.strip():
                    self.bidder_name = bid_doc.bidder_name
                else:
                    # 使用文件名作为默认投标人名称
                    filename = os.path.basename(self.bid_file_path)
                    self.bidder_name = os.path.splitext(filename)[0]
            except Exception as e:
                self.logger.warning(f'初始化时获取投标人名称出错: {e}')
                # 出错时使用文件名作为默认投标人名称
                filename = os.path.basename(self.bid_file_path)
                self.bidder_name = os.path.splitext(filename)[0]
        else:
            # 没有数据库会话时也使用文件名作为默认投标人名称
            filename = os.path.basename(self.bid_file_path)
            self.bidder_name = os.path.splitext(filename)[0]

        # 优化：如果已提供提取好的文本，则直接使用
        if extracted_text is not None:
            self.bid_pages = extracted_text
            self.bid_processor = None  # 不需要再创建PDF处理器
            self.logger.info(
                f'IntelligentBidAnalyzer initialized with pre-extracted text for {self.bid_file_path}.'
            )
        else:
            # 保持旧的兼容性，如果未提供文本，则初始化处理器以便后续提取
            self.logger.warning(
                f'No pre-extracted text provided for {self.bid_file_path}. PDFProcessor will be used.'
            )
            self.bid_processor = PDFProcessor(
                self.bid_file_path, file_type='bid'
            )  # 使用新的PDF处理器，指定为投标文件类型
            self.bid_pages = None

    def _update_progress(self, completed, total, current_rule, partial_results=None):
        if not (self.db is not None and self.bid_document_id is not None):
            return
        try:
            bid_doc = (
                self.db.query(BidDocument)
                .filter(BidDocument.id == self.bid_document_id)
                .first()
            )
            if bid_doc:
                bid_doc.progress_total_rules = total
                bid_doc.progress_completed_rules = completed
                # 修复：确保投标人名称不为空时才使用，否则使用文件名
                if self.bidder_name and self.bidder_name.strip():
                    progress_info = f'{self.bidder_name} - {current_rule}'
                else:
                    # 从文件路径提取文件名作为备用
                    filename = os.path.basename(self.bid_file_path)
                    bidder_name = os.path.splitext(filename)[0]
                    progress_info = f'{bidder_name} - {current_rule}'
                bid_doc.progress_current_rule = progress_info[:100]
                bid_doc.detailed_progress_info = progress_info
                if partial_results is not None:
                    # 确保只保存最新的几个结果，避免数据过大
                    bid_doc.partial_analysis_results = json.dumps(
                        partial_results[-5:], ensure_ascii=False
                    )
                # 更新处理阶段为"AI分析中"
                bid_doc.processing_phase = 'AI分析中'
                self.db.commit()
                self.logger.info(f'进度更新: {completed}/{total} - {progress_info}')
        except Exception as e:
            self.logger.error(f'更新进度时出错: {e}')
            self.db.rollback()

    def _build_rules_tree_from_db(
        self, rules_from_db: List[Any]
    ) -> List[Dict[str, Any]]:
        """将从数据库获取的扁平化评分规则列表转换为树形结构。"""
        # 修复：正确构建树形结构，包含所有子项规则
        rule_map = {}
        for rule in rules_from_db:
            # 只处理有Child_Item_Name的子项规则
            if rule.Child_Item_Name is not None and rule.Child_Item_Name.strip():
                rule_map[rule.id] = {
                    'id': rule.id,
                    'criteria_name': rule.Child_Item_Name,
                    'max_score': rule.Child_max_score,
                    'description': rule.description,
                    'is_price_criteria': rule.is_price_criteria,
                    'is_veto': rule.is_veto,
                    'is_qualitative': rule.is_qualitative,
                    'is_quantitative': rule.is_quantitative,
                    'needs_comprehensive_analysis': getattr(
                        rule, 'needs_comprehensive_analysis', False
                    ),  # 添加综合分析标记
                    'parent_id': None,  # 简化处理
                    'children': [],
                }

        # 转换为列表格式
        tree = list(rule_map.values())
        return tree

    def _get_bid_pages(self) -> List[str]:
        """获取投标文件页面内容，优先使用已加载的文本。"""
        # 如果文本已在初始化时提供，直接返回
        if self.bid_pages is not None:
            return self.bid_pages

        # 作为后备方案，如果文本未提供，则调用PDF处理器
        if self.bid_processor:
            self.logger.info(
                f'No pre-extracted text found, processing PDF for {self.bid_file_path} on demand.'
            )
            # 不再在这里处理PDF，因为已经在analysis_manager中处理过了
            # 直接从PDF处理器加载内容
            pages_content = self.bid_processor.load_content_from_md_file()
            if pages_content is not None:
                self.bid_pages = pages_content
            else:
                # 如果从MD文件加载失败，则使用extract_text_per_page方法
                self.bid_pages = self.bid_processor.extract_text_per_page()
            self._save_failed_pages_info(
                self.db, self.bid_document_id, self.bid_processor
            )
            return self.bid_pages

        # 如果既没有预提取的文本，也没有处理器，则返回错误
        self.logger.error(
            f'Cannot get bid pages: No pre-extracted text and no PDF processor available for {self.bid_file_path}.'
        )
        return []

    def _get_md_file_path(self) -> Optional[str]:
        """
        获取投标文件对应的MD文件路径
        MD文件存放在temp_md目录下，文件名基于PDF文件名生成
        """
        if not self.bid_file_path:
            return None

        # 生成MD文件路径
        pdf_filename = os.path.basename(self.bid_file_path)
        file_key = os.path.splitext(pdf_filename)[0]
        md_filename = f'{file_key}.md'

        # MD文件存放在output目录下
        md_file_path = os.path.join('output', md_filename)

        # 检查文件是否存在
        if os.path.exists(md_file_path):
            return md_file_path
        else:
            self.logger.warning(f'MD文件不存在: {md_file_path}')
            return None

    def _load_content_from_md_file(self, md_file_path: str) -> Optional[List[str]]:
        """
        从MD文件中加载内容并转换为页面列表格式
        """
        try:
            if not md_file_path or not os.path.exists(md_file_path):
                self.logger.warning(f'MD文件不存在或路径无效: {md_file_path}')
                return None

            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按页面分隔符分割内容
            pages = content.split('\n\n---\n\n')
            self.logger.info(f'从MD文件 {md_file_path} 加载了 {len(pages)} 页内容')
            return pages
        except Exception as e:
            self.logger.error(f'从MD文件加载内容时出错: {e}')
            return None

    def analyze_rule_parallel(self, rule, bid_pages):
        """并行分析单个评分规则"""
        try:
            self.logger.info(
                f'正在为投标人 {self.bidder_name} 分析子项规则: {rule.Child_Item_Name}'
            )

            # 查找相关上下文（使用从MD文件读取的内容）
            relevant_context = self._find_relevant_context_for_child_rule(
                rule, bid_pages
            )

            # 创建prompt
            prompt = self._create_prompt_for_child_rule(rule, relevant_context)

            # 记录发送给AI的prompt
            self.logger.info(
                f"--- Prompt for rule '{rule.Child_Item_Name}' ---\n{prompt}\n--- End of Prompt ---"
            )

            # 提交AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)
            if 'Error:' in ai_response:
                self.logger.error(
                    f"AI analysis failed for rule '{rule.Child_Item_Name}': {ai_response}"
                )
                score, reason = 0, f'AI分析失败: {ai_response}'
            else:
                score, reason = self._parse_ai_score_response(
                    ai_response, rule.Child_max_score
                )

            # 返回分析结果
            return {
                'Child_Item_Name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'score': score,
                'reason': reason,
                'Parent_Item_Name': rule.Parent_Item_Name,
                'is_qualitative': rule.is_qualitative,
                'is_quantitative': rule.is_quantitative,
                'is_veto': rule.is_veto,
                'needs_comprehensive_analysis': getattr(
                    rule, 'needs_comprehensive_analysis', False
                ),  # 添加综合分析标记
            }
        except Exception as e:
            self.logger.error(f'分析规则 {rule.Child_Item_Name} 时出错: {e}')
            return {
                'Child_Item_Name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'score': 0,
                'reason': f'分析失败: {str(e)}',
                'Parent_Item_Name': rule.Parent_Item_Name,
                'is_qualitative': rule.is_qualitative,
                'is_quantitative': rule.is_quantitative,
                'is_veto': rule.is_veto,
                'needs_comprehensive_analysis': getattr(
                    rule, 'needs_comprehensive_analysis', False
                ),  # 添加综合分析标记
            }

    def analyze_bidding_document(self):
        """
        分析投标文件并生成评分，包含质量评估和重新转换逻辑
        """
        try:
            self.logger.info(f'开始分析投标文件: {self.bid_file_path}')

            # 初始化变量
            analyzed_scores = []  # 存储分析结果
            analyzed_scores_for_progress = []  # 为进度更新创建一个单独的列表
            qualitative_results = {}  # 存储定性规则分析结果
            quantitative_results = {}  # 存储定量规则分析结果
            failed_veto_items = {}  # 存储未通过的否决项

            # 记录投标人名称信息
            bidder_name_display = (
                self.bidder_name
                if self.bidder_name and self.bidder_name.strip()
                else os.path.splitext(os.path.basename(self.bid_file_path))[0]
            )
            self.logger.info(f'当前投标人名称: {self.bidder_name}')

            # 获取投标文档记录
            bid_document = None
            if self.db is not None and self.bid_document_id is not None:
                try:
                    bid_document = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_document:
                        # 检查OCR重试次数
                        # 确保投标人名称不为空时才使用，否则使用文件名
                        bidder_name_display = (
                            self.bidder_name
                            if self.bidder_name and self.bidder_name.strip()
                            else os.path.splitext(os.path.basename(self.bid_file_path))[
                                0
                            ]
                        )
                        if bid_document.ocr_retry_count >= 3:
                            self.logger.warning(
                                f'投标人 {bidder_name_display} OCR重试次数已达上限(3次)'
                            )
                            return {
                                'status': 'error',
                                'message': f'投标人 {bidder_name_display} 的PDF文件经过3次OCR重试仍无法满足质量要求',
                            }
                except Exception as e:
                    self.logger.warning(f'获取投标文档记录时出错: {e}')
                    bid_document = None
            else:
                bid_document = None

            # 1. 从数据库加载评分规则
            self.logger.info(f'正在为项目 {self.project_id} 从数据库加载评分规则...')
            if not self.db or not self.project_id:
                return {'error': '数据库会话或项目ID未提供，无法加载评分规则。'}

            try:
                rules_from_db = (
                    self.db.query(ScoringRule)
                    .filter(ScoringRule.project_id == self.project_id)
                    .all()
                )
            except Exception as e:
                self.logger.error(f'从数据库加载评分规则时出错: {e}')
                return {'error': f'从数据库加载评分规则时出错: {str(e)}'}

            if not rules_from_db:
                return {'error': f'项目 {self.project_id} 在数据库中没有找到评分规则。'}

            # 修复：直接使用数据库中的规则，不需要转换为树形结构
            self.logger.info(f'成功从数据库加载了 {len(rules_from_db)} 条评分规则。')

            # 2. 提取投标文件内容（优先从MD文件读取）
            bid_pages = None

            # 首先尝试从MD文件读取内容
            md_file_path = self._get_md_file_path()
            if md_file_path:
                bid_pages = self._load_content_from_md_file(md_file_path)

            # 如果MD文件读取失败，则从PDF处理结果获取
            if not bid_pages or not any(bid_pages):
                self.logger.info('从MD文件读取内容失败，回退到PDF处理结果')
                # 更新处理阶段为"PDF处理中"
                if self.db and self.bid_document_id:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.processing_phase = 'PDF处理中'
                        self.db.commit()
                # 不再在这里处理PDF，因为已经在analysis_manager中处理过了
                # 直接从PDF处理器加载内容
                bid_pages = self._get_bid_pages()

            if not bid_pages or not any(bid_pages):
                return {'error': '从投标文件中提取有效文本失败。'}

            # 3. 确保投标人名称已正确设置
            # 从数据库中获取最新的投标人名称
            if self.db and self.bid_document_id:
                bid_doc = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_doc and bid_doc.bidder_name:
                    self.bidder_name = bid_doc.bidder_name
                    bidder_name_display = bid_doc.bidder_name
                    self.logger.info(f'使用数据库中的投标人名称: {self.bidder_name}')

            # 4. 首先检查否决项
            self.logger.info('开始检查否决项...')
            veto_rules = [
                rule
                for rule in rules_from_db
                if rule.is_veto
                and rule.Child_Item_Name is not None
                and rule.Child_Item_Name.strip()
            ]

            veto_passed = True
            for rule in veto_rules:
                try:
                    result = self.analyze_rule_parallel(rule, bid_pages)
                    # 检查否决项是否通过（得分大于0表示通过）
                    if result['score'] <= 0:
                        veto_passed = False
                        failed_veto_items[rule.Child_Item_Name] = result
                        self.logger.warning(
                            f'投标人 {self.bidder_name} 未通过否决项: {rule.Child_Item_Name}'
                        )

                        # 如果有任何否决项未通过，直接判定该投标方不合格
                        self.logger.error(
                            f'投标人 {self.bidder_name} 因未通过否决项而不合格'
                        )

                        # 更新分析结果记录
                        if self.db and self.bid_document_id:
                            analysis_result = (
                                self.db.query(AnalysisResult)
                                .filter(
                                    AnalysisResult.bid_document_id
                                    == self.bid_document_id
                                )
                                .first()
                            )
                            if analysis_result:
                                # 标记否决项检查已完成且未通过
                                analysis_result.veto_items_checked = True
                                analysis_result.veto_items_passed = False
                                analysis_result.failed_veto_items = failed_veto_items
                                # 设置总分为0
                                analysis_result.total_score = 0
                                analysis_result.price_score = 0
                                # 保存定性规则和定量规则分析结果
                                analysis_result.qualitative_analysis_results = {}
                                analysis_result.quantitative_analysis_results = {}
                                self.db.commit()
                                self.logger.info(
                                    f'已更新分析结果记录，标记投标人 {self.bidder_name} 不合格'
                                )

                        # 返回不合格结果
                        return {
                            'status': 'veto_failed',
                            'message': f'投标人 {self.bidder_name} 未通过否决项检查',
                            'failed_veto_items': failed_veto_items,
                        }
                    else:
                        # 否决项通过，记录结果
                        analyzed_scores.append(result)
                        analyzed_scores_for_progress.append(result)
                        self.logger.info(
                            f'投标人 {self.bidder_name} 通过否决项: {rule.Child_Item_Name}'
                        )
                except Exception as e:
                    self.logger.error(f'检查否决项 {rule.Child_Item_Name} 时出错: {e}')
                    # 如果检查否决项出错，继续检查其他否决项

            # 如果所有否决项都通过，继续分析其他规则
            self.logger.info(f'投标人 {self.bidder_name} 通过所有否决项检查')

            # 5. 执行AI分析 - 分别处理定性规则和定量规则
            # 获取所有定量规则（有分数的规则）
            quantitative_rules = [
                rule
                for rule in rules_from_db
                if not rule.is_price_criteria
                and rule.Child_Item_Name is not None
                and rule.Child_Item_Name.strip()
                and rule.is_quantitative  # 使用is_quantitative字段而不是分数来判断
            ]

            # 获取所有定性规则（没有分数的规则）
            qualitative_rules = [
                rule
                for rule in rules_from_db
                if not rule.is_price_criteria
                and rule.Child_Item_Name is not None
                and rule.Child_Item_Name.strip()
                and rule.is_qualitative  # 使用is_qualitative字段而不是分数来判断
            ]

            # 分离需要综合分析的规则
            regular_quantitative_rules = [
                rule
                for rule in quantitative_rules
                if not getattr(rule, 'needs_comprehensive_analysis', False)
            ]

            comprehensive_analysis_rules = [
                rule
                for rule in quantitative_rules
                if getattr(rule, 'needs_comprehensive_analysis', False)
            ]

            self.progress_counter = 0
            self.total_rules_to_analyze = (
                len(regular_quantitative_rules) + len(comprehensive_analysis_rules) + 1
            )  # 定性规则作为一个整体
            self._update_progress(
                0,
                self.total_rules_to_analyze,
                f'[{bidder_name_display}] 初始化分析...',
                [],
            )

            # 先分析普通定量规则
            completed_count = 0
            for rule in regular_quantitative_rules:
                try:
                    result = self.analyze_rule_parallel(rule, bid_pages)
                    self.logger.info(
                        f"定量规则分析结果 - '{rule.Child_Item_Name}': "
                        f'得分 {result.get("score", 0)}/{result.get("max_score", 0)}, '
                        f'原因: {result.get("reason", "N/A")}'
                    )
                    analyzed_scores.append(result)
                    analyzed_scores_for_progress.append(result)
                    # 存储定量规则分析结果
                    quantitative_results[rule.Child_Item_Name] = result

                    # 更新进度
                    completed_count += 1
                    current_rule_name = f'分析定量规则 {completed_count}/{len(regular_quantitative_rules)}: {rule.Child_Item_Name}'
                    self._update_progress(
                        completed_count,
                        self.total_rules_to_analyze,
                        current_rule_name,
                        analyzed_scores_for_progress,
                    )

                except Exception as e:
                    self.logger.error(
                        f'分析定量规则 {rule.Child_Item_Name} 时发生异常: {e}'
                    )
                    # 添加一个默认的失败结果
                    failed_result = {
                        'Child_Item_Name': rule.Child_Item_Name,
                        'max_score': rule.Child_max_score,
                        'score': 0,
                        'reason': f'分析失败: {str(e)}',
                        'Parent_Item_Name': rule.Parent_Item_Name,
                        'is_qualitative': False,  # 定量规则
                        'is_quantitative': True,  # 定量规则
                        'is_veto': rule.is_veto,
                        'needs_comprehensive_analysis': False,  # 普通定量规则
                    }
                    analyzed_scores.append(failed_result)
                    analyzed_scores_for_progress.append(failed_result)
                    quantitative_results[rule.Child_Item_Name] = failed_result

                    # 更新进度
                    completed_count += 1
                    current_rule_name = f'分析定量规则 {completed_count}/{len(regular_quantitative_rules)}: {rule.Child_Item_Name} (失败)'
                    self._update_progress(
                        completed_count,
                        self.total_rules_to_analyze,
                        current_rule_name,
                        analyzed_scores_for_progress,
                    )

            # 分析需要综合分析的规则（只返回预评价数据）
            for rule in comprehensive_analysis_rules:
                try:
                    result = self.analyze_rule_parallel(rule, bid_pages)
                    self.logger.info(
                        f"需要综合分析的规则预评价结果 - '{rule.Child_Item_Name}': "
                        f'预评分 {result.get("score", 0)}/{result.get("max_score", 0)}, '
                        f'原因: {result.get("reason", "N/A")}'
                    )
                    analyzed_scores.append(result)
                    analyzed_scores_for_progress.append(result)
                    # 存储定量规则分析结果
                    quantitative_results[rule.Child_Item_Name] = result

                    # 更新进度
                    completed_count += 1
                    current_rule_name = f'预评价综合分析规则 {completed_count - len(regular_quantitative_rules)}/{len(comprehensive_analysis_rules)}: {rule.Child_Item_Name}'
                    self._update_progress(
                        completed_count,
                        self.total_rules_to_analyze,
                        current_rule_name,
                        analyzed_scores_for_progress,
                    )

                except Exception as e:
                    self.logger.error(
                        f'预评价综合分析规则 {rule.Child_Item_Name} 时发生异常: {e}'
                    )
                    # 添加一个默认的失败结果
                    failed_result = {
                        'Child_Item_Name': rule.Child_Item_Name,
                        'max_score': rule.Child_max_score,
                        'score': 0,
                        'reason': f'预评价失败: {str(e)}',
                        'Parent_Item_Name': rule.Parent_Item_Name,
                        'is_qualitative': False,  # 定量规则
                        'is_quantitative': True,  # 定量规则
                        'is_veto': rule.is_veto,
                        'needs_comprehensive_analysis': True,  # 需要综合分析
                    }
                    analyzed_scores.append(failed_result)
                    analyzed_scores_for_progress.append(failed_result)
                    quantitative_results[rule.Child_Item_Name] = failed_result

                    # 更新进度
                    completed_count += 1
                    current_rule_name = f'预评价综合分析规则 {completed_count - len(regular_quantitative_rules)}/{len(comprehensive_analysis_rules)}: {rule.Child_Item_Name} (失败)'
                    self._update_progress(
                        completed_count,
                        self.total_rules_to_analyze,
                        current_rule_name,
                        analyzed_scores_for_progress,
                    )

            # 再分析定性规则（组合为一个prompt进行分析）
            if qualitative_rules:
                try:
                    # 组合所有定性规则为一个prompt进行分析
                    result = self.analyze_qualitative_rules_combined(
                        qualitative_rules, bid_pages
                    )
                    analyzed_scores.extend(result['detailed_scores'])
                    analyzed_scores_for_progress.extend(result['detailed_scores'])
                    # 存储定性规则分析结果
                    qualitative_results = result['qualitative_results']

                    # 更新进度
                    completed_count += 1
                    current_rule_name = '分析定性规则 (组合分析)'
                    self._update_progress(
                        completed_count,
                        self.total_rules_to_analyze,
                        current_rule_name,
                        analyzed_scores_for_progress,
                    )

                except Exception as e:
                    self.logger.error(f'分析定性规则组合时发生异常: {e}')
                    # 如果组合分析失败，回退到逐条分析
                    for rule in qualitative_rules:
                        try:
                            result = self.analyze_rule_parallel(rule, bid_pages)
                            analyzed_scores.append(result)
                            analyzed_scores_for_progress.append(result)
                            # 存储定性规则分析结果
                            qualitative_results[rule.Child_Item_Name] = result

                            # 更新进度
                            completed_count += 1
                            current_rule_name = f'分析定性规则 {completed_count - len(regular_quantitative_rules) - len(comprehensive_analysis_rules)}/{len(qualitative_rules)}: {rule.Child_Item_Name}'
                            self._update_progress(
                                completed_count,
                                self.total_rules_to_analyze,
                                current_rule_name,
                                analyzed_scores_for_progress,
                            )
                        except Exception as inner_e:
                            self.logger.error(
                                f'分析定性规则 {rule.Child_Item_Name} 时发生异常: {inner_e}'
                            )
                            # 添加一个默认的失败结果
                            failed_result = {
                                'Child_Item_Name': rule.Child_Item_Name,
                                'max_score': rule.Child_max_score,
                                'score': 0,
                                'reason': f'分析失败: {str(inner_e)}',
                                'Parent_Item_Name': rule.Parent_Item_Name,
                                'is_qualitative': True,  # 定性规则
                                'is_quantitative': False,  # 定性规则
                                'is_veto': rule.is_veto,
                                'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                            }
                            analyzed_scores.append(failed_result)
                            analyzed_scores_for_progress.append(failed_result)
                            qualitative_results[rule.Child_Item_Name] = failed_result

                            # 更新进度
                            completed_count += 1
                            current_rule_name = f'分析定性规则 {completed_count - len(regular_quantitative_rules) - len(comprehensive_analysis_rules)}/{len(qualitative_rules)}: {rule.Child_Item_Name} (失败)'
                            self._update_progress(
                                completed_count,
                                self.total_rules_to_analyze,
                                current_rule_name,
                                analyzed_scores_for_progress,
                            )

            # 6. 计算除价格外的总分
            other_scores_total = sum(item['score'] for item in analyzed_scores)

            # 检查是否所有分数都因AI错误而为零
            all_scores_zero = all(item['score'] == 0 for item in analyzed_scores)
            ai_errors_present = any(
                'AI分析失败' in item['reason'] for item in analyzed_scores
            )

            if (
                all_scores_zero
                and ai_errors_present
                and (regular_quantitative_rules or comprehensive_analysis_rules)
            ):
                error_message = '所有评分项的AI分析均失败，请检查AI模型是否正常运行。'
                self.logger.error(error_message)
                # 查找一个具体的错误来显示
                specific_error = next(
                    (
                        item['reason']
                        for item in analyzed_scores
                        if 'AI分析失败' in item['reason']
                    ),
                    '无特定错误信息',
                )
                return {
                    'status': 'error',
                    'message': f'{error_message} 具体错误: {specific_error}',
                }

            # 7. 计算总分（不包含价格分，价格分将在后续统一计算）
            total_score = other_scores_total

            self.logger.info(
                f"===== 标书 '{self.bidder_name}' 非价格项分析完成，总得分为: {total_score} ====="
            )

            # 记录子项分数总和，用于后续计算总分
            self.other_scores_total = other_scores_total
            self._update_progress(
                self.total_rules_to_analyze,
                self.total_rules_to_analyze,
                '分析完成',
                analyzed_scores_for_progress,
            )

            # 更新处理阶段为"分析完成"
            if self.db and self.bid_document_id:
                bid_document = (
                    self.db.query(BidDocument)
                    .filter(BidDocument.id == self.bid_document_id)
                    .first()
                )
                if bid_document:
                    bid_document.processing_phase = '分析完成'
                    self.db.commit()

            # 8. 准备并返回结果
            analysis_result = {
                'status': 'success',
                'total_score': total_score,
                'other_scores_total': other_scores_total,  # 添加子项分数总和
                'detailed_scores': analyzed_scores,  # 现在是列表格式
                'analysis_summary': '分析完成。',
                'ai_model': self.ai_analyzer.model,
                'qualitative_results': qualitative_results,  # 定性规则分析结果
                'quantitative_results': quantitative_results,  # 定量规则分析结果
                'veto_items_checked': True,  # 否决项已检查
                'veto_items_passed': True,  # 否决项通过
                'failed_veto_items': failed_veto_items,  # 未通过的否决项
                'comprehensive_analysis_rules': [
                    rule.Child_Item_Name for rule in comprehensive_analysis_rules
                ],  # 需要综合分析的规则列表
            }

            # 如果有数据库会话，更新分析结果记录
            if self.db and self.bid_document_id:
                result_record = (
                    self.db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == self.bid_document_id)
                    .first()
                )
                if result_record:
                    # 更新分析结果记录
                    result_record.qualitative_analysis_results = qualitative_results
                    result_record.quantitative_analysis_results = quantitative_results
                    result_record.veto_items_checked = True
                    result_record.veto_items_passed = True
                    result_record.failed_veto_items = failed_veto_items
                    self.db.commit()
                    self.logger.info('已更新分析结果记录的定性/定量规则分析结果')

            return analysis_result

        except Exception as e:
            self.logger.error(f'分析过程中发生意外错误: {e}')
            self.logger.error(traceback.format_exc())
            return {'status': 'error', 'message': f'分析过程中发生意外错误: {str(e)}'}

    def _find_relevant_context_for_child_rule(self, rule, pages, context_window=2):
        """为子项规则查找相关上下文"""
        keywords = set(
            re.split(r'\s|，|。', rule.Child_Item_Name + ' ' + (rule.description or ''))
        )
        keywords = {k for k in keywords if k and len(k) > 1}
        relevant_pages_indices = set()
        for i, page_text in enumerate(pages):
            if any(keyword.lower() in page_text.lower() for keyword in keywords):
                for j in range(i, min(i + context_window + 1, len(pages))):
                    relevant_pages_indices.add(j)
        if not relevant_pages_indices:
            return '\n'.join(pages[:3])
        sorted_indices = sorted(list(relevant_pages_indices))
        grouped_pages = []
        if not sorted_indices:
            return ''
        start = end = sorted_indices[0]
        for i in range(1, len(sorted_indices)):
            if sorted_indices[i] == end + 1:
                end = sorted_indices[i]
            else:
                grouped_pages.append((start, end))
                start = end = sorted_indices[i]
        grouped_pages.append((start, end))
        context_parts = [
            f'--- Pages {s + 1}-{e + 1} ---\n' + '\n'.join(pages[s : e + 1])
            for s, e in grouped_pages
        ]
        return '\n\n'.join(context_parts)

    def _create_prompt_for_child_rule(self, rule, context):
        """为子项规则创建AI分析prompt"""
        # 确保Child_Item_Name不为空
        child_item_name = rule.Child_Item_Name or '未知评分项'

        prompt = f"""你是一个专业的评标专家，请根据以下信息对投标文件进行评分：

【评分项名称】
{child_item_name}

【评分标准描述】
{rule.description or '无详细描述'}

【评分满分】
{rule.Child_max_score or 0}分

【投标文件相关内容】
{context}

【评分要求】
1. 请根据评分标准对投标文件相关内容进行评估
2. 给出具体的评分（0-{rule.Child_max_score or 0}分）和评分理由
3. 评分必须基于投标文件的实际内容，不能凭空猜测
4. 如果投标文件中没有相关内容，请给出0分并说明原因

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{"score": 得分, "reason": "评分理由"}}

示例：
{{"score": 8.5, "reason": "投标文件中提供了详细的技术方案，符合评分标准要求"}}
"""
        return prompt

    def _parse_ai_score_response(self, response, max_score):
        """解析AI返回的评分结果"""
        try:
            # 使用我们改进的JSON修复函数
            result = self._fix_and_parse_json_response(response)

            if isinstance(result, dict) and result:
                # 提取分数和理由
                score = float(result.get('score', 0))
                reason = str(result.get('reason', ''))

                # 确保分数在合理范围内
                if score < 0:
                    score = 0
                if score > max_score:
                    score = max_score

                return score, reason
            else:
                # 如果修复函数返回的不是字典或为空，返回默认值
                return 0, '解析AI响应失败'
        except Exception as e:
            self.logger.error(f'解析AI评分响应时出错: {e}')
            self.logger.error(f'原始响应: {response}')
            return 0, f'解析AI响应失败: {str(e)}'

    def _fix_and_parse_json_response(self, response):
        """
        修复并解析AI返回的JSON响应
        """
        try:
            import re
            import json

            # 首先尝试清理响应，移除可能的代码块标记
            cleaned_response = response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # 移除控制字符
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)

            # 使用正则表达式查找被大括号包围的JSON块
            # re.DOTALL 使得 '.' 可以匹配包括换行在内的任意字符
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 如果没有找到JSON块，直接使用清理后的响应
                json_str = cleaned_response

            # 尝试修复JSON格式问题
            # 1. 确保字符串以闭合的大括号结尾
            if not json_str.rstrip().endswith('}'):
                # 查找最后一个闭合的大括号的位置
                last_brace_pos = json_str.rfind('}')
                if last_brace_pos != -1:
                    # 在最后一个闭合大括号后添加缺失的闭合大括号
                    json_str = json_str[: last_brace_pos + 1] + '}'

            # 2. 确保所有引号都是成对出现的
            quote_count = json_str.count('"')
            if quote_count % 2 != 0:
                # 如果引号数量是奇数，尝试在末尾添加一个引号
                json_str = json_str.rstrip() + '"'

            # 3. 修复缺少逗号的问题 - 在 }" 和 " 之间添加逗号（如果它们在同一行）
            json_str = re.sub(r'(\}"\s*)\n\s*"', r'\1,\n"', json_str)

            # 4. 修复多余的逗号问题 - 移除对象或数组末尾的逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 5. 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON
            data = json.loads(json_str)
            return data
        except Exception as e:
            self.logger.error(f'修复JSON时出错: {e}')
            # 如果修复失败，尝试使用更简单的修复方法
            try:
                import re

                # 尝试提取所有的键值对
                # 处理定性规则
                qualitative_pattern = r'"([^"]+)"\s*:\s*\{[^}]*"result"\s*:\s*"([^"]*)"[^}]*"reason"\s*:\s*"([^"]*)"[^}]*\}'
                qualitative_matches = re.findall(
                    qualitative_pattern, response, re.DOTALL
                )

                # 处理定量规则
                quantitative_pattern = r'"([^"]+)"\s*:\s*\{[^}]*"score"\s*:\s*([0-9.]+)[^}]*"reason"\s*:\s*"([^"]*)"[^}]*\}'
                quantitative_matches = re.findall(
                    quantitative_pattern, response, re.DOTALL
                )

                result = {}
                # 处理定性规则匹配
                for match in qualitative_matches:
                    key, result_value, reason = match
                    result[key] = {'result': result_value, 'reason': reason}

                # 处理定量规则匹配
                for match in quantitative_matches:
                    key, score, reason = match
                    # 只有当键不存在时才添加，避免覆盖定性规则
                    if key not in result:
                        result[key] = {'score': float(score), 'reason': reason}

                if result:
                    return result
            except Exception as e2:
                self.logger.error(f'简单修复方法也失败了: {e2}')

            # 如果所有方法都失败，返回空字典
            return {}

    def _parse_combined_ai_response(self, response, rules):
        """解析组合AI返回的评分结果"""
        try:
            # 使用我们改进的JSON修复函数
            result = self._fix_and_parse_json_response(response)

            if isinstance(result, dict) and result:
                results = {}
                # 验证并处理每个规则的结果
                for rule in rules:
                    rule_name = rule.Child_Item_Name
                    if rule_name in result:
                        rule_data = result[rule_name]
                        # 对于定性规则，我们关注的是结果而不是分数
                        if 'result' in rule_data:
                            result_value = str(rule_data.get('result', '未知'))
                            reason = str(rule_data.get('reason', ''))
                            results[rule_name] = {
                                'result': result_value,
                                'reason': reason,
                            }
                        else:
                            # 如果没有result字段，可能是定量规则
                            score = float(rule_data.get('score', 0))
                            reason = str(rule_data.get('reason', ''))
                            results[rule_name] = {'score': score, 'reason': reason}
                    else:
                        # 如果没有返回该规则的结果，给出默认值
                        results[rule_name] = {'result': '未知', 'reason': '未分析'}

                return results
            else:
                # 如果修复函数返回的不是字典或为空，使用默认结果
                results = {}
                for rule in rules:
                    results[rule.Child_Item_Name] = {
                        'result': '未知',
                        'reason': '解析AI响应失败',
                    }
                return results
        except Exception as e:
            self.logger.error(f'解析组合AI评分响应时出错: {e}')
            self.logger.error(f'原始响应: {response}')
            # 返回默认结果
            results = {}
            for rule in rules:
                results[rule.Child_Item_Name] = {
                    'result': '未知',
                    'reason': f'解析AI响应失败: {str(e)}',
                }
            return results

    def _save_failed_pages_info(self, db, bid_document_id, bid_processor):
        """保存PDF处理失败的页面信息"""
        if not (db is not None and bid_document_id is not None):
            return
        try:
            bid_doc = (
                db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
            )
            if bid_doc and hasattr(bid_processor, 'failed_pages_info'):
                bid_doc.failed_pages_info = bid_processor.failed_pages_info
                db.commit()
        except Exception as e:
            self.logger.error(f'保存失败页面信息时出错: {e}')
            db.rollback()

    def _retry_ocr_conversion(self):
        """重新转换PDF文件（OCR重试）"""
        try:
            self.logger.info(f'开始重新转换PDF文件: {self.bid_file_path}')

            # 更新数据库状态为"重新转换PDF中"
            if self.db and self.bid_document_id:
                try:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.processing_phase = '重新转换PDF中'
                        # 重置处理状态以便重新分析
                        bid_doc.processing_status = 'processing'
                        bid_doc.progress_current_rule = '重新转换PDF...'
                        self.db.commit()
                        self.logger.info(
                            f'已更新数据库状态为重新转换PDF中: {self.bidder_name}'
                        )
                except Exception as e:
                    self.logger.warning(f'更新数据库状态时出错: {e}')

            # 使用高级PDF处理器重新转换
            from modules.advanced_pdf_processor import AdvancedPDFProcessor

            # 创建临时目录
            temp_dir = 'temp/retry_ocr'
            output_dir = 'output'
            os.makedirs(temp_dir, exist_ok=True)
            os.makedirs(output_dir, exist_ok=True)

            # 创建高级PDF处理器实例
            processor = AdvancedPDFProcessor(output_dir=output_dir, temp_dir=temp_dir)

            # 尝试使用不同的方法重新转换
            methods = ['mineru', 'pymupdf', 'pdfplumber']
            for method in methods:
                try:
                    self.logger.info(f'尝试使用 {method} 方法重新转换PDF')
                    output_file = processor.process_pdf(
                        self.bid_file_path,
                        method=method,
                        enable_formula=True,
                        enable_table=True,
                        language='ch',
                    )

                    # 检查转换后的文件是否存在且非空
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        self.logger.info(
                            f'使用 {method} 方法重新转换PDF成功: {output_file}'
                        )

                        # 更新数据库状态为"重新转换PDF完成"
                        if self.db and self.bid_document_id:
                            try:
                                bid_doc = (
                                    self.db.query(BidDocument)
                                    .filter(BidDocument.id == self.bid_document_id)
                                    .first()
                                )
                                if bid_doc:
                                    bid_doc.processing_phase = 'PDF处理完成'
                                    bid_doc.progress_current_rule = (
                                        'PDF处理完成，准备分析...'
                                    )
                                    self.db.commit()
                                    self.logger.info(
                                        f'已更新数据库状态为PDF处理完成: {self.bidder_name}'
                                    )
                            except Exception as e:
                                self.logger.warning(f'更新数据库状态时出错: {e}')

                        return {
                            'status': 'success',
                            'message': '重新转换PDF成功',
                            'output_file': output_file,
                        }
                    else:
                        self.logger.warning(
                            f'使用 {method} 方法转换后的文件为空或不存在'
                        )
                except Exception as e:
                    self.logger.warning(f'使用 {method} 方法转换PDF时出错: {e}')
                    continue

            # 如果所有方法都失败了
            self.logger.error(f'所有重新转换方法都失败了: {self.bid_file_path}')

            # 更新数据库状态为"重新转换PDF失败"
            if self.db and self.bid_document_id:
                try:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.processing_phase = 'PDF处理失败'
                        bid_doc.progress_current_rule = 'PDF处理失败'
                        self.db.commit()
                        self.logger.info(
                            f'已更新数据库状态为PDF处理失败: {self.bidder_name}'
                        )
                except Exception as e:
                    self.logger.warning(f'更新数据库状态时出错: {e}')

            return {'status': 'error', 'message': '所有重新转换方法都失败了'}

        except Exception as outer_e:
            self.logger.error(f'重新转换PDF时发生意外错误: {outer_e}')

            # 更新数据库状态为"重新转换PDF失败"
            if self.db and self.bid_document_id:
                try:
                    bid_doc = (
                        self.db.query(BidDocument)
                        .filter(BidDocument.id == self.bid_document_id)
                        .first()
                    )
                    if bid_doc:
                        bid_doc.processing_phase = 'PDF处理失败'
                        bid_doc.progress_current_rule = 'PDF处理失败'
                        self.db.commit()
                        self.logger.info(
                            f'已更新数据库状态为PDF处理失败: {self.bidder_name}'
                        )
                except Exception as e:
                    self.logger.warning(f'更新数据库状态时出错: {e}')

            return {
                'status': 'error',
                'message': f'重新转换PDF时发生意外错误: {str(outer_e)}',
            }

    def analyze(self):
        """
        分析投标文件的公共接口方法
        """
        return self.analyze_bidding_document()

    def analyze_qualitative_rules_combined(self, qualitative_rules, bid_pages):
        """组合分析所有定性规则"""
        try:
            self.logger.info(
                f'正在为投标人 {self.bidder_name} 组合分析 {len(qualitative_rules)} 个定性规则'
            )

            # 构建组合prompt
            prompt = self._create_combined_prompt_for_qualitative_rules(
                qualitative_rules, bid_pages
            )

            # 检查是否需要分块处理
            if isinstance(prompt, list):
                # 分块处理
                return self._analyze_qualitative_rules_chunked(
                    prompt, qualitative_rules
                )
            else:
                # 单个prompt处理
                # 提交AI分析
                ai_response = self.ai_analyzer.analyze_text(prompt)
                if 'Error:' in ai_response:
                    # 如果组合分析失败，返回空结果，让调用者回退到逐条分析
                    raise Exception(f'AI分析失败: {ai_response}')

                # 解析AI响应
                results = self._parse_combined_ai_response(
                    ai_response, qualitative_rules
                )

                # 构造返回结果
                detailed_scores = []
                qualitative_results = {}

                for rule in qualitative_rules:
                    rule_name = rule.Child_Item_Name
                    if rule_name in results:
                        result = results[rule_name]
                        # 对于定性规则，我们不给分数，而是记录符合/不符合的结果
                        detailed_scores.append(
                            {
                                'Child_Item_Name': rule_name,
                                'max_score': rule.Child_max_score,
                                'score': 0,  # 定性规则不给具体分数
                                'result': result['result'],  # 符合/不符合
                                'reason': result['reason'],
                                'Parent_Item_Name': rule.Parent_Item_Name,
                                'is_qualitative': True,
                                'is_quantitative': False,
                                'is_veto': rule.is_veto,
                                'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                            }
                        )
                        qualitative_results[rule_name] = {
                            'Child_Item_Name': rule_name,
                            'max_score': rule.Child_max_score,
                            'score': 0,  # 定性规则不给具体分数
                            'result': result['result'],  # 符合/不符合
                            'reason': result['reason'],
                            'Parent_Item_Name': rule.Parent_Item_Name,
                            'is_qualitative': True,
                            'is_quantitative': False,
                            'is_veto': rule.is_veto,
                            'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                        }
                    else:
                        # 如果没有返回该规则的结果，给出默认值
                        detailed_scores.append(
                            {
                                'Child_Item_Name': rule_name,
                                'max_score': rule.Child_max_score,
                                'score': 0,
                                'result': '未知',
                                'reason': '未分析',
                                'Parent_Item_Name': rule.Parent_Item_Name,
                                'is_qualitative': True,
                                'is_quantitative': False,
                                'is_veto': rule.is_veto,
                                'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                            }
                        )
                        qualitative_results[rule_name] = {
                            'Child_Item_Name': rule_name,
                            'max_score': rule.Child_max_score,
                            'score': 0,
                            'result': '未知',
                            'reason': '未分析',
                            'Parent_Item_Name': rule.Parent_Item_Name,
                            'is_qualitative': True,
                            'is_quantitative': False,
                            'is_veto': rule.is_veto,
                            'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                        }

                return {
                    'detailed_scores': detailed_scores,
                    'qualitative_results': qualitative_results,
                }
        except Exception as e:
            self.logger.error(f'组合分析定性规则时出错: {e}')
            # 重新抛出异常，让调用者决定是否回退到逐条分析
            raise

    def _analyze_qualitative_rules_chunked(self, prompts, qualitative_rules):
        """分块分析定性规则"""
        detailed_scores = []
        qualitative_results = {}

        # 创建规则名称到规则对象的映射，便于查找
        rule_map = {rule.Child_Item_Name: rule for rule in qualitative_rules}

        # 逐个处理每个分块
        for i, prompt in enumerate(prompts):
            try:
                self.logger.info(f'正在分析第 {i + 1}/{len(prompts)} 个定性规则块')

                # 提交AI分析
                ai_response = self.ai_analyzer.analyze_text(prompt)
                if 'Error:' in ai_response:
                    self.logger.warning(
                        f'第 {i + 1} 个定性规则块AI分析失败: {ai_response}'
                    )
                    continue

                # 解析AI响应
                results = self._parse_combined_ai_response(
                    ai_response, qualitative_rules
                )

                # 将结果添加到总体结果中
                for rule_name, result in results.items():
                    if rule_name in rule_map:
                        rule = rule_map[rule_name]
                        # 对于定性规则，我们不给分数，而是记录符合/不符合的结果
                        detailed_scores.append(
                            {
                                'Child_Item_Name': rule_name,
                                'max_score': rule.Child_max_score,
                                'score': 0,  # 定性规则不给具体分数
                                'result': result['result'],  # 符合/不符合
                                'reason': result['reason'],
                                'Parent_Item_Name': rule.Parent_Item_Name,
                                'is_qualitative': True,
                                'is_quantitative': False,
                                'is_veto': rule.is_veto,
                                'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                            }
                        )
                        qualitative_results[rule_name] = {
                            'Child_Item_Name': rule_name,
                            'max_score': rule.Child_max_score,
                            'score': 0,  # 定性规则不给具体分数
                            'result': result['result'],  # 符合/不符合
                            'reason': result['reason'],
                            'Parent_Item_Name': rule.Parent_Item_Name,
                            'is_qualitative': True,
                            'is_quantitative': False,
                            'is_veto': rule.is_veto,
                            'needs_comprehensive_analysis': False,  # 定性规则不需要综合分析
                        }

            except Exception as e:
                self.logger.error(f'分析第 {i + 1} 个定性规则块时出错: {e}')
                continue

        # 如果没有成功分析任何规则，抛出异常让调用者回退到逐条分析
        if not qualitative_results:
            raise Exception('所有定性规则块分析都失败了')

        return {
            'detailed_scores': detailed_scores,
            'qualitative_results': qualitative_results,
        }

    def _create_combined_prompt_for_qualitative_rules(self, rules, bid_pages):
        """为定性规则组合创建AI分析prompt"""
        # 收集所有相关上下文
        all_context = []
        for rule in rules:
            relevant_context = self._find_relevant_context_for_child_rule(
                rule, bid_pages
            )
            all_context.append(f'【{rule.Child_Item_Name}】\n{relevant_context}')

        # 组合所有上下文
        combined_context = '\n\n'.join(all_context)

        # 构建规则描述，包含更详细的信息
        rule_descriptions = []
        for rule in rules:
            rule_descriptions.append(
                f'- 规则名称: {rule.Child_Item_Name}\n  规则描述: {rule.description or "无详细描述"}\n  满分: {rule.Child_max_score or 0}分\n  是否为否决项: {"是" if rule.is_veto else "否"}'
            )

        rules_text = '\n'.join(rule_descriptions)

        prompt = f"""你是一个专业的评标专家，请根据以下信息对投标文件进行定性评估：

【投标人名称】
{self.bidder_name}

【评估规则列表】
{rules_text}

【投标文件相关内容】
{combined_context}

【评估要求】
1. 请根据评估规则对投标文件相关内容进行定性分析
2. 对于每个评估规则，判断投标文件是否符合要求
3. 如果符合要求，请回答"符合"；如果不符合要求，请回答"不符合"并说明原因
4. 评估必须基于投标文件的实际内容，不能凭空猜测

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{
  "规则名称1": {{"result": "符合/不符合", "reason": "判断理由"}},
  "规则名称2": {{"result": "符合/不符合", "reason": "判断理由"}},
  ...
}}

示例：
{{
  "企业证书，认证体系": {{"result": "符合", "reason": "投标文件中提供了完整的认证证书，符合评分标准要求"}},
  "标书的完整性": {{"result": "不符合", "reason": "标书缺少技术方案部分"}}
}}
"""

        # 获取Ollama的上下文长度限制（预留一些余量）
        context_length_limit = self.ai_analyzer.context_length - 500

        # 检查prompt长度，如果超出限制则进行分块处理
        if len(prompt) > context_length_limit:
            # 如果prompt太长，需要分块处理
            return self._create_chunked_prompts_for_qualitative_rules(
                rules, bid_pages, context_length_limit
            )

        return prompt

    def _create_chunked_prompts_for_qualitative_rules(
        self, rules, bid_pages, context_length_limit
    ):
        """为过长的定性规则创建分块prompts"""
        # 将规则分组，每组规则创建一个prompt
        chunked_prompts = []
        chunk_size = max(1, len(rules) // 3)  # 大概分成3组

        for i in range(0, len(rules), chunk_size):
            chunk_rules = rules[i : i + chunk_size]
            prompt = self._create_combined_prompt_for_qualitative_rules_chunk(
                chunk_rules, bid_pages
            )

            # 如果单个chunk仍然太长，则进一步细分
            if len(prompt) > context_length_limit:
                # 进一步细分规则
                sub_chunk_size = max(1, len(chunk_rules) // 2)
                for j in range(0, len(chunk_rules), sub_chunk_size):
                    sub_chunk_rules = chunk_rules[j : j + sub_chunk_size]
                    sub_prompt = (
                        self._create_combined_prompt_for_qualitative_rules_chunk(
                            sub_chunk_rules, bid_pages
                        )
                    )
                    chunked_prompts.append(sub_prompt)
            else:
                chunked_prompts.append(prompt)

        return chunked_prompts

    def _create_combined_prompt_for_qualitative_rules_chunk(self, rules, bid_pages):
        """为定性规则块创建AI分析prompt"""
        # 收集所有相关上下文
        all_context = []
        for rule in rules:
            relevant_context = self._find_relevant_context_for_child_rule(
                rule, bid_pages
            )
            all_context.append(f'【{rule.Child_Item_Name}】\n{relevant_context}')

        # 组合所有上下文
        combined_context = '\n\n'.join(all_context)

        # 构建规则描述，包含更详细的信息
        rule_descriptions = []
        for rule in rules:
            rule_descriptions.append(
                f'- 规则名称: {rule.Child_Item_Name}\n  规则描述: {rule.description or "无详细描述"}\n  满分: {rule.Child_max_score or 0}分\n  是否为否决项: {"是" if rule.is_veto else "否"}'
            )

        rules_text = '\n'.join(rule_descriptions)

        prompt = f"""你是一个专业的评标专家，请根据以下信息对投标文件进行定性评估：

【投标人名称】
{self.bidder_name}

【评估规则列表】
{rules_text}

【投标文件相关内容】
{combined_context}

【评估要求】
1. 请根据评估规则对投标文件相关内容进行定性分析
2. 对于每个评估规则，判断投标文件是否符合要求
3. 如果符合要求，请回答"符合"；如果不符合要求，请回答"不符合"并说明原因
4. 评估必须基于投标文件的实际内容，不能凭空猜测

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{
  "规则名称1": {{"result": "符合/不符合", "reason": "判断理由"}},
  "规则名称2": {{"result": "符合/不符合", "reason": "判断理由"}},
  ...
}}

示例：
{{
  "企业证书，认证体系": {{"result": "符合", "reason": "投标文件中提供了完整的认证证书，符合评分标准要求"}},
  "标书的完整性": {{"result": "不符合", "reason": "标书缺少技术方案部分"}}
}}
"""
        return prompt


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='智能投标分析器')
    parser.add_argument('tender_file_path', help='招标文件路径')
    parser.add_argument('bid_file_path', help='投标文件路径')
    parser.add_argument('--db_session', help='数据库会话对象')
    parser.add_argument('--bid_document_id', help='投标文件ID')
    parser.add_argument('--project_id', help='项目ID')
    parser.add_argument('--extracted_text', help='预提取的文本内容')

    args = parser.parse_args()

    analyzer = IntelligentBidAnalyzer(
        tender_file_path=args.tender_file_path,
        bid_file_path=args.bid_file_path,
        db_session=args.db_session,
        bid_document_id=args.bid_document_id,
        project_id=args.project_id,
        extracted_text=args.extracted_text,
    )

    result = analyzer.analyze()
    print(result)
