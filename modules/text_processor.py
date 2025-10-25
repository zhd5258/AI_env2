#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
文本处理模块
使用textacy库对文本进行清洗和MD文本处理
"""

import re
import logging
from typing import List, Dict, Any, Optional

# 配置日志
logger = logging.getLogger(__name__)

# 检查textacy和spaCy是否可用
TEXTACY_AVAILABLE = False
SPACY_ZH_MODEL_AVAILABLE = False

try:
    import textacy

    TEXTACY_AVAILABLE = True

    # 检查中文模型是否可用
    try:
        import spacy

        nlp = spacy.load('zh_core_web_sm')
        SPACY_ZH_MODEL_AVAILABLE = True
    except (OSError, ImportError):
        SPACY_ZH_MODEL_AVAILABLE = False
        logger.warning('spaCy中文模型不可用，将使用基本文本清洗方法')
except ImportError:
    TEXTACY_AVAILABLE = False
    SPACY_ZH_MODEL_AVAILABLE = False
    logger.warning('textacy库不可用，将使用基本文本清洗方法')


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

        # 如果textacy和spaCy中文模型可用，使用textacy清洗文本
        if TEXTACY_AVAILABLE and SPACY_ZH_MODEL_AVAILABLE:
            try:
                import textacy
                from textacy import preprocessing

                # 创建textacy文档，使用正确的API
                nlp = textacy.load_spacy_lang('zh_core_web_sm')
                doc = textacy.make_spacy_doc(text, lang=nlp)

                # 使用textacy预处理功能清洗文本
                # 移除多余的空白字符
                text = preprocessing.normalize.whitespace(text)

                # 移除多余的标点符号
                text = preprocessing.remove.punctuation(text)

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
        else:
            # 如果textacy或spaCy中文模型不可用，使用基本清洗方法
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
            # 如果textacy可用且中文模型可用，使用textacy清洗文本
            if TEXTACY_AVAILABLE and SPACY_ZH_MODEL_AVAILABLE:
                import textacy
                from textacy import preprocessing

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
                        try:
                            # 创建textacy文档
                            doc = textacy.make_spacy_doc(line, lang='zh')

                            # 清洗文本
                            cleaned_line = preprocessing.normalize.whitespace(line)
                            cleaned_line = preprocessing.remove.punctuation(
                                cleaned_line
                            )
                            cleaned_lines.append(cleaned_line.strip())
                        except Exception:
                            # 如果textacy清洗失败，使用基本清洗方法
                            cleaned_line = self._basic_clean_text(line)
                            cleaned_lines.append(cleaned_line)

                return '\n'.join(cleaned_lines).strip()
            else:
                # 回退到基本清洗方法
                return self._basic_clean_md_text(md_text)
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
        # 暂时禁用关键词提取功能，因为存在依赖兼容性问题
        self.logger.warning('关键词提取功能暂时不可用，返回空列表')
        return []

        # 如果需要启用此功能，请确保解决以下依赖问题：
        # 1. networkx版本兼容性问题
        # 2. textacy与spaCy版本兼容性问题
        """
        # 如果textacy可用且中文模型可用，使用textacy提取关键词
        if TEXTACY_AVAILABLE and SPACY_ZH_MODEL_AVAILABLE:
            try:
                import textacy
                import textacy.extract.keyterms
                
                # 创建textacy文档，使用正确的API
                nlp = textacy.load_spacy_lang("zh_core_web_sm")
                doc = textacy.make_spacy_doc(text, lang=nlp)

                # 提取关键词，使用更简单的算法
                try:
                    # 使用sgrank算法，它对依赖版本要求较低
                    keywords = list(
                        textacy.extract.keyterms.sgrank(doc, ngrams=(1, 2), topn=n_keywords)
                    )
                    # 只返回关键词，不返回权重
                    return [kw[0] for kw in keywords]
                except Exception as e:
                    self.logger.warning(f'使用sgrank提取关键词时出错: {e}')
                    # 如果sgrank也失败，返回空列表
                    return []
            except Exception as e:
                self.logger.warning(f'提取关键词时出错: {e}')
                return []
        else:
            # 如果textacy或中文模型不可用，返回空列表
            self.logger.warning('textacy或spaCy中文模型不可用，无法提取关键词')
            return []
        """

    def normalize_text(self, text: str) -> str:
        """
        标准化文本格式

        Args:
            text: 原始文本

        Returns:
            str: 标准化后的文本
        """
        # 如果textacy可用且中文模型可用，使用textacy标准化文本
        if TEXTACY_AVAILABLE and SPACY_ZH_MODEL_AVAILABLE:
            try:
                from textacy import preprocessing

                # 使用textacy进行文本标准化
                # 统一引号
                text = preprocessing.normalize.quotation_marks(text)

                # 统一unicode字符
                text = preprocessing.normalize.unicode(text)

                # 统一空白字符
                text = preprocessing.normalize.whitespace(text)

                return text
            except Exception as e:
                self.logger.warning(f'标准化文本时出错: {e}')
                return text
        else:
            # 如果textacy或中文模型不可用，返回原文本
            return text

    def remove_unwanted_elements(self, text: str) -> str:
        """
        移除文本中的不需要元素

        Args:
            text: 原始文本

        Returns:
            str: 清理后的文本
        """
        # 如果textacy可用且中文模型可用，使用textacy移除不需要的元素
        if TEXTACY_AVAILABLE and SPACY_ZH_MODEL_AVAILABLE:
            try:
                from textacy import preprocessing

                # 移除HTML标签
                text = preprocessing.remove.html_tags(text)

                # 移除多余的标点符号
                text = preprocessing.remove.punctuation(text)

                return text
            except Exception as e:
                self.logger.warning(f'移除不需要元素时出错: {e}')
                return text
        else:
            # 如果textacy或中文模型不可用，返回原文本
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
