#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-11 20:13:08
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-13 10:05:00
# 文件相对于项目的路径   : \AI_env2\modules\scoring_extractor\__init__.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#

"""
评分提取器模块 (scoring_extractor)

该模块提供从PDF文件中提取评分规则的核心功能。

主要导出:
- IntelligentScoringExtractor: 核心类，用于从PDF提取和解析评分规则。
- ScoringRuleParser: 用于从结构化数据中解析具体规则的辅助类。
"""

from .core import IntelligentScoringExtractor
from .rule_parser import ScoringRuleParser

__all__ = [
    "IntelligentScoringExtractor",
    "ScoringRuleParser",
]
