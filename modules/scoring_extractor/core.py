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

class IntelligentScoringExtractor(DefaultRulesMixin, StructureHandlerMixin):
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
            self.logger.warning("PDF路径为空，无法提取评分规则。将返回默认规则。")
            return self._get_fallback_rules()

        try:
            self.logger.info(f"开始从PDF文件 '{pdf_path}' 中提取评分规则...")
            
            # 1. 使用 TableAnalyzer 提取和解析表格
            analyzer = TableAnalyzer(pdf_path)
            tables = analyzer.extract_and_merge_tables()
            if not tables:
                self.logger.warning("在PDF中未能找到符合条件的表格。")
                return self._get_fallback_rules()
                
            structured_tables = analyzer.convert_to_structured_format(tables)
            
            # 2. 使用 ScoringRuleParser 解析规则
            scoring_rules = self.rule_parser.parse_scoring_rules_from_table_data(structured_tables)
            
            if not scoring_rules:
                self.logger.warning("从表格中未能解析出任何评分规则。")
                return self._get_fallback_rules()

            # 3. 构建树形结构并验证分数
            tree = self._build_tree_from_flat_list(scoring_rules)
            self._verify_and_adjust_scores(tree)
            
            self.logger.info(f"成功提取并处理了 {len(scoring_rules)} 条评分规则。")
            return tree

        except Exception as e:
            self.logger.error(f"提取评分规则时发生严重错误: {e}", exc_info=True)
            return self._get_fallback_rules()

    def _get_fallback_rules(self) -> List[Dict[str, Any]]:
        """
        在提取失败时，提供一个回退机制，返回默认的评分规则。
        """
        self.logger.info("回退到默认评分规则。")
        try:
            default_rules = self._get_default_scoring_rules()
            if default_rules:
                tree = self._build_tree_from_flat_list(default_rules)
                self._verify_and_adjust_scores(tree)
                return tree
        except Exception as fallback_e:
            self.logger.error(f"回退到默认规则时也失败了: {fallback_e}")
        
        return []

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
