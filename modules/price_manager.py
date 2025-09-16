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
        # 首先检查是否有来自"投标一览表"页面的高置信度价格
        summary_page_prices = [p for p in prices if '价格一览表' in p.get('reason', '') and p.get('confidence', 0) >= 90]
        if summary_page_prices:
            # 从"投标一览表"中选择置信度最高的价格
            summary_page_prices.sort(key=lambda x: x['confidence'], reverse=True)
            return summary_page_prices[0]['value']

        # 然后检查智能判断的价格
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
                # 修复字段引用，使用ScoringRule对象的属性而不是字典方法
                criteria_name = rule.Parent_Item_Name if hasattr(rule, 'Parent_Item_Name') else ''
                if (
                    '价格' in criteria_name
                    or 'price' in criteria_name.lower()
                ):
                    price_max_score = rule.Parent_max_score if hasattr(rule, 'Parent_max_score') else 40
                    price_formula = rule.price_formula if hasattr(rule, 'price_formula') else None
                    price_description = rule.description if hasattr(rule, 'description') else ''
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
        # 优先使用price_formula，如果没有则使用price_description
        formula_source = price_formula or price_description
        
        if not formula_source:
            return None
            
        # 尝试从AI分析的结果中提取公式和变量定义
        formula_info = {
            'formula': formula_source,
            'description': price_description,
            'variables': {}
        }
        
        # 解析AI返回的格式
        if '价格计算公式:' in formula_source or '1. 价格计算公式:' in formula_source:
            # AI返回的格式，提取各部分内容
            lines = formula_source.split('\n')
            for line in lines:
                if '价格计算公式:' in line:
                    formula_part = line.split('价格计算公式:', 1)[1].strip()
                    if formula_part:
                        formula_info['formula'] = formula_part
                elif '变量定义:' in line:
                    definition_part = line.split('变量定义:', 1)[1].strip()
                    if definition_part:
                        formula_info['variables']['definition'] = definition_part
                elif '计算说明:' in line:
                    explanation_part = line.split('计算说明:', 1)[1].strip()
                    if explanation_part:
                        formula_info['variables']['explanation'] = explanation_part
        
        # 如果没有从AI格式中提取到公式，尝试其他方式
        if formula_info['formula'] == formula_source and ':' in formula_source:
            # 可能是简单的描述文本，尝试从中提取公式
            # 查找包含等号或数学运算符的行作为公式
            lines = formula_source.split('\n')
            for line in lines:
                if '=' in line or ('/' in line and '×' in line) or ('/' in line and '*' in line):
                    formula_info['formula'] = line.strip()
                    break
        
        # 如果有描述信息，尝试从中提取变量定义
        description_text = price_description or ""
        if description_text:
            # 简单的变量提取逻辑（实际应用中可能需要更复杂的处理）
            variables = {}
            
            # 查找类似"评标基准价"的变量定义
            import re
            benchmark_pattern = r'(评标基准价|基准价)[^\n]*?([最低报价|最低评标价|满足要求的最低价|平均值])'
            benchmark_match = re.search(benchmark_pattern, description_text)
            if benchmark_match:
                variables['benchmark_price'] = benchmark_match.group(2)
                
            # 查找满分定义
            max_score_pattern = r'(\d+(?:\.\d+)?)\s*分|满分\s*(\d+(?:\.\d+)?)'
            max_score_match = re.search(max_score_pattern, description_text)
            if max_score_match:
                score = max_score_match.group(1) or max_score_match.group(2)
                if score:
                    variables['max_score'] = float(score)
            
            # 如果之前没有设置变量，使用新提取的变量
            if not formula_info['variables']:
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
        
        # 记录发送给AI大模型的完整prompt和返回值
        self.logger.info(f"发送给AI大模型的价格分计算请求:")
        self.logger.info(f"  公式: {formula}")
        self.logger.info(f"  描述: {description}")
        self.logger.info(f"  变量定义: {variables}")
        self.logger.info(f"  投标人报价: {bidder_prices}")
        self.logger.info(f"  评标基准价: {benchmark_price}")
        self.logger.info(f"  价格分满分: {price_max_score}")
        
        # 如果没有提供公式，记录错误并返回空结果
        if not formula:
            self.logger.error("没有提供有效的价格计算公式，无法计算价格分")
            return scores
            
        # 这里应该调用AI大模型来计算价格分，而不是硬编码计算逻辑
        # 目前记录详细信息，后续需要实现AI大模型调用
        self.logger.warning("价格分计算应通过AI大模型完成，当前实现返回空结果")
        self.logger.info(f"应发送给AI大模型的信息: 公式={formula}, 投标人报价={bidder_prices}, 满分={price_max_score}, 评标基准价={benchmark_price}")
            
        return scores
