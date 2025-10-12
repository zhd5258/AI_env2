#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
PDF处理器模块
根据PDF文档类型选择合适的处理引擎：
1. 可编辑可搜索的PDF文档使用PyMuPDF引擎
2. 不可编辑不可搜索的PDF文档使用MinerU引擎
"""

import os
import logging
import sys
import re  # 添加正则表达式模块导入
import threading
from typing import List, Optional
from pathlib import Path

# PyMuPDF类型
try:
    import fitz  # PyMuPDF
    from fitz import Document, Page
except ImportError:
    Document = None
    Page = None

# 尝试导入PyMuPDF
try:
    import fitz  # PyMuPDF

    PymuPDF_AVAILABLE = True
except ImportError:
    PymuPDF_AVAILABLE = False
    fitz = None
    logging.warning('PyMuPDF (fitz) 未安装')

from .advanced_pdf_processor import MinerUProcessor

# 添加一个锁来防止并行PDF转换
pdf_conversion_lock = threading.Lock()


class PDFToMarkdownConverter:
    def __init__(self):
        self.document = None  # type: ignore
        self.logger = logging.getLogger(__name__)

    def convert_pdf_to_markdown(
        self, pdf_path: str, output_path: Optional[str] = None
    ) -> str:
        """
        将可编辑可搜索PDF转换为格式良好的Markdown

        Args:
            pdf_path: PDF文件路径
            output_path: 输出Markdown文件路径（可选）

        Returns:
            转换后的Markdown字符串
        """
        # 打开PDF文档
        self.document = fitz.open(pdf_path)  # type: ignore
        markdown_content = []

        # 处理每一页
        for page_num in range(len(self.document)):  # type: ignore
            page_content = self._process_page(page_num)
            markdown_content.append(page_content)

        # 合并所有页面内容
        final_markdown = '\n\n---\n\n'.join(markdown_content)

        # 清理和优化格式
        final_markdown = self._clean_and_optimize_markdown(final_markdown)

        # 保存到文件（如果指定了输出路径）
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_markdown)

        return final_markdown

    def _process_page(self, page_num: int) -> str:
        """
        处理单个页面，提取文本和表格
        """
        page = self.document[page_num]  # type: ignore
        content_parts = []

        # 提取文本内容
        text_content = self._extract_text_with_formatting(page)
        if text_content.strip():
            content_parts.append(text_content)

        # 提取表格
        tables = self._extract_tables(page)
        for table in tables:
            content_parts.append(table)

        return '\n\n'.join(content_parts)

    def _extract_text_with_formatting(self, page) -> str:
        """
        提取带基本格式的文本内容
        """
        # 获取页面的所有文本块
        blocks = page.get_text('dict')
        text_blocks = []

        for block in blocks['blocks']:
            if 'lines' in block:  # 文本块
                block_text = self._process_text_block(block)
                if block_text.strip():
                    text_blocks.append(block_text)

        return '\n\n'.join(text_blocks)

    def _process_text_block(self, block) -> str:
        """
        处理文本块，保留基本格式
        """
        lines = []
        for line in block['lines']:
            line_text = ''
            for span in line['spans']:
                text = span['text']
                # 根据字体大小和样式判断是否需要特殊标记
                fontsize = span['size']
                flags = span.get('flags', 0)

                # 粗体检测
                if flags & 2**4:  # bit 4 indicates bold
                    text = f'**{text}**'

                # 斜体检测
                if flags & 2**1:  # bit 1 indicates italic
                    text = f'*{text}*'

                line_text += text

            lines.append(line_text)

        return '\n'.join(lines)

    def _extract_tables(self, page) -> List[str]:
        """
        提取页面中的表格并转换为Markdown格式
        """
        tables = []

        # 使用PyMuPDF的表格提取功能
        try:
            # 查找表格
            tabs = page.find_tables()
            for tab in tabs:
                # 提取表格数据
                table_data = tab.extract()
                if table_data and len(table_data) > 0:
                    # 转换为Markdown表格
                    markdown_table = self._convert_table_to_markdown(table_data)
                    tables.append(markdown_table)
        except Exception as e:
            logging.warning(f'表格提取错误: {e}')
            # 备用方案：尝试手动识别表格区域
            tables.extend(self._manual_table_extraction(page))

        return tables

    def _convert_table_to_markdown(self, table_data: List[List]) -> str:
        """
        将表格数据转换为Markdown格式
        """
        if not table_data or not table_data[0]:
            return ''

        # 清理表格数据，处理单元格内的多行文本
        cleaned_data = []
        for row in table_data:
            if row:  # 跳过空行
                # 处理每个单元格，将多行文本合并为单行
                cleaned_row = []
                for cell in row:
                    if cell is not None:
                        # 将单元格内的换行符替换为空格，合并多行文本
                        cell_text = str(cell).strip()
                        # 将多个连续的空白字符（包括换行符）替换为单个空格
                        cell_text = re.sub(r'\s+', ' ', cell_text)
                        cleaned_row.append(cell_text)
                    else:
                        cleaned_row.append('')
                cleaned_data.append(cleaned_row)

        if not cleaned_data:
            return ''

        # 创建Markdown表格
        markdown_lines = []

        # 表头
        header = '| ' + ' | '.join(cleaned_data[0]) + ' |'
        markdown_lines.append(header)

        # 分隔线
        separator = '| ' + ' | '.join(['---'] * len(cleaned_data[0])) + ' |'
        markdown_lines.append(separator)

        # 数据行
        for row in cleaned_data[1:]:
            data_row = '| ' + ' | '.join(row) + ' |'
            markdown_lines.append(data_row)

        return '\n'.join(markdown_lines)

    def _manual_table_extraction(self, page) -> List[str]:
        """
        手动表格提取备用方案
        """
        # 这里可以实现更复杂的表格识别逻辑
        # 例如基于文本位置和间距分析
        return []

    def _clean_and_optimize_markdown(self, markdown: str) -> str:
        """
        清理和优化Markdown内容
        """
        # 移除多余的空白行
        markdown = re.sub(r'\n{3,}', '\n\n', markdown)

        # 修复常见的格式问题
        markdown = re.sub(r'\*\* +', '**', markdown)  # 修复粗体格式
        markdown = re.sub(r' +\*\*', '**', markdown)
        markdown = re.sub(r'\* +', '*', markdown)  # 修复斜体格式
        markdown = re.sub(r' +\*', '*', markdown)

        # 清理行首行尾空格
        lines = markdown.split('\n')
        cleaned_lines = [line.strip() for line in lines]
        markdown = '\n'.join(cleaned_lines)

        return markdown.strip()


# 高级版本：针对长文档优化
class AdvancedPDFToMarkdownConverter(PDFToMarkdownConverter):
    def __init__(self, preserve_headers=True, detect_lists=True):
        super().__init__()
        self.preserve_headers = preserve_headers
        self.detect_lists = detect_lists
        # 存储页面上已识别的表格区域，避免将表格内容当作普通文本处理
        self.table_bboxes = []
        self.current_page_num = 0

    def _process_page(self, page_num: int) -> str:
        """
        重写处理页面的方法，先识别表格区域
        """
        self.current_page_num = page_num
        page = self.document[page_num]  # type: ignore
        content_parts = []

        # 清空上一页的表格边界框
        self.table_bboxes = []

        # 先识别表格区域
        try:
            tabs = page.find_tables()  # type: ignore
            for tab in tabs:
                self.table_bboxes.append(tab.bbox)
        except Exception as e:
            logging.warning(f'表格区域识别错误: {e}')

        # 提取文本内容
        text_content = self._extract_text_with_formatting(page)
        if text_content.strip():
            content_parts.append(text_content)

        # 提取表格
        tables = self._extract_tables(page)
        for table in tables:
            content_parts.append(table)

        return '\n\n'.join(content_parts)

    def _is_in_table(self, block) -> bool:
        """
        判断文本块是否在表格区域内
        """
        # 获取文本块的边界框
        if 'bbox' not in block:
            return False

        block_bbox = block['bbox']

        # 检查文本块是否在任何已知的表格区域内
        for table_bbox in self.table_bboxes:
            # 简单的边界框包含检查
            if (
                block_bbox[0] >= table_bbox[0]
                and block_bbox[1] >= table_bbox[1]
                and block_bbox[2] <= table_bbox[2]
                and block_bbox[3] <= table_bbox[3]
            ):
                return True

        return False

    def _extract_text_with_formatting(self, page) -> str:
        """
        为第一页（封面页）使用特殊的文本提取方法，其他页面使用原有方法
        """
        if self.current_page_num == 0:  # 第一页使用words方法
            # 使用words方法提取文本，能更好地保持文本结构
            words = page.get_text('words')  # type: ignore
            text_content = self._process_words_to_text(words)
            return text_content
        else:
            # 其他页面使用原有的dict方法
            return super()._extract_text_with_formatting(page)

    def _process_words_to_text(self, words):
        """
        将提取的单词列表转换为文本（专门用于第一页）
        """
        if not words:
            return ''

        # 按照页面上的位置排序单词
        words.sort(key=lambda w: (w[1], w[0]))  # 按y坐标然后x坐标排序

        lines = []
        current_line = []
        current_y = words[0][1] if words else 0

        for word in words:
            x0, y0, x1, y1, word_text, block_no, line_no, word_no = word

            # 如果y坐标变化较大，认为是新行
            if abs(y0 - current_y) > 5:  # 阈值可以根据需要调整
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word_text]
                current_y = y0
            else:
                current_line.append(word_text)

        # 添加最后一行
        if current_line:
            lines.append(' '.join(current_line))

        # 处理标题和格式
        formatted_lines = []
        for line in lines:
            formatted_line = line
            # 可以在这里添加额外的格式处理逻辑

            # 列表检测
            if self.detect_lists and formatted_line.strip().startswith(
                ('•', '⁃', '-', '*', '·')
            ):
                formatted_line = formatted_line.replace('•', '-', 1)
                formatted_line = formatted_line.replace('⁃', '-', 1)
                formatted_line = formatted_line.replace('*', '-', 1)
                formatted_line = formatted_line.replace('·', '-', 1)
                formatted_line = f'- {formatted_line.strip()[1:].strip()}'

            # 数字列表检测
            if self.detect_lists and re.match(r'^\d+[\.\)]', formatted_line.strip()):
                formatted_line = formatted_line.strip()

            formatted_lines.append(formatted_line)

        return '\n'.join(formatted_lines)

    def _process_text_block(self, block) -> str:
        """
        增强的文本块处理，支持标题检测和列表识别，并避免处理表格内的文本
        """
        # 如果文本块在表格区域内，则跳过处理（因为表格会单独处理）
        if self._is_in_table(block):
            return ''  # 表格区域的文本由表格提取功能处理

        lines = []
        for line in block['lines']:
            line_text = ''
            spans = line['spans']

            # 处理一行中的所有span，保持它们的顺序和连接
            for i, span in enumerate(spans):
                text = span['text']
                if not text:
                    continue

                fontsize = span['size']
                flags = span.get('flags', 0)

                # 标题检测（基于字体大小）
                if self.preserve_headers and fontsize > 14:
                    # 根据字体大小确定标题级别
                    if fontsize >= 20:
                        text = f'# {text}'
                    elif fontsize >= 18:
                        text = f'## {text}'
                    elif fontsize >= 16:
                        text = f'### {text}'
                    else:
                        text = f'#### {text}'
                else:
                    # 普通文本格式化
                    if flags & 2**4:  # 粗体
                        text = f'**{text}**'
                    if flags & 2**1:  # 斜体
                        text = f'*{text}*'

                line_text += text

            # 列表检测（仅对整行文本进行）
            if self.detect_lists and line_text.strip().startswith(
                ('•', '⁃', '-', '*', '·')
            ):
                line_text = line_text.replace('•', '-', 1)
                line_text = line_text.replace('⁃', '-', 1)
                line_text = line_text.replace('*', '-', 1)
                line_text = line_text.replace('·', '-', 1)
                line_text = f'- {line_text.strip()[1:].strip()}'

            # 数字列表检测
            if self.detect_lists and re.match(r'^\d+[\.\)]', line_text.strip()):
                line_text = line_text.strip()

            if line_text.strip():
                lines.append(line_text)

        return '\n'.join(lines)


class PDFProcessor:
    """PDF处理器，根据PDF文档类型选择合适的处理引擎"""

    def __init__(
        self, file_path: str, file_type: str = 'bid', output_dir: str = 'output'
    ):
        """
        初始化PDF处理器

        Args:
            file_path: PDF文件路径
            file_type: 文件类型，"tender"表示招标文件，"bid"表示投标文件
            output_dir: MD文件输出目录，默认为output
        """
        self.file_path = file_path
        self.file_type = file_type  # "tender" or "bid"
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)

        # 确保输出目录存在
        Path(self.output_dir).mkdir(exist_ok=True)

        # 初始化MinerU处理器
        self.mineru_processor = MinerUProcessor(
            output_dir=Path(self.output_dir), temp_dir=Path('temp/mineru')
        )

    def _get_expected_output_paths(self):
        """
        获取预期的输出文件路径（用于检查文件是否已存在）

        Returns:
            tuple: (txt_file_path, md_file_path) 对于招标文件返回txt路径，对于投标文件返回md路径
        """
        file_name = Path(self.file_path).stem
        txt_file_path = os.path.join(self.output_dir, f'{file_name}.txt')
        md_file_path = os.path.join(self.output_dir, f'{file_name}.md')
        return txt_file_path, md_file_path

    def _check_output_exists(self):
        """
        检查输出文件是否已存在

        Returns:
            str or None: 如果文件已存在，返回文件路径；否则返回None
        """
        txt_file_path, md_file_path = self._get_expected_output_paths()

        # 对于招标文件，不再检查txt文件是否存在
        # if self.file_type == "tender":
        #     if os.path.exists(txt_file_path):
        #         self.logger.info(f"招标文件的txt文档已存在，跳过处理: {txt_file_path}")
        #         return txt_file_path
        # 对于投标文件，检查md文件是否存在
        if self.file_type != 'tender':  # 修改条件判断
            if os.path.exists(md_file_path):
                self.logger.info(f'投标文件的md文档已存在，跳过处理: {md_file_path}')
                return md_file_path

        return None

    def process_pdf_to_md(self) -> str:
        """
        根据PDF类型和文件性质选择合适的处理引擎并生成MD文件
        招标文件优先使用PyMuPDF处理，无法处理时使用MinerU
        投标文件强制使用MinerU处理

        Returns:
            str: 生成的MD文件路径
        """
        # 使用锁确保PDF转换不会并行执行
        with pdf_conversion_lock:
            # 首先检查输出文件是否已存在，如果存在则直接返回路径
            existing_file_path = self._check_output_exists()
            if existing_file_path:
                return existing_file_path

            try:
                # 根据文件类型选择处理方式
                if self.file_type == 'tender':
                    # 对于招标文件，优先使用PyMuPDF处理
                    self.logger.info(
                        f'招标文件 {self.file_path} 使用PyMuPDF处理生成MD文件'
                    )
                    md_file_path = self._process_with_pymupdf()
                    self.logger.info(
                        f'招标文件处理完成，生成的MD文件路径: {md_file_path}'
                    )
                    return md_file_path
                else:
                    # 对于投标文件，强制使用MinerU处理
                    self.logger.info(
                        f'投标文件 {self.file_path} 使用MinerU处理生成MD文件'
                    )
                    md_file_path = self.mineru_processor.process_with_mineru(
                        self.file_path,
                        'markdown',
                        True,  # enable_formula
                        True,  # enable_table
                        'ch',  # language
                    )
                    self.logger.info(
                        f'投标文件处理完成，生成的MD文件路径: {md_file_path}'
                    )

                    # 删除质量评估调用，确保即使质量不达标也参与价格分计算

                    return md_file_path

            except Exception as e:
                self.logger.error(f'处理PDF文件时出错: {e}')
                raise

    def _process_tender_to_text(self) -> str:
        """
        处理招标文件生成文本文件（已废弃，改为生成MD文件）

        Returns:
            str: 生成的文本文件路径
        """
        # 直接调用PyMuPDF处理方法生成MD文件
        return self._process_with_pymupdf()

    def _process_with_pymupdf(self) -> str:
        """
        使用PyMuPDF处理PDF并生成MD文件，增强表格处理能力

        Returns:
            str: 生成的MD文件路径
        """
        if not PymuPDF_AVAILABLE or fitz is None:
            raise RuntimeError('PyMuPDF未安装,无法使用此方法')

        try:
            doc = fitz.open(self.file_path)
            file_name = Path(self.file_path).stem
            md_file_path = os.path.join(self.output_dir, f'{file_name}.md')

            # 使用改进的转换器
            converter = AdvancedPDFToMarkdownConverter()
            markdown_content = converter.convert_pdf_to_markdown(
                self.file_path, md_file_path
            )

            # 删除质量评估调用，确保即使质量不达标也参与价格分计算

            return md_file_path
        except Exception as e:
            self.logger.error(f'使用PyMuPDF处理PDF时出错: {e}')
            raise

    def _extract_text_with_enhanced_tables(self, page) -> str:
        """
        提取页面文本并增强表格处理能力

        Args:
            page: PyMuPDF页面对象

        Returns:
            str: 处理后的文本内容
        """
        try:
            # 使用改进的转换器提取文本
            converter = AdvancedPDFToMarkdownConverter()
            # 获取页面的所有文本块
            blocks = page.get_text('dict')
            text_blocks = []

            for block in blocks['blocks']:
                if 'lines' in block:  # 文本块
                    block_text = converter._process_text_block(block)
                    if block_text.strip():
                        text_blocks.append(block_text)

            return '\n\n'.join(text_blocks)
        except Exception as e:
            self.logger.warning(
                f'使用增强表格处理提取文本时出错，回退到简单文本提取: {e}'
            )
            # 回退到简单的文本提取
            try:
                text = page.get_text()  # type: ignore
                return text if text else ''
            except Exception as e2:
                self.logger.error(f'简单文本提取也失败: {e2}')
                return ''

    def _save_to_temp_word(self, pages_text: List[str]) -> None:
        """
        将提取的文本保存到temp_word目录

        Args:
            pages_text: 按页面分割的文本内容
        """
        try:
            # 生成基于文件路径的唯一文件名
            import hashlib

            file_key = hashlib.md5(self.file_path.encode('utf-8')).hexdigest()
            temp_word_filename = f'{file_key}.txt'
            temp_word_dir = 'output'
            temp_word_path = os.path.join(temp_word_dir, temp_word_filename)

            # 确保目录存在
            os.makedirs(temp_word_dir, exist_ok=True)

            # 将所有页面文本合并后保存
            full_text = '\n\n'.join(pages_text)
            with open(temp_word_path, 'w', encoding='utf-8') as f:
                f.write(full_text)

            self.logger.info('文本已保存到temp_word目录: %s', temp_word_path)
        except Exception as e:
            self.logger.warning('保存文本到temp_word目录失败: %s', e)

    def _is_table_block(self, block: dict) -> bool:
        """
        判断文本块是否为表格区域

        Args:
            block: 文本块字典

        Returns:
            bool: 是否为表格区域
        """
        try:
            # 检查块中是否包含多个行，且行中有多个span
            if 'lines' not in block:
                return False

            lines = block['lines']
            if len(lines) < 2:
                return False

            # 检查是否有多行具有相似的span数量（表格特征）
            span_counts = []
            for line in lines:
                if 'spans' in line:
                    span_counts.append(len(line['spans']))

            if len(span_counts) < 2:
                return False

            # 如果大部分行的span数量相同或相近，则可能是表格
            avg_spans = sum(span_counts) / len(span_counts)
            similar_spans = sum(
                1 for count in span_counts if abs(count - avg_spans) <= 1
            )

            # 提高表格识别的准确性：要求至少70%的行具有相似span数量
            result = similar_spans >= len(span_counts) * 0.7
            return result
        except Exception as e:
            self.logger.warning(f'判断表格块时出错: {e}')
            return False

    def _process_table_block(self, block: dict) -> str:
        """
        处理表格块，优化表格格式

        Args:
            block: 表格文本块

        Returns:
            str: 格式化后的表格内容
        """
        try:
            lines = block['lines']
            if not lines:
                return ''

            # 提取表格行数据，保持原始位置信息
            table_rows = []
            for line in lines:
                if 'spans' in line:
                    # 合并同一行中的span文本，保持位置信息
                    row_spans = []
                    for span in line['spans']:
                        # 确保正确处理文本编码
                        span_text = span.get('text', '')
                        if span_text:
                            # 获取span的位置信息
                            bbox = span.get('bbox', [0, 0, 0, 0])
                            row_spans.append({'text': span_text, 'bbox': bbox})
                    # 清理文本
                    if row_spans:
                        table_rows.append(row_spans)

            if not table_rows:
                return ''

            # 智能分割表格列，基于位置信息而不是简单的文本分割
            processed_rows = self._smart_table_column_split(table_rows)

            if not processed_rows:
                # 如果智能分割失败，回退到简单的文本分割
                simple_rows = []
                for row_spans in table_rows:
                    row_text = ''.join([span['text'] for span in row_spans])
                    # 使用正则表达式更好地分割列
                    columns = re.split(r'\s{2,}', row_text)
                    # 清理每列内容
                    columns = [self._clean_cell_content(col) for col in columns]
                    simple_rows.append(columns)
                processed_rows = simple_rows

            if not processed_rows:
                # 如果所有方法都失败，返回原始文本
                raw_lines = []
                for row_spans in table_rows:
                    row_text = ''.join([span['text'] for span in row_spans])
                    raw_lines.append(row_text)
                return '\n'.join(raw_lines)

            # 确定最大列数
            max_cols = max(len(row) for row in processed_rows) if processed_rows else 0
            if max_cols == 0:
                raw_lines = []
                for row_spans in table_rows:
                    row_text = ''.join([span['text'] for span in row_spans])
                    raw_lines.append(row_text)
                return '\n'.join(raw_lines)

            # 格式化为Markdown表格
            formatted_rows = []
            for row in processed_rows:
                # 确保每行都有相同数量的列
                while len(row) < max_cols:
                    row.append('')
                # 格式化为表格行
                formatted_row = '|' + '|'.join([f' {cell} ' for cell in row]) + '|'
                formatted_rows.append(formatted_row)

            # 添加表头分隔行
            if len(formatted_rows) > 1:
                separator = '|' + '|'.join(['---'] * max_cols) + '|'
                # 在第一行后插入分隔行
                formatted_rows.insert(1, separator)

            return '\n'.join(formatted_rows)
        except Exception as e:
            self.logger.warning(f'处理表格块时出错，返回原始文本: {e}')
            # 出错时返回原始文本
            try:
                lines = block.get('lines', [])
                raw_lines = []
                for line in lines:
                    if 'spans' in line:
                        line_text = ''
                        for span in line['spans']:
                            line_text += span.get('text', '')
                        raw_lines.append(line_text)
                return '\n'.join(raw_lines)
            except Exception as e2:
                self.logger.error(f'返回原始文本也失败: {e2}')
                return ''

    def _smart_table_column_split(self, table_rows: list) -> list:
        """
        基于位置信息智能分割表格列

        Args:
            table_rows: 表格行数据，包含位置信息

        Returns:
            list: 分割后的表格行数据
        """
        try:
            if not table_rows:
                return []

            # 收集所有span的位置信息
            all_spans = []
            for row_spans in table_rows:
                for span in row_spans:
                    all_spans.append(span)

            if not all_spans:
                return []

            # 计算列的边界，基于span的x坐标
            x_positions = []
            for span in all_spans:
                bbox = span['bbox']
                # 添加左边界和右边界
                x_positions.extend([bbox[0], bbox[2]])

            if not x_positions:
                return []

            # 对x坐标进行排序和聚类
            x_positions.sort()

            # 简单的聚类方法：将相近的x坐标合并为一列
            column_boundaries = []
            threshold = 20  # 列边界的最小间距阈值

            if x_positions:
                current_boundary = x_positions[0]
                column_boundaries.append(current_boundary)

                for x in x_positions[1:]:
                    if x - current_boundary > threshold:
                        column_boundaries.append(x)
                        current_boundary = x

            if len(column_boundaries) < 2:
                return []

            # 根据列边界分割每一行
            processed_rows = []
            for row_spans in table_rows:
                # 为每一列创建一个空列表
                columns = [[] for _ in range(len(column_boundaries) - 1)]

                # 将span分配到对应的列中
                for span in row_spans:
                    bbox = span['bbox']
                    span_center = (bbox[0] + bbox[2]) / 2

                    # 找到span应该归属的列
                    for i in range(len(column_boundaries) - 1):
                        if (
                            column_boundaries[i]
                            <= span_center
                            < column_boundaries[i + 1]
                        ):
                            columns[i].append(span['text'])
                            break

                # 合并每列中的文本
                row_text = [''.join(column) for column in columns]
                # 清理每列内容
                row_text = [self._clean_cell_content(col) for col in row_text]
                processed_rows.append(row_text)

            return processed_rows
        except Exception as e:
            self.logger.warning(f'智能表格列分割时出错: {e}')
            return []

    def _clean_cell_content(self, content: str) -> str:
        """
        清理单元格内容，去除多余的换行和空格，智能保留表格结构

        Args:
            content: 单元格原始内容

        Returns:
            str: 清理后的内容
        """
        try:
            if not content:
                return ''

            # 去除首尾空白字符
            content = content.strip()

            # 将多个连续的空白字符（包括换行符）替换为单个空格
            # 但在表格环境中，我们需要更智能地处理
            content = re.sub(r'[ \t]+', ' ', content)  # 替换多个空格和制表符为单个空格
            content = re.sub(r'\n\s*\n', '\n', content)  # 替换多个换行符为单个换行符

            # 去除行首行尾的换行符，但保留行内的换行符（表格单元格中的换行）
            content = content.strip('\n')

            return content
        except Exception as e:
            self.logger.warning(f'清理单元格内容时出错，返回原始内容: {e}')
            return content if content else ''

    def _extract_block_text(self, block: dict) -> str:
        """
        提取普通文本块的内容

        Args:
            block: 文本块字典

        Returns:
            str: 提取的文本内容
        """
        if 'lines' in block:
            lines = []
            for line in block['lines']:
                if 'spans' in line:
                    line_text = ''
                    for span in line['spans']:
                        # 确保正确处理文本编码
                        span_text = span.get('text', '')
                        if span_text:
                            # 根据字体大小和样式判断是否需要特殊标记
                            fontsize = span.get('size', 12)
                            flags = span.get('flags', 0)

                            # 粗体检测
                            if flags & 2**4:  # bit 4 indicates bold
                                span_text = f'**{span_text}**'

                            # 斜体检测
                            if flags & 2**1:  # bit 1 indicates italic
                                span_text = f'*{span_text}*'

                            line_text += span_text
                    lines.append(line_text)
            return '\n'.join(lines)
        elif 'image' in block:
            # 对于图像块，尝试提取其中的文本内容而不是简单返回[图像]
            if 'blocks' in block.get('image', {}):
                # 如果图像块中有文本内容，提取它
                image_text = ''
                for img_block in block['image']['blocks']:
                    if 'lines' in img_block:
                        for line in img_block['lines']:
                            if 'spans' in line:
                                for span in line['spans']:
                                    image_text += span.get('text', '')
                return image_text if image_text else ''
            return ''
        else:
            return ''

    def get_md_file_path(self) -> str:
        """
        获取对应的MD文件路径

        Returns:
            str: MD文件路径
        """
        # 生成MD文件路径
        pdf_filename = os.path.basename(self.file_path)
        file_key = os.path.splitext(pdf_filename)[0]
        md_filename = f'{file_key}.md'

        # MD文件存放在temp/md目录下
        md_file_path = os.path.join(self.output_dir, md_filename)

        return md_file_path

    def load_content_from_md_file(self) -> Optional[List[str]]:
        """
        从MD文件中加载内容并转换为页面列表格式

        Returns:
            Optional[List[str]]: 页面内容列表，如果加载失败则返回None
        """
        try:
            md_file_path = self.get_md_file_path()

            if not os.path.exists(md_file_path):
                self.logger.warning(f'MD文件不存在: {md_file_path}')
                return None

            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按页面分隔符分割内容
            pages = content.split('\n\n---\n\n')
            self.logger.info(f'从MD文件 {md_file_path} 加载了 {len(pages)} 页内容')
            return pages
        except Exception as e:
            self.logger.error(f'从MD文件加载内容时出错: {e}')
            return None

    def extract_text_per_page(self, use_cache: bool = True) -> List[str]:
        """
        提取PDF每页的文本内容

        Args:
            use_cache: 是否使用缓存

        Returns:
            List[str]: 每页的文本内容列表
        """
        # 根据文件类型采用不同的处理方式
        if self.file_type == 'tender':
            # 招标文件：检查是否已存在txt文件
            txt_file_path, _ = self._get_expected_output_paths()
            if os.path.exists(txt_file_path):
                # 从已存在的文本文件加载内容
                return self.load_content_from_text_file(txt_file_path)
            else:
                # 生成文本文件
                txt_file_path = self.process_pdf_to_md()
                # 从文本文件加载内容
                return self.load_content_from_text_file(txt_file_path)
        else:
            # 投标文件：检查是否已存在md文件
            _, md_file_path = self._get_expected_output_paths()
            if os.path.exists(md_file_path):
                # 从已存在的MD文件加载内容
                pages_content = self._load_content_from_existing_md_file(md_file_path)
            else:
                # 首先确保PDF已处理为MD文件
                self.process_pdf_to_md()
                # 从MD文件加载内容
                pages_content = self.load_content_from_md_file()

            if pages_content is not None:
                return pages_content
            else:
                self.logger.warning('未能从MD文件加载内容，返回空列表')
                return []

    def _load_content_from_existing_md_file(
        self, md_file_path: str
    ) -> Optional[List[str]]:
        """
        从已存在的MD文件中加载内容并转换为页面列表格式

        Args:
            md_file_path: MD文件路径

        Returns:
            Optional[List[str]]: 页面内容列表，如果加载失败则返回None
        """
        try:
            if not os.path.exists(md_file_path):
                self.logger.warning(f'MD文件不存在: {md_file_path}')
                return None

            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按页面分隔符分割内容
            pages = content.split('\n\n---\n\n')
            self.logger.info(
                f'从已存在的MD文件 {md_file_path} 加载了 {len(pages)} 页内容'
            )
            return pages
        except Exception as e:
            self.logger.error(f'从已存在的MD文件加载内容时出错: {e}')
            return None

    def load_content_from_text_file(self, txt_file_path: str) -> List[str]:
        """
        从文本文件中加载内容并转换为页面列表格式

        Args:
            txt_file_path: 文本文件路径

        Returns:
            List[str]: 页面内容列表
        """
        try:
            if not os.path.exists(txt_file_path):
                self.logger.warning(f'文本文件不存在: {txt_file_path}')
                return []

            with open(txt_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按页面分隔符分割内容
            pages = content.split('\n\n--- Page ')
            # 处理第一页（没有"--- Page "前缀）
            if pages:
                first_page = pages[0]
                if first_page.startswith('--- Page '):
                    # 如果第一页也有前缀，需要特殊处理
                    pages[0] = first_page
                else:
                    # 第一页正常处理
                    pass

            # 清理每页内容，移除页码行
            cleaned_pages = []
            for page in pages:
                lines = page.split('\n')
                # 过滤掉页码行
                cleaned_lines = [
                    line for line in lines if not line.startswith('--- Page ')
                ]
                cleaned_pages.append('\n'.join(cleaned_lines))

            self.logger.info(
                f'从文本文件 {txt_file_path} 加载了 {len(cleaned_pages)} 页内容'
            )
            return cleaned_pages
        except Exception as e:
            self.logger.error(f'从文本文件加载内容时出错: {e}')
            return []
