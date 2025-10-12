#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:12:11
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-26 18:48:38
# 文件相对于项目的路径   : \AI_env2\modules\price_extraction_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import logging
import re
from typing import List, Dict, Any, Optional


class ChineseNumberConverter:
    """
    一个更强大的中文数字转换器，支持大写、小写、单位（万、亿）和基本的小数处理。
    """

    def __init__(self):
        self.num_map = {
            '零': 0,
            '一': 1,
            '二': 2,
            '三': 3,
            '四': 4,
            '五': 5,
            '六': 6,
            '七': 7,
            '八': 8,
            '九': 9,
            '壹': 1,
            '贰': 2,
            '叁': 3,
            '肆': 4,
            '伍': 5,
            '陆': 6,
            '柒': 7,
            '捌': 8,
            '玖': 9,
            '两': 2,
        }
        self.unit_map = {
            '十': 10,
            '百': 100,
            '千': 1000,
            '拾': 10,
            '佰': 100,
            '仟': 1000,
        }
        self.large_unit_map = {'万': 10000, '亿': 100000000}

    def chinese_to_number(self, text: str) -> Optional[float]:
        """
        将中文数字字符串（包括大写）转换为阿拉伯数字浮点数。
        """
        if not text:
            return None

        # 移除常见非数字字符
        text = re.sub(r'[元圆角分整人民币\\s]', '', text)

        # 处理亿和万
        if '亿' in text:
            parts = text.split('亿')
            high = self._convert_segment(parts[0]) * self.large_unit_map['亿']
            low = self._convert_segment(parts[1]) if parts[1] else 0
            return high + low
        if '万' in text:
            parts = text.split('万')
            high = self._convert_segment(parts[0]) * self.large_unit_map['万']
            low = self._convert_segment(parts[1]) if parts[1] else 0
            return high + low

        return self._convert_segment(text)

    def _convert_segment(self, segment: str) -> float:
        """转换万或亿内部的数字部分"""
        if not segment:
            return 0

        total = 0
        current_num = 0
        for char in segment:
            if char in self.num_map:
                current_num = self.num_map[char]
            elif char in self.unit_map:
                total += (current_num or 1) * self.unit_map[char]
                current_num = 0
            else:
                # 忽略无法识别的字符
                pass
        total += current_num
        return total


