#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-11 20:10:49
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-11 20:19:00
# 文件相对于项目的路径   : \AI_env2\modules\scoring_extractor\core.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import re
import logging
from typing import List, Dict, Any, Tuple
import json

from modules.local_ai_analyzer import LocalAIAnalyzer


class IntelligentScoringExtractor:
    def __init__(self, texts=None, ai_analyzer=None, pages=None):
        # 兼容不同参数方式
        if texts is not None:
            self.texts = texts
        elif pages is not None:
            self.texts = pages
        else:
            self.texts = []

        self.ai_analyzer = ai_analyzer if ai_analyzer is not None else LocalAIAnalyzer()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        主要的评分规则提取入口函数
        1. 首先尝试从PDF文件中提取表格形式的评分规则
        2. 如果失败，则使用传统的文本分析方法
        """
        try:
            # 尝试从PDF中提取评分规则
            pdf_rules = self._try_extract_from_pdf()
            if pdf_rules:
                self.logger.info('成功从PDF中提取评分规则')
                return pdf_rules

            # 如果没有提供PDF路径或PDF提取失败，使用传统的文本分析方法
            self.logger.info('无法从PDF中提取评分规则，使用传统文本分析方法')
            return self._extract_scoring_rules_from_text()

        except Exception as e:
            self.logger.error(f'提取评分规则时发生严重错误: {e}', exc_info=True)
            # 发生严重错误时返回默认规则
            try:
                default_rules = self._get_default_scoring_rules()
                if default_rules:
                    tree = self._build_tree_from_flat_list(default_rules)
                    self._verify_and_adjust_scores(tree)
                    return tree
            except Exception as fallback_e:
                self.logger.error(f'回退到默认规则也失败: {fallback_e}')
            return []

    def _try_extract_from_pdf(self) -> List[Dict[str, Any]]:
        """
        尝试从PDF文件中提取评分规则
        """
        # 这里需要获取PDF文件路径，假设它与文本文件在同一目录下
        # 或者通过某种方式传递PDF文件路径
        try:
            # 查找可能的PDF文件路径
            if hasattr(self, '_get_pdf_path') and callable(self._get_pdf_path):
                pdf_path = self._get_pdf_path()
                if pdf_path:
                    return self.extract_scoring_rules_from_pdf(pdf_path)
        except Exception as e:
            self.logger.warning(f'尝试从PDF提取评分规则失败: {e}')

        return []

    def parse_evaluation_criteria(self):
        return self.extract_scoring_rules()

    def generate_scoring_template(self):
        rules = self.extract_scoring_rules()

        # 自定义一个JSON编码器来处理嵌套结构
        def default_serializer(o):
            return o.__dict__

        return json.dumps(
            rules, ensure_ascii=False, indent=2, default=default_serializer
        )
