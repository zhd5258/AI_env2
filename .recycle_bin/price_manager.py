#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-21 18:14:50
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-21 18:22:53
# 文件相对于项目的路径   : \AI_env2\modules\price_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
"""
价格管理模块
负责从投标文件中提取价格信息并选择最佳价格
"""

import logging
import os
from typing import List, Dict, Any, Optional
from modules.enhanced_price_extractor import EnhancedPriceExtractor
from modules.md_price_extractor import MDPriceExtractor


class PriceManager:
    """价格管理器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.extractor = EnhancedPriceExtractor()
        self.md_extractor = MDPriceExtractor()

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
            prices = self.extractor.extract_enhanced_prices(pages)

            # 过滤掉明显不合理的低价（如小于1000元的价格）
            filtered_prices = [p for p in prices if p['value'] >= 1000]

            self.logger.info(
                f'从{len(pages)}页内容中提取到{len(filtered_prices)}个有效价格'
            )
            return filtered_prices
        except Exception as e:
            self.logger.error(f'提取价格时出错: {e}')
            return []

    def extract_price_from_md_file(self, md_file_path: str) -> Optional[float]:
        """
        从MD文件中提取价格

        Args:
            md_file_path: MD文件路径

        Returns:
            提取到的价格，如果未找到则返回None
        """
        return self.md_extractor.extract_price_from_md_file(md_file_path)

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

        # 1. 优先选择来自"投标一览表"且置信度大于90的价格
        summary_page_prices = [
            p
            for p in prices
            if p.get('confidence', 0) > 90 and '一览表' in p.get('reason', '')
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

        # 3. 对价格进行置信度评估，过滤明显不合理的投标总价
        if self._is_price_reasonable(best_price['value'], pages):
            self.logger.info(
                f'选择置信度最高的价格: {best_price["value"]} (置信度: {best_price["confidence"]})'
            )
            return best_price['value']
        else:
            self.logger.warning(
                f'检测到价格 {best_price["value"]} 可能不合理，需要重新提取'
            )
            # 尝试重新提取价格
            return self._re_extract_price(pages)

        self.logger.info(
            f'选择置信度最高的价格: {best_price["value"]} (置信度: {best_price["confidence"]})'
        )
        return best_price['value']

    def _is_price_reasonable(self, price: float, pages: List[str]) -> bool:
        """
        评估价格是否合理

        Args:
            price: 价格值
            pages: PDF页面文本列表

        Returns:
            bool: 价格是否合理
        """
        # 基本范围检查
        if price < 1000:  # 小于1000元的价格不太可能是投标总价
            self.logger.warning(f'价格 {price} 小于1000元，可能不合理')
            return False
        if price > 10000000000:  # 大于100亿的价格可能过大
            self.logger.warning(f'价格 {price} 大于100亿，可能不合理')
            return False

        # 获取所有页面文本
        full_text = ' '.join(pages)

        # 检查价格是否出现在投标一览表附近
        # 查找投标一览表关键词
        bid_summary_keywords = [
            '投标一览表',
            '开标一览表',
            '价格一览表',
            '投标报价一览表',
            '报价一览表',
            '投标文件一览表',
            '投标价格汇总表',
            '投标汇总表',
        ]

        # 查找价格在文本中的位置
        price_str = str(price)
        price_positions = []
        start = 0
        while True:
            pos = full_text.find(price_str, start)
            if pos == -1:
                break
            price_positions.append(pos)
            start = pos + 1

        # 检查每个价格位置附近是否有投标一览表关键词
        for pos in price_positions:
            # 检查位置前后一定范围内的文本
            start_pos = max(0, pos - 500)  # 前500个字符
            end_pos = min(len(full_text), pos + 500)  # 后500个字符
            context = full_text[start_pos:end_pos]

            # 检查上下文中是否包含投标一览表关键词
            if any(keyword in context for keyword in bid_summary_keywords):
                # 检查上下文中是否包含排除关键词（如业绩、合同等）
                exclude_keywords = ['业绩', '合同', '注册资本', '年营业额', '净资产']
                if not any(
                    exclude_keyword in context for exclude_keyword in exclude_keywords
                ):
                    self.logger.info(f'价格 {price} 出现在投标一览表附近，合理')
                    return True

        self.logger.warning(f'价格 {price} 未出现在投标一览表附近，可能不合理')
        return False

    def _re_extract_price(self, pages: List[str]) -> Optional[float]:
        """
        重新提取价格

        Args:
            pages: PDF页面文本列表

        Returns:
            Optional[float]: 重新提取的价格，如果未找到则返回None
        """
        self.logger.info('开始重新提取价格')

        # 使用增强的价格提取器重新提取价格
        try:
            from modules.enhanced_price_extractor import EnhancedPriceExtractor

            extractor = EnhancedPriceExtractor()
            candidate = extractor.extract_bid_price(pdf_path='', pages_text=pages)

            if candidate:
                self.logger.info(
                    f'重新提取到价格: {candidate.value} (置信度: {candidate.confidence})'
                )
                # 再次检查价格是否合理
                if self._is_price_reasonable(candidate.value, pages):
                    return candidate.value
                else:
                    self.logger.warning(f'重新提取的价格 {candidate.value} 仍不合理')
                    return None
            else:
                self.logger.warning('重新提取未找到价格')
                return None
        except Exception as e:
            self.logger.error(f'重新提取价格时出错: {e}')
            return None

    def extract_and_select_price(
        self, pages: List[str], md_file_path: Optional[str] = None
    ) -> Optional[float]:
        """
        提取并选择最佳价格的一体化方法
        优先从MD文件提取价格，如果未找到则从PDF内容提取

        Args:
            pages: PDF页面文本列表
            md_file_path: MD文件路径（可选）

        Returns:
            Optional[float]: 最佳价格，如果未找到则返回None
        """
        # 1. 首先尝试从MD文件提取价格
        if md_file_path and os.path.exists(md_file_path):
            md_price = self.extract_price_from_md_file(md_file_path)
            if md_price is not None and md_price >= 1000:
                self.logger.info(f'从MD文件提取到最佳价格: {md_price}')
                return md_price

        # 2. 如果MD文件中未找到价格，则从PDF内容提取
        # 提取所有价格
        prices = self.extract_prices_from_content(pages)

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
