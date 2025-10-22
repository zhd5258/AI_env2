#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
text_processor模块使用示例
展示如何使用textacy库进行文本清洗和MD文本处理
"""

import logging
from .text_processor import TextProcessor, clean_text_for_analysis, clean_md_content

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def example_text_cleaning():
    """文本清洗示例"""
    # 创建文本处理器实例
    processor = TextProcessor()

    # 示例文本
    sample_text = """
    这是一个    示例文本，
    包含很多    不必要的空格和换行符。
    
    
    还有一些特殊字符和URL：https://example.com
    
    这是另一段文本，包含"引号"和'单引号'。
    """

    print('原始文本:')
    print(repr(sample_text))

    # 使用textacy清洗文本
    cleaned_text = processor.clean_text(sample_text)
    print('\n清洗后的文本:')
    print(repr(cleaned_text))

    # 使用便捷函数清洗文本
    cleaned_text2 = clean_text_for_analysis(sample_text)
    print('\n使用便捷函数清洗后的文本:')
    print(repr(cleaned_text2))


def example_md_cleaning():
    """Markdown文本清洗示例"""
    # 创建文本处理器实例
    processor = TextProcessor()

    # 示例Markdown文本
    sample_md = """
    # 这是   一个标题
    
    这是    一段文本，
    包含很多    不必要的空格和换行符。
    
    
    | 表格 | 示例 |
    | ---- | ---- |
    |  数据  | 内容 |
    
    
    ## 另一个标题
    
    这是另一段文本。
    """

    print('原始Markdown文本:')
    print(sample_md)

    # 清洗Markdown文本
    cleaned_md = processor.clean_md_text(sample_md)
    print('\n清洗后的Markdown文本:')
    print(cleaned_md)


def example_keyword_extraction():
    """关键词提取示例"""
    # 创建文本处理器实例
    processor = TextProcessor()

    # 示例文本
    sample_text = """
    这是一个关于人工智能和机器学习的示例文本。
    文本中提到了深度学习、自然语言处理和计算机视觉等技术。
    这些技术在现代科技中发挥着重要作用。
    """

    print('原始文本:')
    print(sample_text)

    # 提取关键词
    keywords = processor.extract_keywords(sample_text, n_keywords=5)
    print('\n提取的关键词:')
    for i, keyword in enumerate(keywords, 1):
        print(f'{i}. {keyword}')


def example_text_normalization():
    """文本标准化示例"""
    # 创建文本处理器实例
    processor = TextProcessor()

    # 示例文本
    sample_text = """
    这是一段包含"直引号"和'单引号'的文本。
    还包含一些货币符号：$100, €50, ¥200。
    以及一些百分比：25%, 50%, 75%。
    """

    print('原始文本:')
    print(sample_text)

    # 标准化文本
    normalized_text = processor.normalize_text(sample_text)
    print('\n标准化后的文本:')
    print(normalized_text)


def example_unwanted_elements_removal():
    """移除不需要元素示例"""
    # 创建文本处理器实例
    processor = TextProcessor()

    # 示例文本
    sample_text = """
    这是一段包含URL的文本：https://example.com
    还有邮箱地址：user@example.com
    以及电话号码：+86 138 0013 8000
    """

    print('原始文本:')
    print(sample_text)

    # 移除不需要的元素
    cleaned_text = processor.remove_unwanted_elements(sample_text)
    print('\n移除不需要元素后的文本:')
    print(cleaned_text)


def main():
    """主函数，运行所有示例"""
    print('=' * 50)
    print('文本清洗示例')
    print('=' * 50)
    example_text_cleaning()

    print('\n' + '=' * 50)
    print('Markdown文本清洗示例')
    print('=' * 50)
    example_md_cleaning()

    print('\n' + '=' * 50)
    print('关键词提取示例')
    print('=' * 50)
    example_keyword_extraction()

    print('\n' + '=' * 50)
    print('文本标准化示例')
    print('=' * 50)
    example_text_normalization()

    print('\n' + '=' * 50)
    print('移除不需要元素示例')
    print('=' * 50)
    example_unwanted_elements_removal()


if __name__ == '__main__':
    main()
