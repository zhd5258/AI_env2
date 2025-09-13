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
                updated_count = self._update_analysis_results(db, analysis_results, scores)
                
                db.commit()
                self.logger.info(f'成功更新了 {updated_count} 个投标人的价格分')
                return scores

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}', exc_info=True)
            return {}

# 测试代码
if __name__ == '__main__':
    calculator = PriceScoreCalculator()
    # 这里可以添加测试代码
    pass
