#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-25 17:40:40
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-25 17:42:44
#文件相对于项目的路径   : \AI_ENV2\tools\enhanced_text_cleaner.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
增强文本清洗工具
提供更高级的文本清洗功能，用于处理评分规则文本和描述
"""

import re
import logging
from typing import Dict, List

# 配置日志
logger = logging.getLogger(__name__)


def clean_scoring_rule_text(text: str) -> str:
    """
    清洗评分规则文本

    Args:
        text: 原始评分规则文本

    Returns:
        str: 清洗后的文本
    """
    if not text:
        return ''

    try:
        # 移除首尾空白字符
        text = text.strip()

        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)

        # 移除常见的无用前缀/后缀
        patterns_to_remove = [
            r'^\d+\s*[\.\-、]\s*',  # 移除开头的数字编号
            r'\s*[:：]\s*$',  # 移除结尾的冒号
            r'^[\.．]\s*',  # 移除开头的点号
        ]

        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text)

        # 移除特殊字符但保留中文、英文、数字和基本标点
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,;:!?()\-—\[\]{}"\'/\\]+', '', text)

        # 再次清理多余空白
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)

        return text
    except Exception as e:
        logger.warning(f'清洗评分规则文本时出错: {e}')
        return text


def clean_rule_description(description: str) -> str:
    """
    清洗规则描述文本

    Args:
        description: 原始规则描述

    Returns:
        str: 清洗后的描述
    """
    if not description:
        return ''

    try:
        # 移除首尾空白字符
        description = description.strip()

        # 移除多余的空白字符
        description = re.sub(r'\s+', ' ', description)

        # 移除常见的无用描述
        useless_patterns = [
            r'见.*说明',
            r'详见.*',
            r'参见.*',
            r'见.*表',
            r'如.*所示',
            r'同上',
            r'同前',
            r'附.*',
            r'如图.*',
            r'如下.*',
        ]

        for pattern in useless_patterns:
            description = re.sub(pattern, '', description, flags=re.IGNORECASE)

        # 移除特殊字符但保留中文、英文、数字和基本标点
        description = re.sub(
            r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.,;:!?()\-—\[\]{}"\'/\\]+', '', description
        )

        # 再次清理多余空白
        description = description.strip()
        description = re.sub(r'\s+', ' ', description)

        return description
    except Exception as e:
        logger.warning(f'清洗规则描述时出错: {e}')
        return description


def clean_text_for_analysis(text: str) -> str:
    """
    为分析准备清洗文本

    Args:
        text: 原始文本

    Returns:
        str: 清洗后的文本
    """
    if not text:
        return ''

    try:
        # 移除首尾空白字符
        text = text.strip()

        # 移除多余的换行符，但保留段落结构
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除行首行尾的空白字符
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        text = '\n'.join(cleaned_lines)

        return text
    except Exception as e:
        logger.warning(f'为分析准备清洗文本时出错: {e}')
        return text


# 示例使用
if __name__ == '__main__':
    # 测试清洗功能
    test_text = '  1. 评分规则示例   ：  这是一个测试文本  '
    cleaned = clean_scoring_rule_text(test_text)
    print(f'原始文本: {test_text}')
    print(f'清洗后: {cleaned}')

    test_desc = '详见技术规格书说明'
    cleaned_desc = clean_rule_description(test_desc)
    print(f'原始描述: {test_desc}')
    print(f'清洗后: {cleaned_desc}')
