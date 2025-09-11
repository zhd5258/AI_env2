#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-11 20:13:08
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-11 20:16:26
# 文件相对于项目的路径   : \AI_env2\modules\scoring_extractor\__init__.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
from .core import IntelligentScoringExtractor
from .text_analyzer import TextAnalyzerMixin
from .table_analyzer import TableAnalyzerMixin
from .ai_analyzer import AIAnalyzerMixin
from .structure_handler import StructureHandlerMixin
from .default_rules import DefaultRulesMixin
from .db_handler import DBHandlerMixin


# 通过多重继承整合所有功能
class IntegratedIntelligentScoringExtractor(
    IntelligentScoringExtractor,
    TextAnalyzerMixin,
    TableAnalyzerMixin,
    AIAnalyzerMixin,
    StructureHandlerMixin,
    DefaultRulesMixin,
    DBHandlerMixin,
):
    """智能评分规则提取器，整合所有功能"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)