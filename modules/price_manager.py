from modules.enhanced_price_extractor import EnhancedPriceExtractor
from typing import List, Dict, Any


class PriceManager:
    def __init__(self):
        self.price_extractor = EnhancedPriceExtractor()

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

        # 从评分规则中查找价格分的满分
        if tender_rules:
            for rule in tender_rules:
                if (
                    '价格' in rule.get('criteria_name', '')
                    or 'price' in rule.get('criteria_name', '').lower()
                ):
                    price_max_score = rule.get('max_score', 40)
                    break

        for bidder, price in project_prices.items():
            if price == min_price:
                # 最低报价得满分
                scores[bidder] = price_max_score
            else:
                # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100
                # 这里直接乘以满分，因为公式中的40%已经体现在满分设置中
                score = (min_price / price) * price_max_score
                scores[bidder] = round(score, 2)

        return scores
