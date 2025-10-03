#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 增强版价格提取器
# 专门针对投标文件中的投标总价提取优化
# 作者: AI Assistant
# 创建时间: 2025-09-28
#

import logging
import re
import os
import sys
from typing import List, Dict, Any, Optional, Tuple
import pdfplumber
from dataclasses import dataclass

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.price_extraction_manager import (
    PriceExtractionManager,
    ChineseNumberConverter,
)
from modules.table_analyzer import TableAnalyzer


@dataclass
class PriceCandidate:
    """价格候选项数据类"""

    value: float
    page_index: int
    confidence: float
    source_type: str  # 'table', 'text', 'ai'
    location_info: str  # 具体位置信息
    validation_data: Dict[str, Any]  # 验证数据，如大写中文等


class EnhancedPriceExtractor:
    """
    增强版价格提取器
    专注于投标文件中投标总价的精确提取

    主要特性：
    1. 智能页面定位：优先定位包含"投标一览表"的页面
    2. 表格结构识别：使用表格识别算法进行精细化处理
    3. 多源验证：结合大写中文、小写数字等多种格式进行验证
    4. 置信度评估：基于多个维度计算准确的置信度
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_extractor = PriceExtractionManager()
        self.chinese_converter = ChineseNumberConverter()

        # 投标一览表关键词（按优先级排序）
        self.bid_summary_keywords = [
            '投标一览表',
            '开标一览表',
            '价格一览表',
            '投标报价一览表',
            '报价一览表',
            '投标文件一览表',
            '投标价格汇总表',
            '投标汇总表',
        ]

        # 价格字段关键词
        self.price_field_keywords = [
            '投标总价',
            '投标报价',
            '总报价',
            '总价',
            '报价金额',
            '合同金额',
            '项目总价',
        ]

        # 表格中的价格识别模式
        self.table_price_patterns = [
            # 明确的价格字段模式
            r'(?:投标总价|投标报价|总报价|总价|报价金额)[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)\s*(?:元|万元)?',
            # 小写/大写标识模式
            r'(?:小写|小写金额)[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)\s*(?:元|万元)?',
            r'(?:大写|大写金额)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            # 货币符号模式
            r'[￥¥]\s*([\d,]+\.?\d*)',
            # 数字+元的模式（在表格环境中）
            r'([\d,]+\.?\d*)\s*(?:元|万元)',
        ]

        # 排除的干扰词
        self.exclude_keywords = [
            '保证金',
            '投标保证金',
            '履约保证金',
            '质量保证金',
            '保函',
            '保证金金额',
            '投标保函',
            '履约保函',
            '押金',
            '投标押金',
            '投标担保',
            '银行保函',
            '注册资本',
            '年营业额',
            '净资产',
        ]

    def extract_bid_price(
        self, pdf_path: str, pages_text: List[str]
    ) -> Optional[PriceCandidate]:
        """
        从投标文件中提取投标总价

        Args:
            pdf_path: PDF文件路径
            pages_text: 页面文本列表

        Returns:
            最佳价格候选项，如果未找到则返回None
        """
        self.logger.info(f'开始增强版价格提取，PDF: {pdf_path}, 共{len(pages_text)}页')

        # 收集所有价格候选项
        all_candidates = []

        try:
            # 1. 页面定位：找到包含投标一览表的页面
            target_pages = self._locate_bid_summary_pages(pages_text)
            self.logger.info(
                f'定位到{len(target_pages)}个投标一览表页面: {target_pages}'
            )

            # 2. 表格方式提取（最高优先级）
            if target_pages and pdf_path:
                table_candidates = self._extract_from_tables(
                    pdf_path, target_pages, pages_text
                )
                all_candidates.extend(table_candidates)
                self.logger.info(f'从表格提取到{len(table_candidates)}个价格候选项')

            # 3. 智能文本提取（针对目标页面）
            if target_pages:
                for page_idx in target_pages:
                    text_candidates = self._extract_from_target_page_text(
                        pages_text[page_idx], page_idx
                    )
                    all_candidates.extend(text_candidates)
                self.logger.info(
                    f'从目标页面文本提取到{len(text_candidates)}个价格候选项'
                )

            # 4. 回退到全文档提取
            if not all_candidates:
                self.logger.info('目标页面未找到价格，回退到全文档提取')
                fallback_candidates = self._fallback_extraction(pages_text)
                all_candidates.extend(fallback_candidates)
                self.logger.info(f'回退提取到{len(fallback_candidates)}个价格候选项')

            # 5. 选择最佳候选项
            best_candidate = self._select_best_candidate(all_candidates)

            if best_candidate:
                self.logger.info(
                    f'选择最佳价格: {best_candidate.value}, 置信度: {best_candidate.confidence:.2f}'
                )
                return best_candidate
            else:
                self.logger.warning('未找到有效的价格候选项')
                return None

        except Exception as e:
            self.logger.error(f'增强版价格提取出错: {e}')
            return None

    def _locate_bid_summary_pages(self, pages_text: List[str]) -> List[int]:
        """定位包含投标一览表的页面"""
        target_pages = []

        for page_idx, page_text in enumerate(pages_text):
            page_text_lower = page_text.lower()

            for keyword in self.bid_summary_keywords:
                if keyword.lower() in page_text_lower:
                    target_pages.append(page_idx)
                    self.logger.info(f'第{page_idx}页包含关键词: {keyword}')
                    break  # 找到一个关键词就足够了

        return target_pages

    def _extract_from_tables(
        self, pdf_path: str, target_pages: List[int], pages_text: List[str]
    ) -> List[PriceCandidate]:
        """从表格中提取价格（使用表格识别算法）"""
        candidates = []

        try:
            # 使用现有的表格分析器
            table_analyzer = TableAnalyzer(pdf_path)
            all_tables = table_analyzer._extract_all_tables()

            for table_info in all_tables:
                page_idx = table_info.get('page', 1) - 1  # 转换为0基索引

                # 只处理目标页面的表格
                if page_idx not in target_pages:
                    continue

                table_data = table_info.get('data', [])
                if not table_data:
                    continue

                # 分析表格结构寻找价格
                price_candidate = self._analyze_table_for_price(
                    table_data, page_idx, table_info
                )
                if price_candidate:
                    candidates.append(price_candidate)

        except Exception as e:
            self.logger.error(f'表格提取出错: {e}')

        return candidates

    def _analyze_table_for_price(
        self, table_data: List[List], page_idx: int, table_info: Dict
    ) -> Optional[PriceCandidate]:
        """分析表格数据寻找价格信息"""
        if not table_data or len(table_data) < 2:
            return None

        headers = table_data[0] if table_data else []

        # 寻找价格相关的列
        price_col_idx = self._find_price_column(headers)

        if price_col_idx is None:
            # 如果没有明确的价格列，尝试在所有单元格中寻找
            return self._search_price_in_all_cells(table_data, page_idx, table_info)

        # 在价格列中寻找价格值
        for row_idx, row in enumerate(table_data[1:], 1):  # 跳过表头
            if price_col_idx < len(row):
                cell_value = row[price_col_idx]
                if cell_value:
                    price_value = self._extract_price_from_cell(cell_value)
                    if price_value and price_value > 1000:  # 过滤过小的值
                        return PriceCandidate(
                            value=price_value,
                            page_index=page_idx,
                            confidence=95.0,  # 表格提取的高置信度
                            source_type='table',
                            location_info=f'表格第{row_idx}行第{price_col_idx}列',
                            validation_data={
                                'table_headers': headers,
                                'cell_value': cell_value,
                            },
                        )

        return None
