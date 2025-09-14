"""
价格分计算模块
负责在所有投标方分析完成后，根据评标规则进行综合价格分计算
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

from modules.database import SessionLocal, AnalysisResult, ScoringRule
from modules.price_calculator_helpers import PriceScoreCalculatorHelpers


class PriceScoreCalculator(PriceScoreCalculatorHelpers):
    """价格分计算器"""

    def __init__(self, db_session=None):
        # 先初始化logger，再调用父类的__init__()
        self.logger = logging.getLogger(__name__)
        super().__init__()
        self.db_session = db_session
        
    @contextmanager
    def _get_db_session(self):
        """
        数据库会话上下文管理器，确保会话正确关闭
        """
        if self.db_session:
            yield self.db_session
        else:
            db = SessionLocal()
            try:
                yield db
            except Exception as e:
                db.rollback()
                raise e
            finally:
                db.close()

    def calculate_project_price_scores(self, project_id: int) -> Dict[str, float]:
        """
        计算项目的价格分，需要等所有投标方分析完成后调用

        Args:
            project_id: 项目ID

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        try:
            with self._get_db_session() as db:
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
                bidder_prices = self._extract_bidder_prices(analysis_results)

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
                    price_max_score = price_rule.Parent_max_score
                    price_formula = price_rule.price_formula
                    self.logger.info(f"找到价格评分规则: 满分 {price_max_score}, 公式: {price_formula}")
                else:
                    self.logger.warning(f'项目 {project_id} 没有找到价格评分规则，使用默认值')

                # 4. 计算价格分
                scores = self._calculate_price_scores(bidder_prices, price_max_score, price_formula)
                
                # 5. 更新数据库中的价格分
                self._update_analysis_results(db, analysis_results, scores)
                
                db.commit()
                self.logger.info(f'成功计算了 {len(scores)} 个投标人的价格分')
                return scores

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}', exc_info=True)
            return {}

    def _update_analysis_results(self, db, analysis_results: List[AnalysisResult], price_scores: Dict[str, float]):
        """
        更新分析结果中的价格分

        Args:
            db: 数据库会话
            analysis_results: 分析结果列表
            price_scores: 价格分映射
        """
        try:
            updated_count = 0
            for result in analysis_results:
                bidder_name = result.bidder_name
                if bidder_name in price_scores:
                    try:
                        # 获取当前的价格分，用于计算总分调整
                        old_price_score = result.price_score if result.price_score is not None else 0.0
                        new_price_score = price_scores[bidder_name]

                        # 更新详细评分中的价格分
                        detailed_scores = result.detailed_scores
                        if isinstance(detailed_scores, str):
                            try:
                                detailed_scores = json.loads(detailed_scores)
                            except (json.JSONDecodeError, TypeError) as e:
                                self.logger.error(f"解析 {bidder_name} 的 detailed_scores 时出错: {e}")
                                continue
                        
                        # 确保 detailed_scores 是列表或字典类型
                        if not isinstance(detailed_scores, (list, dict)):
                            self.logger.warning(f"{bidder_name} 的 detailed_scores 不是列表或字典类型: {type(detailed_scores)}")
                            continue
                        
                        # 更新详细评分中的价格项
                        updated_scores = self._update_price_in_scores(detailed_scores, new_price_score)
                        
                        # 保存更新后的评分
                        result.detailed_scores = json.dumps(updated_scores, ensure_ascii=False)
                        
                        # 更新AnalysisResult的price_score字段
                        result.price_score = new_price_score
                        
                        # 通过调整现有总分来重新计算总分
                        old_total_score = result.total_score if result.total_score is not None else 0.0
                        # 新总分 = 旧总分 - 旧价格分 + 新价格分
                        new_total_score = old_total_score - old_price_score + new_price_score
                        result.total_score = round(new_total_score, 2)
                        
                        updated_count += 1
                        
                    except Exception as e:
                        self.logger.error(f'更新投标人 {bidder_name} 的价格分时出错: {e}')
                        continue

            db.commit()
            self.logger.info(f'成功更新了 {updated_count} 个投标方的价格分和总分')

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
            # 确保score是字典类型
            if not isinstance(score, dict):
                continue
                
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

    def _update_price_in_scores(self, scores: Union[List[Dict[str, Any]], Dict[str, Any]], new_price_score: float) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        更新评分中的价格分

        Args:
            scores: 评分列表或字典
            new_price_score: 新的价格分

        Returns:
            Union[List[Dict[str, Any]], Dict[str, Any]]: 更新后的评分
        """
        # 如果scores是字典格式（新格式），直接更新价格分
        if isinstance(scores, dict):
            updated_scores = {}
            for key, value in scores.items():
                # 检查键是否包含价格相关关键词
                if any(keyword in key for keyword in ['价格', 'price', '报价', '投标报价']):
                    updated_scores[key] = new_price_score
                else:
                    updated_scores[key] = value
            return updated_scores
        
        # 如果scores是列表格式（旧格式），按原来的方式处理
        if not isinstance(scores, list):
            return scores

        updated_scores = []
        for score in scores:
            # 确保score是字典类型
            if not isinstance(score, dict):
                updated_scores.append(score)
                continue
                
            updated_score = score.copy()
            criteria_name = score.get('criteria_name', '').lower()

            # 检查是否是价格分项
            if (any(keyword in criteria_name for keyword in ['价格', 'price', '报价', '投标报价']) or 
                score.get('is_price_criteria', False)):
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

            updated_scores.append(updated_score)

        return updated_scores

# 测试代码
if __name__ == '__main__':
    calculator = PriceScoreCalculator()
    # 这里可以添加测试代码
    pass