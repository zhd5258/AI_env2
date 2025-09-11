"""
智能评分规则提取器模块
该模块已重构为多个子模块，以提高代码的可维护性和模块化程度
"""

# 从新的模块结构导入IntelligentScoringExtractor类
from .scoring_extractor import IntegratedIntelligentScoringExtractor as IntelligentScoringExtractor

# 保持向后兼容性
__all__ = ['IntelligentScoringExtractor']