from modules.enhanced_price_extractor import EnhancedPriceExtractor
from typing import List, Dict, Any, Optional
import logging


class PriceManager:
    def __init__(self):
        self.price_extractor = EnhancedPriceExtractor()
        self.logger = logging.getLogger(__name__)

    def extract_prices_from_content(self, pages: List[str]) -> List[Dict[str, Any]]:
        prices = self.price_extractor.extract_enhanced_prices(pages)
        return self._deduplicate_prices(prices)

    def select_best_price(
        self, prices: List[Dict[str, Any]], pages: List[str]
    ) -> float:
        intelligent_prices = []
        for price_info in prices:
            page_index = price_info['page']
            # Create a context of the current page and the next one if it exists
            context = pages[page_index]
            if page_index + 1 < len(pages):
                context += '\n' + pages[page_index + 1]

            if self.price_extractor._is_total_price_intelligent(
                context, price_info['value']
            ):
                intelligent_prices.append(price_info['value'])

        if intelligent_prices:
            return max(intelligent_prices)

        # Fallback to the simple method if no intelligent price is found
        return self.price_extractor.select_best_total_price(prices)

    def _deduplicate_prices(self, prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Deduplicate based on price value, keeping the first occurrence (lowest page number)
        seen = set()
        deduplicated = []
        for price_info in prices:
            if price_info['value'] not in seen:
                seen.add(price_info['value'])
                deduplicated.append(price_info)
        # Sort by value, descending
        return sorted(deduplicated, key=lambda p: p['value'], reverse=True)

    def calculate_project_price_scores(self, project_prices, tender_rules):
        """
        计算项目价格分，严格按照评标规则：
        满足招标文件要求且投标报价最低的投标报价为评标基准价，其价格分为满分。
        其他投标人的价格分统一按照下列公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100
        """
        if not project_prices:
            return {}

        scores = {}
        # 找到最低价格作为评标基准价
        min_price = min(project_prices.values())

        # 价格分满分（通常是40分，但需要从评分规则中获取）
        price_max_score = 40  # 默认40分，实际应该从tender_rules中获取
        price_formula = None
        price_description = None

        # 从评分规则中查找价格分的满分和计算公式
        if tender_rules:
            for rule in tender_rules:
                if (
                    '价格' in rule.get('criteria_name', '')
                    or 'price' in rule.get('criteria_name', '').lower()
                ):
                    price_max_score = rule.get('max_score', 40)
                    price_formula = rule.get('price_formula', None)
                    price_description = rule.get('description', '')
                    break

        self.logger.info(f"价格分计算 - 满分: {price_max_score}, 公式: {price_formula}")

        # 解析价格计算公式和变量定义
        formula_info = self._parse_price_formula(price_formula, price_description)
        
        # 如果有专门的价格计算公式，使用特殊计算方法
        if formula_info and formula_info.get('formula'):
            scores = self._calculate_with_custom_formula(project_prices, price_max_score, formula_info, min_price)
        else:
            # 使用默认计算方法
            for bidder, price in project_prices.items():
                if price == min_price:
                    # 最低报价得满分
                    scores[bidder] = price_max_score
                    self.logger.info(f"投标人 {bidder} 报价为最低价 {price}，得满分 {price_max_score}")
                else:
                    # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*满分
                    score = (min_price / price) * price_max_score
                    scores[bidder] = round(score, 2)
                    self.logger.info(f"投标人 {bidder} 报价 {price}，得分 {scores[bidder]}")

        return scores

    def _parse_price_formula(self, price_formula: Optional[str], price_description: Optional[str]) -> Optional[Dict[str, Any]]:
        """
        解析价格计算公式和变量定义
        
        Args:
            price_formula: 价格计算公式
            price_description: 价格评分描述
            
        Returns:
            Optional[Dict[str, Any]]: 包含公式和变量定义的字典
        """
        if not price_formula and not price_description:
            return None
            
        # 尝试从AI分析的结果中提取公式和变量定义
        formula_info = {
            'formula': price_formula,
            'description': price_description,
            'variables': {}
        }
        
        # 如果有描述信息，尝试从中提取变量定义
        if price_description:
            # 简单的变量提取逻辑（实际应用中可能需要更复杂的处理）
            variables = {}
            
            # 查找类似"评标基准价"的变量定义
            import re
            benchmark_pattern = r'(评标基准价|基准价)[^\n]*?([最低报价|最低评标价|满足要求的最低价])'
            benchmark_match = re.search(benchmark_pattern, price_description)
            if benchmark_match:
                variables['benchmark_price'] = benchmark_match.group(2)
                
            # 查找满分定义
            max_score_pattern = r'(\d+(?:\.\d+)?)\s*分|满分\s*(\d+(?:\.\d+)?)'
            max_score_match = re.search(max_score_pattern, price_description)
            if max_score_match:
                score = max_score_match.group(1) or max_score_match.group(2)
                if score:
                    variables['max_score'] = float(score)
            
            formula_info['variables'] = variables
            
        return formula_info

    def _calculate_with_custom_formula(
        self, 
        bidder_prices: Dict[str, float], 
        price_max_score: float, 
        formula_info: Dict[str, Any],
        benchmark_price: float
    ) -> Dict[str, float]:
        """
        使用自定义公式计算价格分
        
        Args:
            bidder_prices: 投标方价格
            price_max_score: 价格分满分
            formula_info: 公式信息
            benchmark_price: 评标基准价
            
        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        scores = {}
        
        # 获取变量定义
        variables = formula_info.get('variables', {})
        benchmark_definition = variables.get('benchmark_price', '最低报价')
        
        self.logger.info(f"评标基准价定义: {benchmark_definition}, 实际评标基准价: {benchmark_price}")

        # 根据公式计算每个投标人的价格分
        formula = formula_info.get('formula', '')
        description = formula_info.get('description', '')
        
        # 如果公式中包含特定的计算方式，则按该方式计算
        import re
        if '评标基准价/投标报价' in formula or '基准价/报价' in formula:
            self.logger.info("使用 评标基准价/投标报价 的计算方式")
            for bidder, price in bidder_prices.items():
                # 投标报价得分＝（评标基准价/投标报价）*价格分满分
                score = (benchmark_price / price) * price_max_score
                scores[bidder] = round(score, 2)
                self.logger.info(f"投标人 {bidder} 报价 {price}，得分 {scores[bidder]}")
        else:
            # 使用默认方法计算
            self.logger.info("使用默认价格计算方法")
            for bidder, price in bidder_prices.items():
                if price == benchmark_price:
                    # 最低报价得满分
                    scores[bidder] = price_max_score
                    self.logger.info(f"投标人 {bidder} 报价为最低价 {price}，得满分 {price_max_score}")
                else:
                    # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*满分
                    score = (benchmark_price / price) * price_max_score
                    scores[bidder] = round(score, 2)
                    self.logger.info(f"投标人 {bidder} 报价 {price}，得分 {scores[bidder]}")
            
        return scores