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

        self.logger.info(
            f'选择置信度最高的价格: {best_price["value"]} (置信度: {best_price["confidence"]})'
        )
        return best_price['value']

    def extract_and_select_price(self, pages: List[str], md_file_path: Optional[str] = None) -> Optional[float]:
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
