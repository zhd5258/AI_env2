#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
表格分析模块
用于处理PDF中的表格数据，特别是跨页表格的识别和合并
"""

import json
import logging
import sys
import os
from typing import List, Dict, Any

# 添加项目根目录到Python路径，解决导入问题
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入项目模块
try:
    from modules.pdf_processor import PDFProcessor
except ImportError:
    try:
        from pdf_processor import PDFProcessor
    except ImportError:
        PDFProcessor = None

import pdfplumber


class TableAnalyzer:
    """表格分析器，用于处理PDF中的表格数据"""

    def __init__(self, pdf_path: str):
        self.pdf_path = pdf_path
        self.logger = logging.getLogger(__name__)
        # 定义需要保留的表头关键词
        self.target_headers = ['评价项目', '评价标准']

    def extract_and_merge_tables(self) -> List[Dict[str, Any]]:
        """
        提取并合并跨页表格

        Returns:
            List[Dict]: 合并后的表格列表
        """
        try:
            # 首先提取所有页面的原始表格数据
            all_tables = self._extract_all_tables()

            # 然后智能合并跨页表格
            merged_tables = self._merge_cross_page_tables(all_tables)

            # 过滤出包含目标表头的表格
            filtered_tables = self._filter_target_tables(merged_tables)

            return filtered_tables
        except Exception as e:
            self.logger.error(f'提取表格时出错: {e}')
            return []

    def _extract_all_tables(self) -> List[Dict]:
        """
        提取所有页面的原始表格数据

        Returns:
            List[Dict]: 所有表格信息列表
        """
        tables_info = []

        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    try:
                        tables = page.extract_tables()
                        for table_index, table in enumerate(tables):
                            if table and len(table) > 0:
                                # 基本信息
                                rows = len(table)
                                cols = max(len(row) for row in table) if table else 0
                                headers = table[0] if table else []

                                tables_info.append(
                                    {
                                        'page': page_num,
                                        'table_index': table_index,
                                        'rows': rows,
                                        'cols': cols,
                                        'headers': headers,
                                        'data': table,
                                    }
                                )
                    except Exception as page_e:
                        self.logger.warning(f'处理第{page_num}页表格时出错: {page_e}')
                        continue
        except Exception as e:
            self.logger.error(f'使用pdfplumber提取表格时出错: {e}')

        return tables_info

    def _merge_cross_page_tables(self, all_tables: List[Dict]) -> List[Dict]:
        """
        合并跨页表格

        Args:
            all_tables: 所有原始表格信息列表

        Returns:
            List[Dict]: 合并后的表格列表
        """
        if not all_tables:
            return []

        merged_tables = []
        i = 0

        while i < len(all_tables):
            current_table = all_tables[i]
            # 从当前表格开始，查找可能的连续表格
            continuous_tables = [current_table]
            j = i + 1

            # 查找连续的表格
            while j < len(all_tables):
                next_table = all_tables[j]

                # 判断是否为连续表格
                if self._is_continuous_table(current_table, next_table):
                    continuous_tables.append(next_table)
                    current_table = next_table
                    j += 1
                else:
                    break

            # 合并连续的表格
            merged_table = self._merge_continuous_tables(continuous_tables)
            merged_tables.append(merged_table)

            i = j

        return merged_tables

    def _is_continuous_table(self, table1: Dict, table2: Dict) -> bool:
        """
        判断两个表格是否为连续表格（跨页）

        Args:
            table1: 第一个表格
            table2: 第二个表格

        Returns:
            bool: 是否为连续表格
        """
        # 1. 必须是连续页面
        if table2['page'] != table1['page'] + 1:
            return False

        # 2. 列数必须相同
        if table1['cols'] != table2['cols']:
            return False

        # 3. 表头结构相似度
        header_similarity = self._calculate_header_similarity(
            table1['headers'], table2['headers']
        )

        # 4. 内容结构相似度（非空单元格数量）
        content_similarity = self._calculate_content_similarity(
            table1['data'], table2['data']
        )

        # 如果表头相似度高或者内容结构相似度高，则认为是连续表格
        return header_similarity > 0.6 or content_similarity > 0.7

    def _calculate_content_similarity(
        self, table1_data: List[List], table2_data: List[List]
    ) -> float:
        """
        计算表格内容结构相似度

        Args:
            table1_data: 第一个表格数据
            table2_data: 第二个表格数据

        Returns:
            float: 相似度 (0-1)
        """
        if not table1_data or not table2_data:
            return 0.0

        # 计算每行非空单元格数量
        non_empty_counts1 = [sum(1 for cell in row if cell) for row in table1_data]
        non_empty_counts2 = [sum(1 for cell in row if cell) for row in table2_data]

        # 计算平均非空单元格数量
        avg1 = (
            sum(non_empty_counts1) / len(non_empty_counts1) if non_empty_counts1 else 0
        )
        avg2 = (
            sum(non_empty_counts2) / len(non_empty_counts2) if non_empty_counts2 else 0
        )

        # 计算相似度（基于平均值差异）
        if avg1 == 0 and avg2 == 0:
            return 1.0
        elif avg1 == 0 or avg2 == 0:
            return 0.0
        else:
            diff = abs(avg1 - avg2) / max(avg1, avg2)
            return 1.0 - diff

    def _merge_continuous_tables(self, continuous_tables: List[Dict]) -> Dict:
        """
        合并连续的表格

        Args:
            continuous_tables: 连续的表格列表

        Returns:
            Dict: 合并后的表格
        """
        if not continuous_tables:
            return {}

        # 以第一个表格为基准
        base_table = continuous_tables[0]

        # 合并所有表格数据
        merged_data = []
        all_pages = []

        for i, table in enumerate(continuous_tables):
            all_pages.append(table['page'])

            if i == 0:
                # 第一个表格保留所有行
                cleaned_data = []
                for row in table['data']:
                    cleaned_row = [
                        self._clean_text(str(cell)) if cell is not None else ''
                        for cell in row
                    ]
                    cleaned_data.append(cleaned_row)
                merged_data.extend(cleaned_data)
            else:
                # 后续表格去掉表头行（假设第一行为表头）
                table_data = table['data']
                if len(table_data) > 1:
                    data_rows = table_data[1:]  # 去掉表头行
                    cleaned_data = []
                    for row in data_rows:
                        cleaned_row = [
                            self._clean_text(str(cell)) if cell is not None else ''
                            for cell in row
                        ]
                        cleaned_data.append(cleaned_row)
                    merged_data.extend(cleaned_data)

        # 清理表头
        cleaned_headers = [
            self._clean_text(str(h)) if h is not None else ''
            for h in base_table['headers']
        ]

        # 创建合并后的表格
        merged_table = {
            'start_page': min(all_pages),
            'end_page': max(all_pages),
            'pages': all_pages,
            'page_count': len(all_pages),
            'total_rows': len(merged_data),
            'cols': base_table['cols'],
            'headers': cleaned_headers,
            'data': merged_data,
        }

        return merged_table

    def _calculate_header_similarity(self, headers1: List, headers2: List) -> float:
        """
        计算表头相似度

        Args:
            headers1: 第一个表头
            headers2: 第二个表头

        Returns:
            float: 相似度 (0-1)
        """
        if not headers1 or not headers2:
            return 0.0

        max_len = max(len(headers1), len(headers2))
        matches = 0

        for i in range(min(len(headers1), len(headers2))):
            h1 = str(headers1[i]).strip() if headers1[i] else ''
            h2 = str(headers2[i]).strip() if headers2[i] else ''

            if h1 and h2:
                # 字符串包含关系或完全相等
                if h1 == h2 or h1 in h2 or h2 in h1:
                    matches += 1
            elif h1 == h2:  # 都为空
                matches += 1
            # 处理None值的情况
            elif h1 == '' and h2 == '':
                matches += 1

        return matches / max_len if max_len > 0 else 0.0

    def _filter_target_tables(self, merged_tables: List[Dict]) -> List[Dict]:
        """
        过滤出包含目标表头的表格

        Args:
            merged_tables: 合并后的表格列表

        Returns:
            List[Dict]: 包含目标表头的表格列表
        """
        target_tables = []

        for table in merged_tables:
            headers = table['headers']
            # 检查是否包含目标表头
            if self._contains_target_headers(headers):
                target_tables.append(table)

        return target_tables

    def _contains_target_headers(self, headers: List[str]) -> bool:
        """
        检查表头是否包含目标关键词

        Args:
            headers: 表头列表

        Returns:
            bool: 是否包含目标表头
        """
        if not headers:
            return False

        # 清理表头文本
        cleaned_headers = [
            self._clean_text(str(h)) if h is not None else '' for h in headers
        ]

        # 检查是否包含所有目标关键词
        for target_header in self.target_headers:
            found = False
            for header in cleaned_headers:
                if target_header in header:
                    found = True
                    break
            if not found:
                return False

        return True

    def convert_to_structured_format(self, merged_tables: List[Dict]) -> List[Dict]:
        """
        将合并后的表格转换为结构化格式（仅包含表头和行数据）

        Args:
            merged_tables: 合并后的表格列表

        Returns:
            List[Dict]: 结构化表格列表（不包含metadata）
        """
        structured_tables = []

        for table_info in merged_tables:
            headers = table_info['headers']
            data = table_info['data']

            # 转换为键值对格式
            rows = []
            if len(data) > 1:
                data_rows = data[1:]  # 跳过表头行
                for row in data_rows:
                    # 确保行数据和表头长度一致
                    if len(row) == len(headers):
                        # 处理可能的None值并清理文本，同时去除多余空格
                        row_dict = {}
                        for i, (header, cell) in enumerate(zip(headers, row)):
                            # 清理文本并去除多余空格
                            cleaned_cell = (
                                self._clean_text_and_spaces(str(cell))
                                if cell is not None
                                else ''
                            )
                            row_dict[header] = cleaned_cell
                        rows.append(row_dict)
                    else:
                        # 如果长度不一致，创建一个通用的字典
                        row_dict = {}
                        for i, cell in enumerate(row):
                            header = (
                                f'column_{i}'
                                if i >= len(headers)
                                else headers[i]
                                if i < len(headers) and headers[i]
                                else f'column_{i}'
                            )
                            # 清理文本并去除多余空格
                            cleaned_cell = (
                                self._clean_text_and_spaces(str(cell))
                                if cell is not None
                                else ''
                            )
                            row_dict[header] = cleaned_cell
                        rows.append(row_dict)

            # 只保留表头和行数据，不包含metadata
            structured_table = {
                'headers': headers,
                'rows': rows,
            }

            structured_tables.append(structured_table)

        return structured_tables

    def _clean_text_and_spaces(self, text: str) -> str:
        """
        清理文本中的换行符并去除所有空格以提高可读性

        Args:
            text: 需要清理的文本

        Returns:
            str: 清理后的文本
        """
        if not text:
            return ''

        # 替换各种换行符和制表符为空格
        text = (
            text.replace('\r\n', ' ')
            .replace('\n', ' ')
            .replace('\r', ' ')
            .replace('\t', ' ')
        )

        # 处理特殊Unicode字符
        text = text.replace('\u2029', ' ').replace('\u2028', ' ').replace('\u00a0', ' ')

        # 处理其他可能的空白字符
        import re

        # 匹配所有Unicode空白字符并替换为空格
        text = re.sub(
            r'[\x00-\x20\x7f-\xa0\u2000-\u200f\u2028-\u202f\u205f-\u206f\u3000\ufeff]+',
            ' ',
            text,
        )

        # 去除所有空格
        text = text.replace(' ', '')

        # 去除首尾空格（虽然已经没有空格了，但为了保险起见）
        return text.strip()

    def _clean_text(self, text: str) -> str:
        """
        清理文本中的换行符和多余空白字符（兼容旧方法）

        Args:
            text: 需要清理的文本

        Returns:
            str: 清理后的文本
        """
        return self._clean_text_and_spaces(text)

    def save_tables(self, tables: List[Dict], output_path: str):
        """
        保存表格到JSON文件

        Args:
            tables: 表格数据
            output_path: 输出文件路径
        """
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(tables, f, ensure_ascii=False, indent=2)
            self.logger.info(f'表格已保存到 {output_path}')
        except Exception as e:
            self.logger.error(f'保存表格到 {output_path} 时出错: {e}')


# 使用示例
if __name__ == '__main__':
    # 示例用法
    # if len(sys.argv) < 2:
    #     print('用法: python table_analyzer.py <pdf文件路径> [输出文件路径]')
    #     sys.exit(1)

    pdf_path = r'D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf'  # sys.argv[1]
    analyzer = TableAnalyzer(pdf_path)

    # 提取并合并表格
    print('开始提取表格...')
    tables = analyzer.extract_and_merge_tables()
    print(f'提取到 {len(tables)} 个目标表格')

    # 转换为结构化格式
    print('转换为结构化格式...')
    structured_tables = analyzer.convert_to_structured_format(tables)

    # 确定输出文件名
    output_path = sys.argv[2] if len(sys.argv) > 2 else 'target_tables.json'

    # 保存结果
    analyzer.save_tables(structured_tables, output_path)
    print(f'结果已保存到 {output_path}')

    # 显示部分结果
    if structured_tables:
        print('\n表格信息预览:')
        for i, table in enumerate(structured_tables, 1):
            print(f'\n表格 {i}:')

            if table['headers']:
                headers_preview = [
                    h[:20] for h in table['headers'][:3]
                ]  # 显示前3个表头的前20个字符
                print(f'  - 表头: {headers_preview}')

            if table['rows']:
                print(f'  - 数据行数: {len(table["rows"])}')
                # 显示第一行数据的预览
                first_row = table['rows'][0]
                row_preview = {
                    k: v[:30] for k, v in list(first_row.items())[:3]
                }  # 每个值显示前30个字符
                print(f'  - 第一行预览: {row_preview}')

            if table['headers']:
                headers_preview = [
                    h[:20] for h in table['headers'][:3]
                ]  # 显示前3个表头的前20个字符
                print(f'  - 表头: {headers_preview}')

            if table['rows']:
                print(f'  - 数据行数: {len(table["rows"])}')
                # 显示第一行数据的预览
                first_row = table['rows'][0]
                row_preview = {
                    k: v[:30] for k, v in list(first_row.items())[:3]
                }  # 每个值显示前30个字符
                print(f'  - 第一行预览: {row_preview}')