class PriceExtractionManager:
    """价格提取管理器，统一处理价格提取相关功能"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.converter = ChineseNumberConverter()
        # 优先匹配包含明确关键字的模式
        self.total_price_keywords = ['总价', '总报价', '投标报价', '合计', '总计']
        # 排除干扰关键词（避免将保证金等识别为总报价）
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
        ]
        # 增加投标一览表关键词，包括更多变体
        self.bid_summary_keywords = [
            '投标一览表',
            '开标一览表',
            '价格一览表',
            '投标报价一览表',
            '报价一览表',
            '投标文件一览表',
            '投标价格汇总表',
            '投标汇总表',
            '投标总价',  # 增加这个关键词
            '货物名称.*投标总价',  # 增加这个模式
        ]
        # 匹配 "关键字" 和 数字 的模式
        self.price_patterns = [
            # 格式: (关键字) 金额(阿拉伯数字, 带/不带逗号, 带/不带小数) (可选的大写中文)
            r'({keywords})[:：\s]*?([\d,]+\.?\d*)\s*\(?(?:[\u4e00-\u9fa5]+)?\)?'.format(
                keywords='|'.join(self.total_price_keywords)
            ),
            # 格式: 金额(阿拉伯数字) 后面紧跟 (关键字)
            r'([\d,]+\.?\d*)\s*({keywords})'.format(
                keywords='|'.join(self.total_price_keywords)
            ),
        ]
        # 通用价格模式，作为补充
        self.general_price_patterns = [
            r'￥\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*元',
        ]
        # 专门针对价格一览表的模式
        self.price_summary_patterns = [
            # 投标一览表专用模式
            r'(投标总价|投标报价|总报价|总价)[:：\s]*([\d,]+\.?\d*)\s*元?',
            r'(小写)[:：\s]*([\d,]+\.?\d*)\s*元?',
            r'(大写)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿]+)',
            r'([\d,]+\.?\d*)\s*元\s*(?:大写|小写)?',
            # 表格格式的价格
            r'(投标报价|总价|总报价)[\s\S]*?([\d,]+\.?\d*)\s*元',
            r'([\d,]+\.?\d*)\s*元[\s\S]*?(投标报价|总价|总报价)',
        ]

    def extract_prices_from_content(self, pages: List[str]) -> List[Dict[str, Any]]:
        """
        从PDF页面内容中提取价格信息

        Args:
            pages: PDF页面文本列表

        Returns:
            List[Dict[str, Any]]: 价格信息列表，每个元素包含value、confidence等字段
        """
        try:
            # 使用增强的价格提取器提取价格
            prices = self.extract_enhanced_prices(pages)

            # 过滤掉明显不合理的低价（如小于1000元的价格）
            filtered_prices = [p for p in prices if p['value'] >= 1000]

            self.logger.info(
                f'从{len(pages)}页内容中提取到{len(filtered_prices)}个有效价格'
            )
            return filtered_prices
        except Exception as e:
            self.logger.error(f'提取价格时出错: {e}')
            return []

    def select_best_price(
        self, prices: List[Dict[str, Any]], pages: List[str]
    ) -> Optional[float]:
        """
        选择最佳价格，优先选择"投标一览表"中的高置信度价格

        Args:
            prices: 价格信息列表
            pages: PDF页面文本列表

        Returns:
            Optional[float]: 最佳价格，如果未找到则返回None
        """
        if not prices:
            return None

        # 1. 优先选择来自"投标一览表"且置信度大于80的价格
        summary_page_prices = [
            p
            for p in prices
            if p.get('confidence', 0) > 80
            and ('一览表' in p.get('reason', '') or '投标一览表' in p.get('reason', ''))
        ]

        if summary_page_prices:
            # 按置信度排序，选择置信度最高的
            best_price = sorted(
                summary_page_prices, key=lambda x: x['confidence'], reverse=True
            )[0]
            self.logger.info(
                f'选择来自投标一览表的高置信度价格: {best_price["value"]} (置信度: {best_price["confidence"]})'
            )
            return best_price['value']

        # 2. 如果没有投标一览表中的高置信度价格，则选择置信度最高的价格
        prices_sorted = sorted(
            prices, key=lambda x: x.get('confidence', 0), reverse=True
        )
        best_price = prices_sorted[0]

        self.logger.info(
            f'选择置信度最高的价格: {best_price["value"]} (置信度: {best_price["confidence"]})'
        )
        return best_price['value']

    def extract_and_select_price(self, pages: List[str]) -> Optional[float]:
        """
        提取并选择最佳价格的一体化方法

        Args:
            pages: PDF页面文本列表

        Returns:
            Optional[float]: 最佳价格，如果未找到则返回None
        """
        self.logger.info(f'开始价格提取，共 {len(pages)} 页')

        # 提取所有价格
        prices = self.extract_prices_from_content(pages)
        self.logger.info(f'提取到 {len(prices)} 个价格')

        if not prices:
            self.logger.warning('未提取到任何有效价格')
            return None

        # 选择最佳价格
        best_price = self.select_best_price(prices, pages)

        if best_price is not None:
            self.logger.info(f'最终选择的最佳价格: {best_price}')
        else:
            self.logger.warning('未能选择出最佳价格')

        return best_price

    def extract_enhanced_prices(self, pages: List[str]) -> List[Dict[str, Any]]:
        """
        从PDF页面中提取价格，并为每个价格计算置信度。
        """
        all_prices = []

        # 1. 识别关键章节 - 优先识别投标一览表
        price_summary_pages = self._identify_sections(
            pages,
            self.bid_summary_keywords,  # 使用我们定义的关键词列表
        )
        price_doc_pages = self._identify_sections(pages, ['价格文件', '报价部分'])

        for i, page_text in enumerate(pages):
            context = page_text.replace('\n', ' ')

            # 2. 特别处理价格一览表页面
            if i in price_summary_pages:
                summary_prices = self._extract_prices_from_summary_page(page_text, i)
                all_prices.extend(summary_prices)

            # 3. 在页面中查找所有可能的价格
            # 查找与关键字强相关的价格
            for pattern in self.price_patterns:
                for match in re.finditer(pattern, context):
                    groups = match.groups()
                    price_str = (
                        groups[1]
                        if groups[0] in self.total_price_keywords
                        else groups[0]
                    )
                    chinese_price_str = groups[2] if len(groups) > 2 else None
                    # 窗口文本用于排除保证金等干扰
                    window_start = max(0, match.start() - 40)
                    window_end = min(len(context), match.end() + 40)
                    window_text = context[window_start:window_end]
                    if any(k in window_text for k in self.exclude_keywords):
                        continue

                    price_value = self._str_to_float(price_str)
                    if price_value is None:
                        continue

                    confidence = self._calculate_price_confidence(
                        page_index=i,
                        price_value=price_value,
                        keyword_found=True,
                        chinese_price_str=chinese_price_str,
                        price_summary_pages=price_summary_pages,
                        price_doc_pages=price_doc_pages,
                        pattern_used=pattern,
                        context_text=window_text,
                    )
                    all_prices.append(
                        {
                            'value': price_value,
                            'page': i,
                            'confidence': confidence,
                            'reason': f'关键字匹配 (pattern: {pattern})',
                        }
                    )

            # 查找通用价格格式
            for pattern in self.general_price_patterns:
                for match in re.finditer(pattern, context):
                    price_str = match.group(1)
                    window_start = max(0, match.start() - 25)
                    window_end = min(len(context), match.end() + 25)
                    window_text = context[window_start:window_end]
                    if any(k in window_text for k in self.exclude_keywords):
                        continue
                    price_value = self._str_to_float(price_str)
                    if price_value is None:
                        continue

                    confidence = self._calculate_price_confidence(
                        page_index=i,
                        price_value=price_value,
                        keyword_found=False,
                        price_summary_pages=price_summary_pages,
                        price_doc_pages=price_doc_pages,
                        pattern_used=pattern,
                        context_text=window_text,
                    )
                    all_prices.append(
                        {
                            'value': price_value,
                            'page': i,
                            'confidence': confidence,
                            'reason': f'通用格式匹配 (pattern: {pattern})',
                        }
                    )

        return all_prices

    def _extract_prices_from_summary_page(
        self, page_text: str, page_index: int
    ) -> List[Dict[str, Any]]:
        """
        从价格一览表页面提取价格，特别处理小写和大写价格对照的情况
        """
        self.logger.info(f'开始从第 {page_index} 页提取价格，页面包含"投标一览表"')
        prices = []

        # 首先尝试提取江苏鑫桥文件中的特殊格式
        # 模式: （小写）1522300.00元（写）壹佰伍拾贰万贰仟叁佰元整。含13%增值税
        self.logger.info('尝试匹配江苏鑫桥文件特殊格式')
        jiangsu_pattern = r'（小写）([￥¥]?[\d,]+\.?\d*)元（写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)元整。含[\d%]*增值税'
        jiangsu_match = re.search(jiangsu_pattern, page_text)

        if jiangsu_match:
            self.logger.info('江苏鑫桥文件特殊格式匹配成功!')
            small_price_str = jiangsu_match.group(1)
            chinese_text = jiangsu_match.group(2)

            small_price = self._str_to_float(small_price_str)
            large_price = self.converter.chinese_to_number(chinese_text)

            self.logger.info(f'小写价格: {small_price}, 大写价格: {large_price}')

            if small_price is not None and small_price > 1000:
                prices.append(
                    {
                        'value': small_price,
                        'page': page_index,
                        'confidence': 100,
                        'reason': '江苏鑫桥文件特殊格式价格',
                    }
                )
                self.logger.info(f'从江苏鑫桥文件特殊格式提取到价格: {small_price}')
                return prices  # 直接返回，因为这是最准确的价格
        else:
            self.logger.info('江苏鑫桥文件特殊格式匹配失败')
            # 调试信息
            test_pattern = r'（小写）.*?（写）'
            test_match = re.search(test_pattern, page_text)
            if test_match:
                self.logger.info(f'测试模式匹配到: {test_match.group()}')

        # 如果没有找到江苏鑫桥文件的特殊格式，继续使用原有逻辑
        xiaoxie_price = None
        daxie_price_text = None
        daxie_price_value = None

        # 查找小写价格 - 增强模式以匹配更多格式
        xiaoxie_patterns = [
            r'(小写).*?￥?\s*([\d,]+\.?\d*)',
            r'(小写金额)[:：\s]*￥?\s*([\d,]+\.?\d*)',
            r'(投标报价)[:：\s]*￥?\s*([\d,]+\.?\d*)',
            r'(总报价)[:：\s]*￥?\s*([\d,]+\.?\d*)',
            r'(总价)[:：\s]*￥?\s*([\d,]+\.?\d*)',
            r'(人民币)[:：\s]*￥?\s*([\d,]+\.?\d*)',
            r'￥\s*([\d,]+\.?\d*)',
            r'([\d,]+\.?\d*)\s*(?:元|人民币)',
            # 新增处理您提到的特殊格式
            r'（小写）¥([\d,]+\.?\d*)',
            r'（小写）￥([\d,]+\.?\d*)',
            r'小写[:：]\s*¥([\d,]+\.?\d*)',
            r'小写[:：]\s*￥([\d,]+\.?\d*)',
        ]

        # 首先查找更明确的投标报价、总报价等关键字
        for pattern in xiaoxie_patterns:
            xiaoxie_match = re.search(pattern, page_text, re.IGNORECASE)
            if xiaoxie_match:
                self.logger.info(f'模式匹配成功: {pattern}')
                self.logger.info(f'匹配结果: {xiaoxie_match.groups()}')
                xiaoxie_price_str = (
                    xiaoxie_match.group(2)
                    if len(xiaoxie_match.groups()) >= 2
                    else xiaoxie_match.group(1)
                )  # 获取价格组
                # 行级过滤以排除保证金等干扰项
                line_start = page_text.rfind('\n', 0, xiaoxie_match.start()) + 1
                line_end = page_text.find('\n', xiaoxie_match.end())
                if line_end == -1:
                    line_end = len(page_text)
                line_text = page_text[line_start:line_end]
                self.logger.info(f'匹配行文本: {line_text}')
                if any(k in line_text for k in self.exclude_keywords):
                    self.logger.info('该行包含排除关键词，跳过')
                    continue
                xiaoxie_price = self._str_to_float(xiaoxie_price_str)
                self.logger.info(f'解析的价格值: {xiaoxie_price}')
                if (
                    xiaoxie_price is not None and xiaoxie_price > 1000
                ):  # 过滤掉过小的价格（如1.00）
                    prices.append(
                        {
                            'value': xiaoxie_price,
                            'page': page_index,
                            'confidence': 100,  # 最高置信度
                            'reason': f'价格一览表明确关键字价格 (pattern: {pattern})',
                        }
                    )
                    self.logger.info(f'成功添加价格: {xiaoxie_price}')
                    break  # 找到第一个有效价格就停止

        # 查找大写价格，增加更多模式
        daxie_patterns = [
            r'(大写)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)',
            r'(大写金额)[:：\s]*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)',
            r'([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)[:：\s]*(?:元|人民币)',
            # 新增处理您提到的特殊格式
            r'（大写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)',
            r'大写[:：]\s*([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)',
            # 江苏鑫桥文件中的特殊格式
            r'（写）([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿\s]+)',
        ]

        for pattern in daxie_patterns:
            daxie_match = re.search(pattern, page_text, re.IGNORECASE)
            if daxie_match:
                daxie_price_text = (
                    daxie_match.group(2)
                    if len(daxie_match.groups()) >= 2
                    else daxie_match.group(1)
                )
                # 清理大写价格文本，移除多余的空格和干扰字符
                daxie_price_text = re.sub(r'[^\u4e00-\u9fa5]', '', daxie_price_text)
                # 行级过滤以排除保证金等干扰项
                line_start = page_text.rfind('\n', 0, daxie_match.start()) + 1
                line_end = page_text.find('\n', daxie_match.end())
                if line_end == -1:
                    line_end = len(page_text)
                line_text = page_text[line_start:line_end]
                if any(k in line_text for k in self.exclude_keywords):
                    continue
                daxie_price_value = self.converter.chinese_to_number(daxie_price_text)
                if (
                    daxie_price_value is not None and daxie_price_value > 1000
                ):  # 过滤掉过小的价格
                    prices.append(
                        {
                            'value': daxie_price_value,
                            'page': page_index,
                            'confidence': 95,  # 高置信度
                            'reason': f'价格一览表大写价格 (pattern: {pattern})',
                        }
                    )
                    break  # 找到第一个有效价格就停止

        # 如果同时找到小写和大写价格，进行验证
        if xiaoxie_price is not None and daxie_price_value is not None:
            # 如果两个价格相差不大(允许一定误差)，则提高小写价格的置信度
            if (
                abs(xiaoxie_price - daxie_price_value)
                / max(xiaoxie_price, daxie_price_value)
                < 0.01
            ):  # 1%误差范围内
                # 找到小写价格条目并提高置信度
                for price_info in prices:
                    if price_info['value'] == xiaoxie_price:
                        price_info['confidence'] = 100  # 最高置信度
                        price_info['reason'] = '价格一览表小写价格(与大写价格匹配)'
                        break

        return prices

    def _calculate_price_confidence(
        self,
        page_index: int,
        price_value: float,
        keyword_found: bool,
        price_summary_pages: List[int],
        price_doc_pages: List[int],
        chinese_price_str: Optional[str] = None,
        pattern_used: Optional[str] = None,
        context_text: Optional[str] = None,
    ) -> float:
        """
        为提取到的价格计算置信度分数。
        """
        confidence = 0.0

        # 基础分
        if keyword_found:
            confidence += 50  # 找到总价等关键字，基础分高
        else:
            confidence += 10  # 通用价格格式，基础分低

        # 章节加分
        if page_index in price_summary_pages:
            confidence += 40  # 在"投标一览表"中，权重最高
        elif page_index in price_doc_pages:
            confidence += 20  # 在价格文档中，权重较高

        # 大写中文价格加分
        if chinese_price_str:
            confidence += 10  # 有大写中文价格，增加可信度

        # 价格合理性加分（价格在合理范围内）
        if 1000 <= price_value <= 1000000000:  # 1000元到10亿元之间
            confidence += 10
        elif price_value > 1000000000:  # 超过10亿元，可能是总价
            confidence += 5

        # 根据使用的模式增加置信度
        if pattern_used:
            # 如果使用了明确的关键字模式，增加置信度
            if any(
                keyword in pattern_used
                for keyword in ['投标报价', '总报价', '总价', '小写', '大写']
            ):
                confidence += 15
            # 如果使用了人民币符号模式，增加置信度
            elif '￥' in pattern_used or '¥' in pattern_used:
                confidence += 10

        # 上下文相关性加分
        if context_text:
            # 检查上下文是否包含价格相关的关键词
            price_context_keywords = ['含税', '税率', '增值税', '13%', '6%', '3%']
            context_matches = sum(
                1 for keyword in price_context_keywords if keyword in context_text
            )
            confidence += min(context_matches * 5, 15)  # 最多增加15分

        # 限制最大置信度
        confidence = min(confidence, 100.0)

        return confidence

    def _identify_sections(self, pages: List[str], keywords: List[str]) -> List[int]:
        """
        识别包含特定关键词的页面。

        Args:
            pages: 页面文本列表
            keywords: 关键词列表

        Returns:
            List[int]: 包含关键词的页面索引列表
        """
        matched_pages = []
        for i, page_text in enumerate(pages):
            # 将页面文本转换为小写进行匹配
            lower_text = page_text.lower()
            # 检查是否包含任何关键词
            if any(keyword.lower() in lower_text for keyword in keywords):
                matched_pages.append(i)
            # 增加对"投标总价"的特殊处理
            elif '投标总价' in page_text and (
                '货物名称' in page_text or '制造商名称' in page_text
            ):
                matched_pages.append(i)
        return matched_pages

    def _str_to_float(self, s: str) -> Optional[float]:
        """
        将字符串转换为浮点数，处理逗号分隔符。

        Args:
            s: 字符串

        Returns:
            Optional[float]: 转换后的浮点数，如果转换失败则返回None
        """
        if not s:
            return None
        try:
            # 移除逗号并转换为浮点数
            return float(s.replace(',', ''))
        except ValueError:
            return None
