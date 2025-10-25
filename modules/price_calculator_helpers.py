"""
价格分计算辅助模块
包含价格分计算相关的辅助函数
"""

import logging
from typing import List, Dict, Any, Optional


class PriceScoreCalculatorHelpers:
    """价格分计算辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _extract_bidder_prices(self, analysis_results) -> Dict[str, float]:
        """
        从分析结果中提取所有投标方的价格信息

        Args:
            analysis_results: 分析结果列表

        Returns:
            Dict[str, float]: 投标方名称到价格的映射
        """
        bidder_prices = {}
        for result in analysis_results:
            try:
                # 确保投标人名称不为空
                bidder_name = result.bidder_name
                if (
                    not bidder_name
                    or not str(bidder_name).strip()
                    or bidder_name == 'None'
                ):
                    bidder_name = f'未知投标人_{result.id}'

                # 优先使用extracted_price字段
                if result.extracted_price is not None and result.extracted_price > 0:
                    price_value = result.extracted_price
                    bidder_prices[bidder_name] = float(price_value)
                    self.logger.info(
                        f'使用extracted_price提取到投标人 {bidder_name} 的价格: {price_value}'
                    )
                    continue

                # 从detailed_scores中查找价格分项
                price_info = self._extract_price_from_result(result)
                if price_info and price_info.get('price') is not None:
                    price_value = price_info['price']
                    # 确保价格是有效的正数
                    if isinstance(price_value, (int, float)) and price_value > 0:
                        bidder_prices[bidder_name] = float(price_value)
                        self.logger.info(
                            f'从detailed_scores提取到投标人 {bidder_name} 的价格: {price_value}'
                        )
                        continue

                # 如果所有方法都失败，记录错误
                self.logger.error(
                    f'投标人 {bidder_name} 的价格提取失败，无法进行价格分计算'
                )
                self.logger.error(f'  extracted_price: {result.extracted_price}')
                self.logger.error(f'  detailed_scores: {result.detailed_scores}')

            except Exception as e:
                self.logger.error(
                    f'提取投标人 {result.bidder_name} 的价格信息时出错: {e}'
                )
                continue
                
        self.logger.info(f'成功提取到 {len(bidder_prices)} 个投标人的价格: {bidder_prices}')
        return bidder_prices

    def _extract_price_from_result(self, result) -> Optional[Dict[str, Any]]:
        """
        从分析结果中提取价格信息

        Args:
            result: AnalysisResult对象

        Returns:
            Optional[Dict[str, Any]]: 价格信息字典，包含'price'键
        """
        if not result.detailed_scores:
            return None

        # 查找价格分项
        def find_price_item(scores_list):
            if not isinstance(scores_list, list):
                return None

            for item in scores_list:
                # 检查是否为价格分项
                if (
                    item.get('is_price_criteria')
                    or '价格' in item.get('criteria_name', '')
                    or '价格分' in item.get('criteria_name', '')
                ):
                    return item
                # 递归检查子项
                if 'children' in item and item['children']:
                    price_item = find_price_item(item['children'])
                    if price_item:
                        return price_item
            return None

        price_item = find_price_item(result.detailed_scores)
        if price_item:
            # 从价格分项中提取价格信息
            price = None
            # 首先尝试从extracted_price字段获取
            if 'extracted_price' in price_item:
                price = price_item['extracted_price']
            # 如果没有，则尝试从score字段获取
            elif 'score' in price_item:
                price = price_item['score']

            # 确保价格是有效的正数
            if price is not None and isinstance(price, (int, float)) and price >= 0:
                return {'price': float(price), 'details': price_item}

        return None

    def _find_price_in_scores(self, scores: List[Dict[str, Any]]) -> Optional[float]:
        """
        递归查找价格分项

        Args:
            scores: 评分列表

        Returns:
            Optional[float]: 找到的价格，如果未找到则返回None
        """
        if not isinstance(scores, list):
            return None

        for score in scores:
            criteria_name = score.get('criteria_name', '').lower()

            # 检查是否是价格分项
            if any(
                keyword in criteria_name
                for keyword in ['价格', 'price', '报价', '投标报价']
            ) or score.get('is_price_criteria', False):
                # 优先从extracted_price字段获取价格
                if 'extracted_price' in score and isinstance(
                    score['extracted_price'], (int, float)
                ):
                    price_value = float(score['extracted_price'])
                    if price_value > 0:  # 确保是正数
                        return price_value

                # 如果extracted_price不存在，尝试从score字段获取价格
                if 'score' in score and isinstance(score['score'], (int, float)):
                    price_value = float(score['score'])
                    if price_value > 0:  # 确保是正数
                        return price_value

                # 递归检查子项
                if 'children' in score and score['children']:
                    child_price = self._find_price_in_scores(score['children'])
                    if child_price is not None and child_price > 0:
                        return child_price

        return None

    def _calculate_price_scores(
        self,
        bidder_prices: Dict[str, float],
        max_score: float,
        formula: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        根据价格计算公式计算各投标方的价格分

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula: 价格计算公式（可选）

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not bidder_prices:
            return {}

        # 如果有专门的价格计算公式，使用特殊计算方法
        if formula:
            formula_info = self._parse_price_formula(formula)
            if formula_info:
                return self._calculate_with_custom_formula(
                    bidder_prices, max_score, formula_info
                )

        # 使用默认计算方法：满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分
        min_price = min(bidder_prices.values())
        scores = {}

        for bidder, price in bidder_prices.items():
            if price == min_price:
                # 最低报价得满分
                scores[bidder] = max_score
                self.logger.info(
                    f'投标人 {bidder} 报价为最低价 {price}，得满分 {max_score}'
                )
            else:
                # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*满分
                try:
                    if price > 0:  # 防止除零错误
                        score = (min_price / price) * max_score
                        scores[bidder] = round(score, 2)
                        self.logger.info(
                            f'投标人 {bidder} 报价 {price}，得分 {scores[bidder]}'
                        )
                    else:
                        scores[bidder] = 0
                        self.logger.warning(f'投标人 {bidder} 报价为0或负数: {price}')
                except Exception as e:
                    scores[bidder] = 0
                    self.logger.error(f'计算投标人 {bidder} 的价格分时出错: {e}')

        return scores

    def _parse_price_formula(self, formula: str) -> Optional[Dict[str, Any]]:
        """
        解析价格计算公式

        Args:
            formula: 价格计算公式字符串

        Returns:
            Optional[Dict[str, Any]]: 解析后的公式信息
        """
        if not formula:
            return None

        # 简单的价格公式解析示例
        # 这里可以根据实际需求进行更复杂的解析
        return {'formula': formula, 'parsed': True}

    def _calculate_with_custom_formula(
        self,
        bidder_prices: Dict[str, float],
        max_score: float,
        formula_info: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        使用自定义公式计算价格分

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula_info: 公式信息

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        # 这里实现自定义公式计算逻辑
        # 目前使用默认计算方法作为示例
        return self._calculate_price_scores(bidder_prices, max_score, None)

    def _update_analysis_results(
        self, db, analysis_results, scores: Dict[str, float]
    ) -> int:
        """
        更新分析结果中的价格分

        Args:
            db: 数据库会话
            analysis_results: 分析结果列表
            scores: 价格分字典

        Returns:
            int: 更新的记录数
        """
        updated_count = 0
        for result in analysis_results:
            if result.bidder_name in scores:
                try:
                    result.price_score = scores[result.bidder_name]
                    # 同时更新总分
                    if result.detailed_scores:
                        # 计算除价格分外的其他分数总和
                        other_scores_total = 0

                        def calculate_other_scores(scores_list):
                            total = 0
                            for item in scores_list:
                                # 支持多种字段名检查
                                item_name = (
                                    item.get('Child_Item_Name')
                                    or item.get('criteria_name')
                                    or item.get('name', '')
                                )

                                if item.get('is_price_criteria') or '价格' in item_name:
                                    # 跳过价格分项
                                    continue
                                else:
                                    score = item.get('score', 0)
                                    if isinstance(score, (int, float)):
                                        total += float(score)
                                    # 递归处理子项
                                    if 'children' in item and item['children']:
                                        total += calculate_other_scores(
                                            item['children']
                                        )
                            return total

                        other_scores_total = calculate_other_scores(
                            result.detailed_scores
                        )
                        result.total_score = (
                            other_scores_total + scores[result.bidder_name]
                        )
                        updated_count += 1
                except Exception as e:
                    self.logger.error(
                        f'更新投标人 {result.bidder_name} 的价格分时出错: {e}'
                    )
                    continue
        return updated_count

    def _calculate_other_scores_total(self, detailed_scores: list) -> float:
        """
        计算除价格分外的其他分数总和

        Args:
            detailed_scores: 详细评分列表

        Returns:
            float: 其他分数总和
        """
        total = 0
        try:
            if not isinstance(detailed_scores, list):
                return total

            for item in detailed_scores:
                # 跳过价格分项 - 支持多种字段名检查
                item_name = (
                    item.get('Child_Item_Name')
                    or item.get('criteria_name')
                    or item.get('name', '')
                )

                if item.get('is_price_criteria') or '价格' in str(item_name):
                    continue

                # 累加分数
                score = item.get('score', 0)
                if isinstance(score, (int, float)):
                    total += float(score)

                # 递归处理子项
                if 'children' in item and isinstance(item['children'], list):
                    total += self._calculate_other_scores_total(item['children'])
        except Exception as e:
            self.logger.error(f'计算其他分数总和时出错: {e}')

        return total
