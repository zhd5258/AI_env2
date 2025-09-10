"""
价格分计算模块
负责在所有投标方分析完成后，根据评标规则进行综合价格分计算
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
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
                if price_info:
                    bidder_prices[result.bidder_name] = price_info

            if not bidder_prices:
                self.logger.warning(f'项目 {project_id} 没有找到有效的价格信息')
                return {}

            # 3. 获取价格分的满分和计算公式
            price_max_score, price_formula = self._get_price_rule_info(project_id, db)

            # 4. 计算价格分
            price_scores = self._calculate_price_scores(
                bidder_prices, price_max_score, price_formula
            )

            # 5. 更新数据库中的价格分
            self._update_price_scores_in_db(analysis_results, price_scores, db)

            return price_scores

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 价格分时出错: {e}')
            return {}
        finally:
            if should_close:
                db.close()

    def _extract_price_from_result(self, result: AnalysisResult) -> Optional[float]:
        """
        从分析结果中提取价格信息

        Args:
            result: 分析结果对象

        Returns:
            Optional[float]: 提取到的价格，如果未找到则返回None
        """
        try:
            # 首先尝试从result.extracted_price获取价格
            if result.extracted_price is not None:
                return float(result.extracted_price)

            # 从detailed_scores中查找价格分项
            detailed_scores = result.detailed_scores
            if isinstance(detailed_scores, str):
                import json

                detailed_scores = json.loads(detailed_scores)

            # 递归查找价格分项
            price = self._find_price_in_scores(detailed_scores)
            if price is not None:
                return price

            return None

        except Exception as e:
            self.logger.error(f'从分析结果中提取价格时出错: {e}')
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

    def _get_price_rule_info(self, project_id: int, db) -> Tuple[float, Optional[str]]:
        """
        获取价格分的满分和计算公式

        Args:
            project_id: 项目ID
            db: 数据库会话

        Returns:
            Tuple[float, Optional[str]]: (价格分的满分, 价格计算公式)
        """
        try:
            # 从评分规则中查找价格分的满分和公式
            scoring_rules = (
                db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
            )

            for rule in scoring_rules:
                criteria_name = rule.criteria_name.lower()
                if any(
                    keyword in criteria_name
                    for keyword in ['价格', 'price', '报价', '投标报价']
                ):
                    # 价格计算公式存储在description字段
                    formula = rule.description
                    self.logger.info(f'项目 {project_id} 找到价格分计算公式: {formula}')
                    return float(rule.max_score), formula

            # 如果没有找到，返回默认值
            self.logger.warning(
                f'项目 {project_id} 未找到价格分计算规则，将使用默认规则'
            )
            return 40.0, None

        except Exception as e:
            self.logger.error(f'获取价格分满分和公式时出错: {e}')
            return 40.0, None

    def _calculate_price_scores(
        self,
        bidder_prices: Dict[str, float],
        price_max_score: float,
        formula: Optional[str],
    ) -> Dict[str, float]:
        """
        根据从招标文件提取的评标规则计算价格分

        Args:
            bidder_prices: 投标方价格映射
            price_max_score: 价格分满分
            formula: 价格分计算公式 (例如: "(min_price / price) * price_max_score")

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not bidder_prices:
            return {}

        # 筛选出有效的价格（大于0）
        valid_prices = {
            bidder: price for bidder, price in bidder_prices.items() if price > 0
        }
        if not valid_prices:
            self.logger.warning('没有找到任何有效的投标报价（大于0）')
            return {bidder: 0.0 for bidder in bidder_prices}

        # 找到最低价格作为评标基准价
        min_price = min(valid_prices.values())

        # 如果没有提供公式，则使用默认的线性插值法
        if not formula:
            formula = '(min_price / price) * price_max_score'
            self.logger.info(f'使用默认价格分计算公式: {formula}')

        price_scores = {}
        for bidder, price in bidder_prices.items():
            # 对于无效报价（0或None），价格分直接给0
            if price is None or price <= 0:
                price_scores[bidder] = 0.0
                continue

            try:
                # 为eval准备一个安全的环境
                safe_dict = {
                    'min_price': min_price,
                    'price': price,
                    'price_max_score': price_max_score,
                    'round': round,
                    'min': min,
                    'max': max,
                }
                # 执行计算
                score = eval(formula, {'__builtins__': {}}, safe_dict)
                # 确保分数不会超过满分
                price_scores[bidder] = round(min(score, price_max_score), 2)

            except Exception as e:
                self.logger.error(
                    f"执行价格分公式 '{formula}' 时出错 (bidder: {bidder}): {e}. "
                    f'将使用默认公式进行回退计算。'
                )
                # 回退到默认公式
                score = (min_price / price) * price_max_score
                price_scores[bidder] = round(min(score, price_max_score), 2)

        return price_scores

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
