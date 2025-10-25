#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
统一综合计算器模块
整合价格分计算和需要综合计算的定量规则处理
"""

import logging
import json
import datetime
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from models.database import ScoringRule, AnalysisResult, TenderProject
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.logging_config import get_logger
from modules.price_score_calculator import PriceScoreCalculator


class UnifiedComprehensiveCalculator:
    """统一综合计算器，整合价格分计算和需要综合分析的定量规则处理"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.ai_analyzer = LocalAIAnalyzer()
        self.logger = get_logger(__name__)

    def execute_comprehensive_calculation(self, project_id: int) -> bool:
        """
        执行统一的综合计算，包括价格分和需要综合分析的规则

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功执行综合计算
        """
        try:
            self.logger.info(f'开始执行项目 {project_id} 的统一综合计算')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 1. 获取项目信息
            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if not project:
                self.logger.error(f'项目 {project_id} 不存在')
                return False

            # 2. 获取所有分析结果
            analysis_results = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            if not analysis_results:
                self.logger.warning(f'项目 {project_id} 没有找到分析结果')
                return False

            # 3. 执行价格分计算（使用专门的价格分计算器）
            price_calculation_success = (
                self._calculate_price_scores_with_dedicated_calculator(project_id)
            )

            # 4. 执行需要综合分析的规则计算
            comprehensive_calculation_success = (
                self._calculate_comprehensive_analysis_rules(
                    project_id, analysis_results
                )
            )

            # 5. 更新项目状态
            if price_calculation_success and comprehensive_calculation_success:
                self._update_project_status(project_id)
                self.logger.info(f'项目 {project_id} 统一综合计算执行完成')
                return True
            else:
                self.logger.error(f'项目 {project_id} 统一综合计算执行失败')
                return False

        except Exception as e:
            self.logger.error(f'执行统一综合计算时出错: {e}', exc_info=True)
            return False

    def _calculate_price_scores_with_dedicated_calculator(
        self, project_id: int
    ) -> bool:
        """
        使用专用的价格分计算器计算价格分

        Args:
            project_id: 项目ID

        Returns:
            bool: 计算是否成功
        """
        try:
            # 获取项目信息用于日志记录
            project = self.db.query(TenderProject).filter(TenderProject.id == project_id).first()
            project_name = project.name if project and hasattr(project, 'name') else f"项目{project_id}"
            
            self.logger.info(f'项目 [{project_name}]: 使用专用价格分计算器计算价格分')
            
            # 创建价格分计算器实例
            price_calculator = PriceScoreCalculator(db_session=self.db)

            # 执行价格分计算
            success = price_calculator.calculate_project_price_scores(project_id)

            if success:
                self.logger.info(f'项目 [{project_name}]: 价格分计算成功')
            else:
                self.logger.error(f'项目 [{project_name}]: 价格分计算失败')

            return success
        except Exception as e:
            self.logger.error(f'项目 {project_id}: 价格分计算出错: {str(e)}', exc_info=True)
            return False

    def _calculate_price_scores(
        self, project_id: int, analysis_results: List[AnalysisResult]
    ) -> bool:
        """
        计算价格分（保留此方法以保持向后兼容性，但实际使用专门的计算器）

        Args:
            project_id: 项目ID
            analysis_results: 分析结果列表

        Returns:
            bool: 是否成功计算价格分
        """
        try:
            self.logger.info(f'=== 开始计算项目 {project_id} 的价格分 ===')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 1. 获取价格评分规则
            price_rule = (
                self.db.query(ScoringRule)
                .filter(
                    ScoringRule.project_id == project_id,
                    ScoringRule.is_price_criteria == True,
                )
                .first()
            )

            if not price_rule:
                self.logger.warning(
                    f'项目 {project_id} 没有找到价格评分规则，跳过价格分计算。'
                )
                return True

            # 2. 提取所有投标人的有效报价
            bidder_prices = {}
            for result in analysis_results:
                if (
                    result.bidder_name
                    and result.extracted_price is not None
                    and result.extracted_price > 0
                ):
                    bidder_prices[result.bidder_name] = float(result.extracted_price)

            if not bidder_prices:
                self.logger.warning(
                    f'项目 {project_id} 没有有效的投标人报价，所有价格分记为0。'
                )
                for result in analysis_results:
                    result.price_score = 0.0
                if self.db:
                    self.db.commit()
                return True

            # 3. 使用默认的、可靠的编程方法计算价格分
            price_scores = self._fallback_price_calculation(price_rule, bidder_prices)

            if not price_scores:
                self.logger.error(f'项目 {project_id}: 价格分计算失败。')
                return False

            # 4. 更新每个投标人的价格分和总分
            for result in analysis_results:
                bidder_name = result.bidder_name
                new_price_score = price_scores.get(bidder_name, 0.0)

                # 更新价格分
                old_price_score = result.price_score or 0
                result.price_score = new_price_score

                # 更新总分 (总分 = 原总分 - 旧价格分 + 新价格分)
                # 假设原总分已经包含了其他所有非价格项的得分
                current_total_score = result.total_score or 0
                new_total_score = (
                    current_total_score - old_price_score
                ) + new_price_score
                result.total_score = round(new_total_score, 2)

                self.logger.info(
                    f"更新投标人 '{bidder_name}': 价格分 {old_price_score} -> {new_price_score}, 总分 {current_total_score} -> {new_total_score}"
                )

            if self.db:
                self.db.commit()
            self.logger.info(f'项目 {project_id}: 成功更新所有投标人的价格分和总分。')
            return True

        except Exception as e:
            self.logger.error(
                f'计算项目 {project_id} 的价格分时发生严重错误: {e}', exc_info=True
            )
            if self.db:
                self.db.rollback()
            return False

    def _calculate_comprehensive_analysis_rules(
        self, project_id: int, analysis_results: List[AnalysisResult]
    ) -> bool:
        """
        计算需要综合分析的规则

        Args:
            project_id: 项目ID
            analysis_results: 分析结果列表

        Returns:
            bool: 是否成功计算综合分析规则
        """
        try:
            self.logger.info(f'开始计算项目 {project_id} 的综合分析规则')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 1. 获取需要综合分析的规则（排除价格规则）
            comprehensive_rules = (
                self.db.query(ScoringRule)
                .filter(
                    ScoringRule.project_id == project_id,
                    ScoringRule.needs_comprehensive_analysis == True,
                    ScoringRule.is_quantitative == True,
                    ScoringRule.is_price_criteria == False,  # 排除价格规则
                )
                .all()
            )

            self.logger.info(
                f'项目 {project_id} 找到 {len(comprehensive_rules)} 个需要综合分析的规则（不包括价格规则）'
            )

            # 2. 为每个规则执行综合分析
            for rule in comprehensive_rules:
                self.logger.info(f'开始处理规则: {rule.Child_Item_Name}')

                # 处理需要综合分析的定量规则
                success = self._process_comprehensive_rule(rule, analysis_results)
                if not success:
                    self.logger.error(f'处理规则 {rule.Child_Item_Name} 失败')
                    return False

            self.logger.info(f'项目 {project_id} 的综合分析规则计算完成')
            return True

        except Exception as e:
            self.logger.error(
                f'计算项目 {project_id} 的综合分析规则时出错: {e}', exc_info=True
            )
            return False

    def _process_comprehensive_rule(
        self, rule: ScoringRule, analysis_results: List[AnalysisResult]
    ) -> bool:
        """
        处理单个需要综合分析的规则

        Args:
            rule: 评分规则
            analysis_results: 分析结果列表

        Returns:
            bool: 是否成功处理规则
        """
        try:
            self.logger.info(f'处理综合分析规则: {rule.Child_Item_Name}')

            # 为每个投标人执行分析
            for result in analysis_results:
                # 获取投标文件内容（从detailed_scores中提取）
                bid_content = ''
                if result.detailed_scores:
                    try:
                        if isinstance(result.detailed_scores, str):
                            detailed_scores = json.loads(result.detailed_scores)
                        else:
                            detailed_scores = result.detailed_scores

                        # 提取评分内容作为投标文件内容
                        content_parts = []
                        self._extract_content_from_scores(
                            detailed_scores, content_parts
                        )
                        bid_content = '\n'.join(content_parts)
                    except Exception as parse_e:
                        self.logger.warning(f'解析详细评分时出错: {parse_e}')
                        bid_content = '无法获取投标文件内容'
                else:
                    bid_content = '无投标文件内容'

                # 构造分析提示
                prompt = f"""
                根据以下评分规则对投标文件进行评分：
                
                评分规则：{rule.description}
                满分：{rule.Child_max_score}
                
                投标文件内容：
                {bid_content[:2000]}  # 限制文本长度
                
                请根据评分规则对投标文件进行评分，只返回一个0到{rule.Child_max_score}之间的数字，不要包含其他文字。
                """

                # 使用AI分析器分析投标文件内容
                ai_response = self.ai_analyzer.analyze_text(prompt)

                # 尝试从AI响应中提取分数
                score = self._extract_score_from_response(
                    ai_response, rule.Child_max_score
                )

                if score is not None:
                    # 更新分析结果
                    # 这里需要根据具体的规则类型来更新相应的字段
                    # 作为示例，我们假设有一个通用的评分字段
                    result.custom_score = score
                    self.logger.info(
                        f"投标人 '{result.bidder_name}' 的规则 '{rule.Child_Item_Name}' 得分: {score}"
                    )
                else:
                    self.logger.warning(
                        f"无法为投标人 '{result.bidder_name}' 计算规则 '{rule.Child_Item_Name}' 的得分，AI响应: {ai_response}"
                    )

            if self.db:
                self.db.commit()
            return True

        except Exception as e:
            self.logger.error(
                f'处理综合分析规则 {rule.Child_Item_Name} 时出错: {e}', exc_info=True
            )
            if self.db:
                self.db.rollback()
            return False

    def _extract_content_from_scores(self, scores, content_parts):
        """
        从评分数据中提取内容

        Args:
            scores: 评分数据
            content_parts: 内容片段列表
        """
        if not isinstance(scores, list):
            return

        for item in scores:
            if isinstance(item, dict):
                # 提取评分项的内容
                if 'criteria_name' in item:
                    content_parts.append(f'评分项: {item["criteria_name"]}')
                if 'score' in item:
                    content_parts.append(f'得分: {item["score"]}')
                if 'details' in item and item['details']:
                    content_parts.append(f'详情: {item["details"]}')

                # 递归处理子项
                if 'children' in item and item['children']:
                    self._extract_content_from_scores(item['children'], content_parts)

    def _extract_score_from_response(
        self, response: str, max_score: float
    ) -> Optional[float]:
        """
        从AI响应中提取分数

        Args:
            response: AI响应文本
            max_score: 最大分数

        Returns:
            Optional[float]: 提取的分数，如果无法提取则返回None
        """
        try:
            # 尝试直接转换为浮点数
            score = float(response.strip())
            if 0 <= score <= max_score:
                return score
            else:
                self.logger.warning(f'提取的分数 {score} 超出有效范围 [0, {max_score}]')
                return None
        except ValueError:
            # 如果直接转换失败，尝试从文本中提取数字
            import re

            numbers = re.findall(r'\d+\.?\d*', response)
            if numbers:
                score = float(numbers[0])
                if 0 <= score <= max_score:
                    return score
            self.logger.warning(f"无法从响应 '{response}' 中提取有效分数")
            return None

    def _fallback_price_calculation(
        self, price_rule: ScoringRule, bidder_prices: Dict[str, float]
    ) -> Dict[str, float]:
        """
        价格分计算的备用方法（使用可靠的编程方法）

        Args:
            price_rule: 价格评分规则
            bidder_prices: 投标人报价字典

        Returns:
            Dict[str, float]: 投标人价格分字典
        """
        try:
            self.logger.info('使用备用方法计算价格分')

            if not bidder_prices:
                return {}

            # 获取最低价作为基准价
            base_price = min(bidder_prices.values())
            self.logger.info(f'基准价格: {base_price}')

            # 计算每个投标人的价格分
            price_scores = {}
            for bidder_name, price in bidder_prices.items():
                # 使用价格得分计算公式
                # 这里使用一个简单的线性公式作为示例
                # 实际项目中应该根据具体的评分规则来计算
                if price == base_price:
                    score = price_rule.Child_max_score  # 最低价得满分
                else:
                    # 简单线性计算，实际应该根据具体规则调整
                    score = max(0, price_rule.Child_max_score * (base_price / price))

                price_scores[bidder_name] = round(score, 2)
                self.logger.info(
                    f"投标人 '{bidder_name}' 报价: {price}, 价格分: {score}"
                )

            return price_scores

        except Exception as e:
            self.logger.error(f'价格分计算失败: {e}', exc_info=True)
            return {}

    def _update_project_status(self, project_id: int):
        """
        更新项目状态为已完成

        Args:
            project_id: 项目ID
        """
        try:
            if not self.db:
                self.logger.error('数据库会话未提供')
                return

            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if project:
                project.status = 'completed'
                project.updated_at = datetime.datetime.now()
                self.db.commit()
                self.logger.info(f'项目 {project_id} 状态已更新为已完成')
            else:
                self.logger.warning(f'未找到项目 {project_id}，无法更新状态')

        except Exception as e:
            self.logger.error(f'更新项目 {project_id} 状态时出错: {e}', exc_info=True)
            if self.db:
                self.db.rollback()
