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
            text_candidates_count = 0
            if target_pages:
                for page_idx in target_pages:
                    text_candidates = self._extract_from_target_page_text(
                        pages_text[page_idx], page_idx
                    )
                    all_candidates.extend(text_candidates)
                    text_candidates_count += len(text_candidates)
                self.logger.info(
                    f'从目标页面文本提取到{text_candidates_count}个价格候选项'
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

    def extract_enhanced_prices(self, pages_text: List[str]) -> List[Dict[str, Any]]:
        """
        从PDF页面中提取价格，为与现有系统兼容而提供的接口方法
        
        Args:
            pages_text: PDF页面文本列表
            
        Returns:
            价格信息列表，每个元素包含value、confidence等字段
        """
        # 调用现有的extract_bid_price方法
        candidate = self.extract_bid_price(pdf_path="", pages_text=pages_text)
        
        if candidate:
            # 转换为与现有系统兼容的格式
            return [{
                'value': candidate.value,
                'page': candidate.page_index,
                'confidence': candidate.confidence,
                'reason': f'增强版价格提取器 ({candidate.source_type})',
                'location': candidate.location_info
            }]
        else:
            # 如果没有找到价格，回退到基础提取器
            return self.base_extractor.extract_enhanced_prices(pages_text)

    def _extract_from_target_page_text(
        self, page_text: str, page_idx: int
    ) -> List[PriceCandidate]:
        """从目标页面文本中提取价格候选项"""
        candidates = []
        
        # 首先查找投标一览表中的特殊格式价格（小写和大写在同一单元格中）
        # 这种格式具有最高的置信度
        bid_table_patterns = [
            r'（小写）[￥¥]?([\d,]+\.?\d*)\s*元?\s*（大写）(.+?)元整',
            r'投标总价（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*元?\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'投标总价\s*（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*元?\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'投标总价（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*元?\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            r'[投标总价总报价]\s*（小写）[￥¥]?\s*([\d,]+\.?\d*)\s*（大写）[人民币]?\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)',
            # 新增支持用户提到的格式：小写）203 万元  （大写）贰佰零叁万元
            r'小写[）\)]\s*([\d,]+\.?\d*)\s*(?:万元|元)\s*[(（]大写[)）]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元万元整]+)',
        ]
        
        for pattern in bid_table_patterns:
            matches = list(re.finditer(pattern, page_text))
            for match in matches:
                if pattern == r'（小写）[￥¥]?([\d,]+\.?\d*)\s*元?\s*（大写）(.+?)元整':
                    # 特殊处理第一个模式
                    small_price_str = match.group(1)
                    chinese_text_with_rmb = match.group(2)
                    # 移除"人民币"前缀
                    chinese_num = re.sub(r'^人民币', '', chinese_text_with_rmb)
                else:
                    small_price_str = match.group(1)
                    chinese_num = match.group(2)
                
                try:
                    small_number_price = self._str_to_float(small_price_str)
                    large_number_price = self.chinese_converter.chinese_to_number(chinese_num)
                    
                    if small_number_price and large_number_price:
                        # 验证两个价格是否接近
                        if abs(small_number_price - large_number_price) < 10000:  # 允许一定误差（扩大到10000）
                            # 这种格式具有最高置信度
                            candidates.append(
                                PriceCandidate(
                                    value=small_number_price,  # 优先返回小写金额
                                    page_index=page_idx,
                                    confidence=98.0,  # 最高置信度
                                    source_type='bid_table_format',
                                    location_info=f'页面{page_idx+1}投标一览表格式',
                                    validation_data={
                                        'small_price': small_price_str,
                                        'large_price': chinese_num,
                                        'match_text': match.group(0)
                                    }
                                )
                            )
                            self.logger.info(f'从投标一览表特殊格式提取到价格: {small_number_price}, 大写: {large_number_price}')
                except Exception as e:
                    self.logger.warning(f'处理投标一览表格式价格时出错: {e}')
        
        # 查找数字价格
        for pattern in self.table_price_patterns:
            for match in re.finditer(pattern, page_text, re.IGNORECASE | re.MULTILINE):
                price_str = match.group(1)

                # 检查上下文，排除干扰词
                context_start = max(0, match.start() - 100)
                context_end = min(len(page_text), match.end() + 100)
                context = page_text[context_start:context_end]

                if any(keyword in context for keyword in self.exclude_keywords):
                    continue

                try:
                    # 清理和转换价格
                    numeric_str = re.sub(r'[￥¥,\s]', '', price_str)
                    price_value = float(numeric_str)

                    # 验证价格合理性
                    if self._is_reasonable_price(price_value, context):
                        confidence = self._calculate_confidence(page_text, match, context)
                        candidates.append(
                            PriceCandidate(
                                value=price_value,
                                page_index=page_idx,
                                confidence=confidence,
                                source_type='text',
                                location_info=f'页面{page_idx+1}文本',
                                validation_data={'context': context}
                            )
                        )

                except ValueError:
                    continue

        # 查找大写中文价格
        chinese_pattern = r'([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿元整]+)'
        for match in re.finditer(chinese_pattern, page_text):
            chinese_text = match.group(1)
            # 清理大写价格文本
            cleaned_text = re.sub(r'[^\u4e00-\u9fa5]', '', chinese_text)
            price_value = self.chinese_converter.chinese_to_number(cleaned_text)
            
            if price_value and self._is_reasonable_price(price_value, page_text[match.start()-50:match.end()+50]):
                candidates.append(
                    PriceCandidate(
                        value=price_value,
                        page_index=page_idx,
                        confidence=85.0,  # 大写中文价格的置信度
                        source_type='chinese_text',
                        location_info=f'页面{page_idx+1}大写中文',
                        validation_data={'chinese_text': cleaned_text}
                    )
                )

        return candidates

    def _is_reasonable_price(self, price_value: float, context: str) -> bool:
        """验证价格是否合理"""
        # 基本范围检查
        if price_value < 1000:  # 小于1000元的价格不太可能是投标总价
            return False
        if price_value > 10000000000:  # 大于100亿的价格可能过大
            return False

        # 检查上下文中是否包含保证金相关信息
        bond_indicators = [
            '保证金', '投标保证金', '履约保证金', '质量保证金', '保函', 
            '投标保函', '履约保函', '押金', '担保', '银行保函'
        ]

        for indicator in bond_indicators:
            # 检查indicator前后一定范围内的文本
            indicator_pos = context.find(indicator)
            if indicator_pos != -1:
                # 检查indicator附近是否有"价格"、"金额"等词，如果有则可能是相关价格
                nearby_text = context[max(0, indicator_pos-10):min(len(context), indicator_pos+len(indicator)+10)]
                price_related_words = ['价格', '金额', '报价', '总价']
                if not any(word in nearby_text for word in price_related_words):
                    return False

        return True

    def _calculate_confidence(self, page_text: str, match, context: str) -> float:
        """计算置信度"""
        confidence = 60.0  # 基础置信度

        # 投标一览表关键词加分
        if any(keyword in context.lower() for keyword in self.bid_summary_keywords):
            confidence += 25.0

        # 明确价格字段关键词加分
        price_keywords = ['投标总价', '投标报价', '总报价', '总价', '小写']
        if any(keyword in context for keyword in price_keywords):
            confidence += 15.0

        # 表格格式特征加分
        if '│' in context or '┃' in context or '|' in context:
            confidence += 10.0

        # 数字格式合理性加分
        price_str = match.group(1)
        if ',' in price_str:  # 有千位分隔符
            confidence += 5.0

        # 上下文中有"元"字符加分
        if '元' in context:
            confidence += 5.0
            
        # 价格数值大小加分（大额价格更可能是总价）
        try:
            price_value = self._str_to_float(price_str)
            if price_value and price_value >= 100000:  # 大于10万的金额
                confidence += 10.0
            elif price_value and price_value >= 1000000:  # 大于100万的金额
                confidence += 20.0
        except:
            pass

        return min(confidence, 100.0)

    def _fallback_extraction(self, pages_text: List[str]) -> List[PriceCandidate]:
        """回退到基础提取器进行价格提取"""
        try:
            # 使用基础提取器提取价格
            base_prices = self.base_extractor.extract_enhanced_prices(pages_text)
            
            # 转换为基础价格候选项
            candidates = []
            for price_info in base_prices:
                candidates.append(
                    PriceCandidate(
                        value=price_info['value'],
                        page_index=price_info['page'],
                        confidence=price_info['confidence'] * 0.8,  # 降低回退方法的置信度
                        source_type='fallback',
                        location_info=price_info.get('reason', '回退提取'),
                        validation_data={}
                    )
                )
            
            return candidates
        except Exception as e:
            self.logger.error(f'回退提取出错: {e}')
            return []

    def _select_best_candidate(self, candidates: List[PriceCandidate]) -> Optional[PriceCandidate]:
        """选择最佳价格候选项"""
        if not candidates:
            return None

        # 优先选择来自投标一览表特殊格式的候选项（置信度最高）
        bid_table_candidates = [c for c in candidates if c.source_type == 'bid_table_format' and c.confidence >= 95]
        if bid_table_candidates:
            return max(bid_table_candidates, key=lambda x: x.confidence)

        # 其次选择来自表格且置信度高的候选项
        table_candidates = [c for c in candidates if c.source_type == 'table' and c.confidence > 90]
        if table_candidates:
            return max(table_candidates, key=lambda x: x.confidence)

        # 再次选择来自文本且置信度高的候选项
        text_candidates = [c for c in candidates if c.source_type in ['text', 'chinese_text'] and c.confidence > 85]
        if text_candidates:
            return max(text_candidates, key=lambda x: x.confidence)

        # 最后选择置信度最高的候选项
        return max(candidates, key=lambda x: x.confidence)

    def _find_price_column(self, headers: List[str]) -> Optional[int]:
        """在表格表头中寻找价格相关的列"""
        for i, header in enumerate(headers):
            header_lower = header.lower().strip()
            # 检查是否包含价格相关关键词
            for keyword in self.price_field_keywords:
                if keyword in header_lower:
                    return i
        return None

    def _search_price_in_all_cells(self, table_data: List[List[Any]], page_idx: int, table_info: Dict[str, Any]) -> Optional[PriceCandidate]:
        """在表格的所有单元格中搜索价格"""
        for row_idx, row in enumerate(table_data):
            for col_idx, cell in enumerate(row):
                if cell:
                    price_value = self._extract_price_from_cell(str(cell))
                    if price_value and price_value > 1000:  # 过滤过小的值
                        return PriceCandidate(
                            value=price_value,
                            page_index=page_idx,
                            confidence=80.0,  # 表格提取的中等置信度
                            source_type='table_cell',
                            location_info=f'表格第{row_idx+1}行第{col_idx+1}列',
                            validation_data={
                                'cell_value': cell,
                            },
                        )
        return None

    def _extract_price_from_cell(self, cell_value: str) -> Optional[float]:
        """从单元格中提取价格"""
        # 尝试多种价格模式
        patterns = [
            r'[￥¥]\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:元|万元)',
            r'(?:小写|小写金额)[:：\s]*([￥¥]?\s*[\d,]+\.?\d*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, cell_value, re.IGNORECASE)
            if match:
                price_str = match.group(1)
                try:
                    # 清理和转换价格
                    numeric_str = re.sub(r'[￥¥,\s]', '', price_str)
                    return float(numeric_str)
                except ValueError:
                    continue
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
        self, table_data: List[List[Any]], page_idx: int, table_info: Dict[str, Any]
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

    def _str_to_float(self, s: str) -> Optional[float]:
        """将字符串转换为浮点数"""
        try:
            # 清理字符串中的非数字字符（保留小数点和千位分隔符）
            cleaned = re.sub(r'[^\d\.]', '', s)
            return float(cleaned)
        except (ValueError, TypeError):
            return None
