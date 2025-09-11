"""
价格分计算模块
负责在所有投标方分析完成后，根据评标规则进行综合价格分计算
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from modules.database import SessionLocal, AnalysisResult, ScoringRule


class PriceScoreCalculator:
    """价格分计算器"""

    def __init__(self, db_session=None):
        self.db_session = db_session
        self.logger = logging.getLogger(__name__)

    def calculate_project_price_scores(self, project_id: int) -> Dict[str, float]:
        """
        计算项目的价格分，需要等所有投标方分析完成后调用

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not self.db_session:
            db = SessionLocal()
            should_close = True
        else:
            db = self.db_session
            should_close = False

        try:
            # 1. 获取所有投标方的分析结果
            analysis_results = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            if not analysis_results:
                self.logger.warning(f'项目 {project_id} 没有找到分析结果')
                return {}

            # 2. 提取所有投标方的价格信息
            bidder_prices = {}
            for result in analysis_results:
                # 从detailed_scores中查找价格分项
                price_info = self._extract_price_from_result(result)
                if price_info and price_info.get('price') is not None:
                    bidder_prices[result.bidder_name] = price_info['price']
                elif result.extracted_price is not None:
                    # 使用直接提取的价格
                    bidder_prices[result.bidder_name] = result.extracted_price

            if not bidder_prices:
                self.logger.warning(f'项目 {project_id} 没有找到有效的投标价格')
                return {}

            # 3. 获取评分规则中的价格分规则
            price_rules = (
                db.query(ScoringRule)
                .filter(
                    ScoringRule.project_id == project_id,
                    ScoringRule.is_price_criteria == True
                )
                .all()
            )

            price_max_score = 40  # 默认值
            price_formula = None
            
            if price_rules:
                price_rule = price_rules[0]  # 通常只有一个价格评分规则
                price_max_score = price_rule.max_score
                price_formula = price_rule.price_formula
                self.logger.info(f"找到价格评分规则: 满分 {price_max_score}, 公式: {price_formula}")
            else:
                self.logger.warning(f'项目 {project_id} 没有找到价格评分规则，使用默认值')

            # 4. 计算价格分
            scores = self._calculate_price_scores(bidder_prices, price_max_score, price_formula)
            
            # 5. 更新数据库中的价格分
            for result in analysis_results:
                if result.bidder_name in scores:
                    result.price_score = scores[result.bidder_name]
                    # 同时更新总分
                    if result.detailed_scores:
                        total_score = sum(
                            item.get('score', 0) 
                            for item in result.detailed_scores 
                            if item.get('criteria_name') != '价格分'
                        )
                        result.total_score = total_score + scores[result.bidder_name]
            
            if should_close:
                db.commit()
                
            return scores

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}', exc_info=True)
            if should_close:
                db.rollback()
            return {}
        finally:
            if should_close:
                db.close()

    def _extract_price_from_result(self, result: AnalysisResult) -> Optional[Dict[str, Any]]:
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
        for item in result.detailed_scores:
            if item.get('is_price_criteria') or '价格' in item.get('criteria_name', ''):
                return {
                    'price': item.get('price') or item.get('score'),
                    'details': item
                }
        
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
                    return float(score['extracted_price'])

                # 如果extracted_price不存在，尝试从score字段获取价格
                if 'score' in score and isinstance(score['score'], (int, float)):
                    return float(score['score'])

            # 递归查找子项
            if 'children' in score and score['children']:
                child_price = self._find_price_in_scores(score['children'])
                if child_price is not None:
                    return child_price

        return None

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
        formula_info: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        使用自定义公式计算价格分
        
        Args:
            bidder_prices: 投标方价格
            price_max_score: 价格分满分
            formula_info: 公式信息
            
        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        scores = {}
        
        # 获取变量定义
        variables = formula_info.get('variables', {})
        benchmark_definition = variables.get('benchmark_price', '最低报价')
        
        # 确定评标基准价
        benchmark_price = None
        if '最低' in benchmark_definition:
            benchmark_price = min(bidder_prices.values())
        else:
            # 默认使用最低报价作为评标基准价
            benchmark_price = min(bidder_prices.values())
            
        self.logger.info(f"评标基准价定义: {benchmark_definition}, 实际评标基准价: {benchmark_price}")

        # 根据公式计算每个投标人的价格分
        formula = formula_info.get('formula', '')
        description = formula_info.get('description', '')
        
        # 如果公式中包含特定的计算方式，则按该方式计算
        if '评标基准价/投标报价' in formula or '基准价/报价' in formula:
            self.logger.info("使用 评标基准价/投标报价 的计算方式")
            for bidder, price in bidder_prices.items():
                # 投标报价得分＝（评标基准价/投标报价）*价格分满分
                score = (benchmark_price / price) * price_max_score
                scores[bidder] = round(score, 2)
                self.logger.info(f"投标人 {bidder} 报价 {price}，得分 {scores[bidder]}")
        else:
            # 使用AI辅助计算（如果需要更复杂的计算）
            self.logger.info("使用AI辅助计算价格分")
            scores = self._calculate_with_ai_assistance(bidder_prices, price_max_score, formula_info)
            
        return scores

    def _calculate_with_ai_assistance(
        self, 
        bidder_prices: Dict[str, float], 
        price_max_score: float, 
        formula_info: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        使用AI辅助计算价格分
        
        Args:
            bidder_prices: 投标方价格
            price_max_score: 价格分满分
            formula_info: 公式信息
            
        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        # 这里可以实现更复杂的AI辅助计算逻辑
        # 目前我们简化处理，使用默认方法
        return self._calculate_with_default_method(bidder_prices, price_max_score)

    def _calculate_with_default_method(
        self, 
        bidder_prices: Dict[str, float], 
        price_max_score: float
    ) -> Dict[str, float]:
        """
        使用默认方法计算价格分
        
        Args:
            bidder_prices: 投标方价格
            price_max_score: 价格分满分
            
        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        scores = {}
        # 找到最低价格作为评标基准价
        min_price = min(bidder_prices.values())
        self.logger.info(f"评标基准价: {min_price}")

        for bidder, price in bidder_prices.items():
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

    def _calculate_price_scores(
        self, 
        bidder_prices: Dict[str, float], 
        price_max_score: float, 
        price_formula: Optional[str] = None,
        price_description: Optional[str] = None
    ) -> Dict[str, float]:
        """
        计算各投标方的价格分
        
        Args:
            bidder_prices: 投标方名称到价格的映射
            price_max_score: 价格分满分
            price_formula: 价格计算公式（如果有）
            price_description: 价格评分描述（如果有）
            
        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not bidder_prices:
            return {}

        scores = {}
        
        # 解析价格计算公式和变量定义
        formula_info = self._parse_price_formula(price_formula, price_description)
        
        # 如果有专门的价格计算公式，使用AI辅助计算
        if formula_info and formula_info.get('formula') and formula_info.get('variables'):
            self.logger.info("使用专门的价格计算公式进行计算")
            scores = self._calculate_with_custom_formula(bidder_prices, price_max_score, formula_info)
        else:
            # 使用默认计算方法
            self.logger.info("使用默认价格计算方法")
            scores = self._calculate_with_default_method(bidder_prices, price_max_score)
                
        return scores

    def _update_price_scores_in_db(
        self, analysis_results: List[AnalysisResult], price_scores: Dict[str, float], db
    ):
        """
        更新数据库中的价格分和总分

        Args:
            analysis_results: 分析结果列表
            price_scores: 价格分映射
            db: 数据库会话
        """
        try:
            for result in analysis_results:
                bidder_name = result.bidder_name
                if bidder_name in price_scores:
                    new_price_score = price_scores[bidder_name]
                    
                    detailed_scores = result.detailed_scores
                    if isinstance(detailed_scores, str):
                        import json
                        detailed_scores = json.loads(detailed_scores)

                    # 查找旧的价格分，以便正确调整总分
                    old_price_score = self._find_existing_price_score(detailed_scores)

                    # 更新detailed_scores中的价格分项
                    updated_scores = self._update_price_in_scores(
                        detailed_scores, new_price_score
                    )
                    result.detailed_scores = json.dumps(
                        updated_scores, ensure_ascii=False
                    )

                    # 更新AnalysisResult的price_score字段
                    result.price_score = new_price_score

                    # 通过调整现有总分来重新计算总分
                    old_total_score = result.total_score if result.total_score is not None else 0.0
                    # 新总分 = 旧总分 - 旧价格分 + 新价格分
                    new_total_score = old_total_score - old_price_score + new_price_score
                    result.total_score = round(new_total_score, 2)

            db.commit()
            self.logger.info(f'成功更新了 {len(price_scores)} 个投标方的价格分和总分')

        except Exception as e:
            self.logger.error(f'更新数据库中的价格分时出错: {e}')
            db.rollback()

    def _find_existing_price_score(self, scores: List[Dict[str, Any]]) -> float:
        """
        递归查找并返回现有价格项的分数。
        """
        if not isinstance(scores, list):
            return 0.0

        for score in scores:
            criteria_name = score.get('criteria_name', '').lower()
            is_price_criteria = (
                any(keyword in criteria_name for keyword in ['价格', 'price', '报价', '投标报价']) 
                or score.get('is_price_criteria', False)
            )
            
            if is_price_criteria and 'score' in score:
                return float(score.get('score', 0.0))
            
            if 'children' in score and score['children']:
                child_price_score = self._find_existing_price_score(score['children'])
                # 假设只有一个价格项，找到就返回
                if child_price_score != 0.0:
                    return child_price_score
                    
        return 0.0

    def _update_price_in_scores(
        self, scores: List[Dict[str, Any]], new_price_score: float
    ) -> List[Dict[str, Any]]:
        """
        更新评分中的价格分

        Args:
            scores: 评分列表
            new_price_score: 新的价格分

        Returns:
            List[Dict[str, Any]]: 更新后的评分列表
        """
        if not isinstance(scores, list):
            return scores

        updated_scores = []
        for score in scores:
            updated_score = score.copy()
            criteria_name = score.get('criteria_name', '').lower()

            # 检查是否是价格分项
            if any(
                keyword in criteria_name
                for keyword in ['价格', 'price', '报价', '投标报价']
            ) or score.get('is_price_criteria', False):
                updated_score['score'] = new_price_score
                updated_score['reason'] = (
                    f'根据评标规则重新计算的价格分: {new_price_score}'
                )
                updated_score['is_price_criteria'] = True  # 确保标记为价格分项

            # 递归更新子项
            if 'children' in score and score['children']:
                updated_score['children'] = self._update_price_in_scores(
                    score['children'], new_price_score
                )

                # 重新计算父项分数（如果子项中包含价格分，则需要特殊处理）
                if updated_score['children']:
                    children_scores = []
                    price_child_found = False
                    for child in updated_score['children']:
                        # 如果子项是价格分项，则使用新计算的价格分
                        if (any(keyword in child.get('criteria_name', '').lower() 
                                for keyword in ['价格', 'price', '报价', '投标报价']) 
                            or child.get('is_price_criteria', False)):
                            children_scores.append(new_price_score)
                            price_child_found = True
                        else:
                            children_scores.append(child.get('score', 0))
                    
                    # 如果找到价格分项子节点，则父节点分数为其他子节点分数之和加上价格分
                    if price_child_found:
                        updated_score['score'] = sum(children_scores)
                    # 否则按正常方式计算父节点分数
                    elif not (any(keyword in criteria_name 
                                for keyword in ['价格', 'price', '报价', '投标报价']) 
                            or score.get('is_price_criteria', False)):
                        updated_score['score'] = sum(child.get('score', 0) for child in updated_score['children'])

            updated_scores.append(updated_score)

        return updated_scores

    


# 测试代码
if __name__ == '__main__':
    calculator = PriceScoreCalculator()
    # 这里可以添加测试代码
    pass
