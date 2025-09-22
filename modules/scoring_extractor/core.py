#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-11 20:10:49
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-13 11:00:00
# 文件相对于项目的路径   : \AI_env2\modules\scoring_extractor\core.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import logging
from typing import List, Dict, Any
import json

from modules.table_analyzer import TableAnalyzer
from .rule_parser import ScoringRuleParser
from .default_rules import DefaultRulesMixin
from .structure_handler import StructureHandlerMixin
from .text_analyzer import TextAnalyzerMixin
from modules.pdf_processor import PDFProcessor


class IntelligentScoringExtractor(
    DefaultRulesMixin, StructureHandlerMixin, TextAnalyzerMixin
):
    """
    一个精简、重构后的评分规则提取器。
    它遵循一个清晰的流程：
    1. 使用 TableAnalyzer 从PDF中提取结构化表格。
    2. 使用 ScoringRuleParser 从表格中解析出评分规则。
    3. 如果上述步骤失败，则回退到默认规则。
    """

    def __init__(self):
        """初始化提取器，设置日志和解析器。"""
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.rule_parser = ScoringRuleParser()

    def extract(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        从指定的PDF文件中提取评分规则。

        Args:
            pdf_path (str): 需要分析的PDF文件的绝对路径。

        Returns:
            List[Dict[str, Any]]: 一个结构化的评分规则列表（树形结构）。
                                  如果提取失败，则返回一个默认的规则集。
        """
        if not pdf_path:
            self.logger.warning('PDF路径为空，无法提取评分规则。将返回默认规则。')
            return self._get_fallback_rules()

        try:
            self.logger.info(f"开始从PDF文件 '{pdf_path}' 中提取评分规则...")

            # 1. 使用 TableAnalyzer 提取和解析表格
            analyzer = TableAnalyzer(pdf_path)

            # 提取所有表格（不经过过滤）- 参考extract_all_tables.py的实现
            self.logger.info('正在提取表格...')
            all_tables = analyzer._extract_all_tables()

            if not all_tables:
                self.logger.warning(
                    '在PDF中未能找到任何表格。严格按项目要求，不使用默认规则与OCR，返回空并提示前端。'
                )
                return []

            self.logger.info(f'总共找到 {len(all_tables)} 个原始表格')

            # 尝试合并跨页表格 - 参考extract_all_tables.py的实现
            self.logger.info('正在合并跨页表格...')
            merged_tables = analyzer._merge_cross_page_tables(all_tables)
            self.logger.info(f'合并后得到 {len(merged_tables)} 个表格')

            # 转换为结构化格式（所有合并后的表格）- 参考extract_all_tables.py的实现
            self.logger.info('正在转换为结构化格式...')
            structured_tables = analyzer.convert_to_structured_format(merged_tables)

            # 2. 使用 ScoringRuleParser 解析规则
            scoring_rules = self.rule_parser.parse_scoring_rules_from_table_data(
                structured_tables
            )

            if not scoring_rules:
                self.logger.warning(
                    '从表格中未能解析出任何评分规则。严格按项目要求，不使用默认规则与OCR，返回空并提示前端。'
                )
                return []

            # 3. 构建树形结构并验证分数
            tree = self._build_tree_from_flat_list(scoring_rules)
            self._verify_and_adjust_scores(tree)

            self.logger.info(f'成功提取并处理了 {len(scoring_rules)} 条评分规则。')
            return tree

        except Exception as e:
            self.logger.error(f'提取评分规则时发生严重错误: {e}', exc_info=True)
            return []

    def _get_fallback_rules(self) -> List[Dict[str, Any]]:
        """
        在提取失败时，提供一个回退机制，返回默认的评分规则。
        """
        self.logger.info('回退到默认评分规则。')
        try:
            default_rules = self._get_default_scoring_rules()
            if default_rules:
                tree = self._build_tree_from_flat_list(default_rules)
                self._verify_and_adjust_scores(tree)
                return tree
        except Exception as fallback_e:
            self.logger.error(f'回退到默认规则时也失败了: {fallback_e}')

        return []

    def _extract_via_text_fallback(self, pdf_path: str) -> List[Dict[str, Any]]:
        """
        当表格法失败时，回退到文本法提取评分规则。
        """
        try:
            # 读取运行时GPU配置
            import os

            use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'

            # 使用PDFProcessor提取全文文本（针对招标文件）
            processor = PDFProcessor(pdf_path, use_gpu=use_gpu, file_type='tender')
            pages_text = processor.extract_text_per_page()
            if not pages_text or not any(p.strip() for p in pages_text):
                self.logger.warning('文本法回退失败：未能提取到任何文本。')
                return self._get_fallback_rules()

            # 设置文本供TextAnalyzerMixin使用
            self.texts = pages_text  # type: ignore[attr-defined]

            # 通过文本分析提取评分规则
            tree = self._extract_scoring_rules_from_text()
            if tree:
                self.logger.info(
                    f'文本法回退成功，提取到 {len(tree)} 条评分规则（树形结点数）。'
                )
                return tree

            self.logger.warning('文本法回退未能提取到评分规则，返回默认规则。')
            return self._get_fallback_rules()
        except Exception as e:
            self.logger.error(f'文本法回退提取评分规则时出错: {e}', exc_info=True)
            return self._get_fallback_rules()

    def generate_scoring_template(self, pdf_path: str) -> str:
        """
        提取评分规则并生成一个JSON格式的评分模板。

        Args:
            pdf_path (str): 需要分析的PDF文件的路径。

        Returns:
            str: JSON格式的评分规则模板。
        """
        rules = self.extract(pdf_path)
        return json.dumps(rules, ensure_ascii=False, indent=2)
