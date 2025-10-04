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
from typing import List, Optional
from pathlib import Path

# 尝试导入PyMuPDF
try:
    import fitz  # PyMuPDF
    PymuPDF_AVAILABLE = True
except ImportError:
    PymuPDF_AVAILABLE = False
    fitz = None
    logging.warning('PyMuPDF (fitz) 未安装')

from .advanced_pdf_processor import MinerUProcessor

class PDFProcessor:
    """PDF处理器，根据PDF文档类型选择合适的处理引擎"""

    def __init__(self, file_path: str, output_dir: str = "temp/md"):
        """
        初始化PDF处理器

        Args:
            file_path: PDF文件路径
            output_dir: MD文件输出目录，默认为temp/md
        """
        self.file_path = file_path
        self.output_dir = output_dir
        self.logger = logging.getLogger(__name__)
        
        # 确保输出目录存在
        Path(self.output_dir).mkdir(exist_ok=True)
        
        # 初始化MinerU处理器
        self.mineru_processor = MinerUProcessor(
            output_dir=Path(self.output_dir),
            temp_dir=Path("temp_mineru")
        )

    def _is_pdf_editable_and_searchable(self) -> bool:
        """
        判断PDF是否可编辑可搜索

        Returns:
            bool: 如果PDF可编辑可搜索返回True，否则返回False
        """
        if not PymuPDF_AVAILABLE or fitz is None:
            return False
            
        try:
            doc = fitz.open(self.file_path)
            total_chars = 0
            total_pages = min(5, len(doc))  # 只检查前5页
            
            for i in range(total_pages):
                page = doc.load_page(i)
                text = page.get_text()
                total_chars += len(text)
                
            doc.close()
            
            # 如果平均每页字符数超过100，则认为是可编辑可搜索的PDF
            avg_chars_per_page = total_chars / total_pages if total_pages > 0 else 0
            return avg_chars_per_page > 100
        except Exception as e:
            self.logger.warning(f"判断PDF是否可编辑可搜索时出错: {e}")
            return False

    def process_pdf_to_md(self) -> str:
        """
        根据PDF类型选择合适的处理引擎并生成MD文件

        Returns:
            str: 生成的MD文件路径
        """
        try:
            # 判断PDF是否可编辑可搜索
            if self._is_pdf_editable_and_searchable():
                self.logger.info(f"PDF文件 {self.file_path} 是可编辑可搜索的，使用PyMuPDF处理")
                md_file_path = self._process_with_pymupdf()
            else:
                self.logger.info(f"PDF文件 {self.file_path} 是不可编辑不可搜索的，使用MinerU处理")
                md_file_path = self.mineru_processor.process_with_mineru(
                    pdf_path=self.file_path,
                    output_format='markdown',
                    enable_formula=True,
                    enable_table=True,
                    language='ch'
                )
            
            self.logger.info(f"PDF处理完成，生成的MD文件路径: {md_file_path}")
            return md_file_path
            
        except Exception as e:
            self.logger.error(f"处理PDF文件时出错: {e}")
            raise

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
            md_file_path = os.path.join(self.output_dir, f"{file_name}.md")
            
            with open(md_file_path, 'w', encoding='utf-8') as f:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    
                    # 使用更精确的文本提取方法来处理表格
                    text = self._extract_text_with_enhanced_tables(page)
                    
                    # 写入页面分隔符
                    if page_num > 0:
                        f.write('\n\n---\n\n')
                    
                    f.write(text)
            
            doc.close()
            return md_file_path
        except Exception as e:
            self.logger.error(f"使用PyMuPDF处理PDF时出错: {e}")
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
            # 尝试使用多种方法提取文本
            # 首先使用"rawdict"模式
            blocks = page.get_text("rawdict")
            content_parts = []
            
            # 如果rawdict没有blocks，尝试使用"dict"模式
            if "blocks" not in blocks or not blocks["blocks"]:
                blocks = page.get_text("dict")
                
            if "blocks" in blocks and blocks["blocks"]:
                for block in blocks["blocks"]:
                    if "lines" in block:  # 文本块
                        # 检查是否是表格区域
                        if self._is_table_block(block):
                            # 处理表格块
                            table_content = self._process_table_block(block)
                            content_parts.append(table_content)
                        else:
                            # 普通文本块处理
                            block_text = self._extract_block_text(block)
                            content_parts.append(block_text)
                    else:
                        # 其他类型的块（如图像）
                        block_text = self._extract_block_text(block)
                        content_parts.append(block_text)
                
                return "\n\n".join(content_parts)
            else:
                # 如果结构化提取失败，回退到简单的文本提取
                text = page.get_text()
                return text if text else ""
        except Exception as e:
            self.logger.warning(f"使用增强表格处理提取文本时出错，回退到简单文本提取: {e}")
            # 回退到简单的文本提取
            try:
                text = page.get_text()
                return text if text else ""
            except Exception as e2:
                self.logger.error(f"简单文本提取也失败: {e2}")
                return ""

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
            if "lines" not in block:
                return False
                
            lines = block["lines"]
            if len(lines) < 2:
                return False
                
            # 检查是否有多行具有相似的span数量（表格特征）
            span_counts = []
            for line in lines:
                if "spans" in line:
                    span_counts.append(len(line["spans"]))
            
            if len(span_counts) < 2:
                return False
                
            # 如果大部分行的span数量相同或相近，则可能是表格
            avg_spans = sum(span_counts) / len(span_counts)
            similar_spans = sum(1 for count in span_counts if abs(count - avg_spans) <= 1)
            
            # 提高表格识别的准确性：要求至少70%的行具有相似span数量
            result = similar_spans >= len(span_counts) * 0.7
            return result
        except Exception as e:
            self.logger.warning(f"判断表格块时出错: {e}")
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
            lines = block["lines"]
            if not lines:
                return ""
                
            # 提取表格行数据，保持原始位置信息
            table_rows = []
            for line in lines:
                if "spans" in line:
                    # 合并同一行中的span文本，保持位置信息
                    row_spans = []
                    for span in line["spans"]:
                        # 确保正确处理文本编码
                        span_text = span.get("text", "")
                        if span_text:
                            # 获取span的位置信息
                            bbox = span.get("bbox", [0, 0, 0, 0])
                            row_spans.append({
                                "text": span_text,
                                "bbox": bbox
                            })
                    # 清理文本
                    if row_spans:
                        table_rows.append(row_spans)
            
            if not table_rows:
                return ""
                
            # 智能分割表格列，基于位置信息而不是简单的文本分割
            processed_rows = self._smart_table_column_split(table_rows)
            
            if not processed_rows:
                # 如果智能分割失败，回退到简单的文本分割
                simple_rows = []
                for row_spans in table_rows:
                    row_text = "".join([span["text"] for span in row_spans])
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
                    row_text = "".join([span["text"] for span in row_spans])
                    raw_lines.append(row_text)
                return "\n".join(raw_lines)
                
            # 确定最大列数
            max_cols = max(len(row) for row in processed_rows) if processed_rows else 0
            if max_cols == 0:
                raw_lines = []
                for row_spans in table_rows:
                    row_text = "".join([span["text"] for span in row_spans])
                    raw_lines.append(row_text)
                return "\n".join(raw_lines)
                
            # 格式化为Markdown表格
            formatted_rows = []
            for row in processed_rows:
                # 确保每行都有相同数量的列
                while len(row) < max_cols:
                    row.append("")
                # 格式化为表格行
                formatted_row = "|" + "|".join([f" {cell} " for cell in row]) + "|"
                formatted_rows.append(formatted_row)
            
            # 添加表头分隔行
            if len(formatted_rows) > 1:
                separator = "|" + "|".join(["---"] * max_cols) + "|"
                # 在第一行后插入分隔行
                formatted_rows.insert(1, separator)
            
            return "\n".join(formatted_rows)
        except Exception as e:
            self.logger.warning(f"处理表格块时出错，返回原始文本: {e}")
            # 出错时返回原始文本
            try:
                lines = block.get("lines", [])
                raw_lines = []
                for line in lines:
                    if "spans" in line:
                        line_text = ""
                        for span in line["spans"]:
                            line_text += span.get("text", "")
                        raw_lines.append(line_text)
                return "\n".join(raw_lines)
            except Exception as e2:
                self.logger.error(f"返回原始文本也失败: {e2}")
                return ""

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
                bbox = span["bbox"]
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
                    bbox = span["bbox"]
                    span_center = (bbox[0] + bbox[2]) / 2
                    
                    # 找到span应该归属的列
                    for i in range(len(column_boundaries) - 1):
                        if column_boundaries[i] <= span_center < column_boundaries[i + 1]:
                            columns[i].append(span["text"])
                            break
                            
                # 合并每列中的文本
                row_text = ["".join(column) for column in columns]
                # 清理每列内容
                row_text = [self._clean_cell_content(col) for col in row_text]
                processed_rows.append(row_text)
                
            return processed_rows
        except Exception as e:
            self.logger.warning(f"智能表格列分割时出错: {e}")
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
                return ""
                
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
            self.logger.warning(f"清理单元格内容时出错，返回原始内容: {e}")
            return content if content else ""

    def _extract_block_text(self, block: dict) -> str:
        """
        提取普通文本块的内容

        Args:
            block: 文本块字典

        Returns:
            str: 提取的文本内容
        """
        if "lines" in block:
            lines = []
            for line in block["lines"]:
                if "spans" in line:
                    line_text = ""
                    for span in line["spans"]:
                        # 确保正确处理文本编码
                        span_text = span.get("text", "")
                        if span_text:
                            line_text += span_text
                    lines.append(line_text)
            return "\n".join(lines)
        elif "image" in block:
            return "[图像]"
        else:
            return ""

    def get_md_file_path(self) -> str:
        """
        获取对应的MD文件路径

        Returns:
            str: MD文件路径
        """
        # 生成MD文件路径
        pdf_filename = os.path.basename(self.file_path)
        file_key = os.path.splitext(pdf_filename)[0]
        md_filename = f"{file_key}.md"
        
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
                self.logger.warning(f"MD文件不存在: {md_file_path}")
                return None
                
            with open(md_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 按页面分隔符分割内容
            pages = content.split('\n\n---\n\n')
            self.logger.info(f"从MD文件 {md_file_path} 加载了 {len(pages)} 页内容")
            return pages
        except Exception as e:
            self.logger.error(f"从MD文件加载内容时出错: {e}")
            return None

    def extract_text_per_page(self, use_cache: bool = True) -> List[str]:
        """
        提取PDF每页的文本内容

        Args:
            use_cache: 是否使用缓存

        Returns:
            List[str]: 每页的文本内容列表
        """
        # 首先确保PDF已处理为MD文件
        self.process_pdf_to_md()
        
        # 从MD文件加载内容
        pages_content = self.load_content_from_md_file()
        
        if pages_content is not None:
            return pages_content
        else:
            self.logger.warning("未能从MD文件加载内容，返回空列表")
            return []
