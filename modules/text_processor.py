#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理模块
使用textacy库对文本进行清洗和MD文本处理
"""

import re
import logging
from typing import List, Dict, Any, Optional
import textacy
from textacy import preprocessing
from textacy.preprocessing import normalize, remove

# 配置日志
logger = logging.getLogger(__name__)


class TextProcessor:
    """文本处理器类，使用textacy库进行文本清洗和处理"""

    def __init__(self):
        """初始化文本处理器"""
        self.logger = logging.getLogger(__name__)

    def clean_text(self, text: str) -> str:
        """
        使用textacy清洗文本

        Args:
            text: 待清洗的文本

        Returns:
            str: 清洗后的文本
        """
        if not text:
            return ''

        try:
            # 创建textacy文档
            doc = textacy.make_spacy_doc(text, lang='zh')

            # 使用textacy预处理功能清洗文本
            # 移除多余的空白字符
            text = preprocessing.normalize_whitespace(text)

            # 移除多余的标点符号
            text = preprocessing.remove_punctuation(text, only_in_front_of=len(text))

            # 移除多余的换行符，保留单个换行符
            text = re.sub(r'\n{3,}', '\n\n', text)

            # 移除行首行尾的空白字符
            lines = text.split('\n')
            cleaned_lines = [line.strip() for line in lines]
            text = '\n'.join(cleaned_lines)

            return text.strip()
        except Exception as e:
            self.logger.warning(f'使用textacy清洗文本时出错: {e}')
            # 回退到基本的文本清洗方法
            return self._basic_clean_text(text)

    def _basic_clean_text(self, text: str) -> str:
        """
        基本文本清洗方法（当textacy不可用时的回退方案）

        Args:
            text: 待清洗的文本

        Returns:
            str: 清洗后的文本
        """
        if not text:
            return ''

        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)

        # 移除多余的换行符
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除行首行尾的空白字符
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines]
        text = '\n'.join(cleaned_lines)

        return text.strip()

    def clean_md_text(self, md_text: str) -> str:
        """
        清洗Markdown文本

        Args:
            md_text: Markdown文本

        Returns:
            str: 清洗后的Markdown文本
        """
        if not md_text:
            return ''

        try:
            # 保持Markdown结构的清洗
            # 移除多余的空白行，但保留Markdown结构
            md_text = re.sub(r'\n{4,}', '\n\n\n', md_text)

            # 清洗每一行
            lines = md_text.split('\n')
            cleaned_lines = []

            for line in lines:
                # 如果是Markdown标题行，只清理行首行尾空格
                if line.startswith('#'):
                    cleaned_lines.append(line.strip())
                # 如果是Markdown表格行，保持表格结构
                elif '|' in line and line.count('|') >= 2:
                    # 清理表格单元格内容
                    cells = line.split('|')
                    cleaned_cells = [cell.strip() for cell in cells]
                    cleaned_lines.append('|'.join(cleaned_cells))
                else:
                    # 普通文本行使用textacy清洗
                    cleaned_line = self.clean_text(line)
                    cleaned_lines.append(cleaned_line)

            return '\n'.join(cleaned_lines).strip()
        except Exception as e:
            self.logger.warning(f'清洗Markdown文本时出错: {e}')
            # 回退到基本清洗方法
            return self._basic_clean_md_text(md_text)

    def _basic_clean_md_text(self, md_text: str) -> str:
        """
        基本Markdown文本清洗方法

        Args:
            md_text: Markdown文本

        Returns:
            str: 清洗后的Markdown文本
        """
        if not md_text:
            return ''

        # 移除多余的空白行，但保留Markdown结构
        md_text = re.sub(r'\n{4,}', '\n\n\n', md_text)

        # 清洗每一行
        lines = md_text.split('\n')
        cleaned_lines = []

        for line in lines:
            # 如果是Markdown标题行，只清理行首行尾空格
            if line.startswith('#'):
                cleaned_lines.append(line.strip())
            # 如果是Markdown表格行，保持表格结构
            elif '|' in line and line.count('|') >= 2:
                # 清理表格单元格内容
                cells = line.split('|')
                cleaned_cells = [cell.strip() for cell in cells]
                cleaned_lines.append('|'.join(cleaned_cells))
            else:
                # 普通文本行使用基本清洗
                cleaned_line = self._basic_clean_text(line)
                cleaned_lines.append(cleaned_line)

        return '\n'.join(cleaned_lines).strip()

    def extract_keywords(self, text: str, n_keywords: int = 10) -> List[str]:
        """
        使用textacy提取文本关键词

        Args:
            text: 文本内容
            n_keywords: 提取关键词数量

        Returns:
            List[str]: 关键词列表
        """
        try:
            # 创建textacy文档
            doc = textacy.make_spacy_doc(text, lang='zh')

            # 提取关键词
            keywords = list(
                textacy.extract.keyterms.textrank(doc, n_keyterms=n_keywords)
            )

            # 只返回关键词，不返回权重
            return [kw[0] for kw in keywords]
        except Exception as e:
            self.logger.warning(f'提取关键词时出错: {e}')
            return []

    def normalize_text(self, text: str) -> str:
        """
        标准化文本格式

        Args:
            text: 原始文本

        Returns:
            str: 标准化后的文本
        """
        try:
            # 使用textacy进行文本标准化
            # 统一引号
            text = normalize.quotation_marks(text)

            # 统一货币符号
            text = normalize.currency_symbols(text)

            # 统一百分比符号
            text = normalize.percentages(text)

            # 统一数字空格
            text = normalize.numbers(text)

            # 统一unicode字符
            text = normalize.unicode(text)

            return text
        except Exception as e:
            self.logger.warning(f'标准化文本时出错: {e}')
            return text

    def remove_unwanted_elements(self, text: str) -> str:
        """
        移除文本中的不需要元素

        Args:
            text: 原始文本

        Returns:
            str: 清理后的文本
        """
        try:
            # 移除URL
            text = remove.urls(text)

            # 移除邮箱地址
            text = remove.emails(text)

            # 移除电话号码
            text = remove.phone_numbers(text)

            # 移除多余的标点符号
            text = remove.punctuation(text, only_in_front_of=len(text))

            return text
        except Exception as e:
            self.logger.warning(f'移除不需要元素时出错: {e}')
            return text


def clean_text_for_analysis(text: str) -> str:
    """
    为分析准备清洗文本的便捷函数

    Args:
        text: 原始文本

    Returns:
        str: 清洗后的文本
    """
    processor = TextProcessor()
    return processor.clean_text(text)


def clean_md_content(md_text: str) -> str:
    """
    清洗Markdown内容的便捷函数

    Args:
        md_text: Markdown文本

    Returns:
        str: 清洗后的Markdown文本
    """
    processor = TextProcessor()
    return processor.clean_md_text(md_text)


def extract_text_keywords(text: str, n_keywords: int = 10) -> List[str]:
    """
    提取文本关键词的便捷函数

    Args:
        text: 文本内容
        n_keywords: 提取关键词数量

    Returns:
        List[str]: 关键词列表
    """
    processor = TextProcessor()
    return processor.extract_keywords(text, n_keywords)


# 示例使用
if __name__ == '__main__':
    # 示例文本
    sample_text = """
    这是一个    示例文本，
    包含很多    不必要的空格和换行符。
    
    
    还有一些特殊字符和URL：https://example.com
    """

    # 创建文本处理器
    processor = TextProcessor()

    # 清洗文本
    cleaned = processor.clean_text(sample_text)
    print('清洗后的文本:')
    print(cleaned)

    # 示例Markdown文本
    sample_md = """
    # 标题
    
    这是   一段文本。
    
    
    | 表格 | 示例 |
    | ---- | ---- |
    |  数据  | 内容 |
    """

    # 清洗Markdown文本
    cleaned_md = processor.clean_md_text(sample_md)
    print('\n清洗后的Markdown文本:')
    print(cleaned_md)
