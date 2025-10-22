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


class UnifiedComprehensiveCalculator:
    """统一综合计算器，整合价格分计算和需要综合计算的定量规则处理"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.ai_analyzer = LocalAIAnalyzer()
        self.logger = logging.getLogger(__name__)

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

            # 3. 执行价格分计算
            price_calculation_success = self._calculate_price_scores(
                project_id, analysis_results
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
            self.logger.error(f'执行统一综合计算时出错: {e}')
            return False

    def _calculate_price_scores(
        self, project_id: int, analysis_results: List[AnalysisResult]
    ) -> bool:
        """
        计算价格分（预评价阶段只提取投标总价并保存）

        Args:
            project_id: 项目ID
            analysis_results: 分析结果列表

        Returns:
            bool: 是否成功计算价格分
        """
        try:
            self.logger.info(f'开始计算项目 {project_id} 的价格分')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 1. 获取评分规则
            scoring_rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .all()
            )
            price_rule = next(
                (
                    rule
                    for rule in scoring_rules
                    if getattr(rule, 'is_price_criteria', False)
                ),
                None,
            )

            if not price_rule:
                self.logger.warning(f'项目 {project_id} 没有找到价格评分规则')
                return True  # 没有价格规则也算成功

            # 2. 提取投标人报价（预评价阶段）
            bidder_prices = self._extract_bidder_prices(analysis_results)
            self.logger.info(
                f'提取到 {len(bidder_prices)} 个投标人的报价: {bidder_prices}'
            )

            # 3. 构造发送给AI大模型的完整prompt
            valid_bidder_prices = {
                name: price
                for name, price in bidder_prices.items()
                if name and str(name).strip() and name != 'None' and price is not None
            }

            if not valid_bidder_prices:
                self.logger.error('没有有效的投标人报价用于价格分计算')
                return False

            bidder_info_str = ','.join(
                [f'{name}：{price}' for name, price in valid_bidder_prices.items()]
            )

            # 获取价格分的最高分
            price_max_score = price_rule.Child_max_score or 40

            # 构造发送给AI大模型的prompt
            prompt = f"""你是一个专业的评标专家，请根据以下信息计算各投标人的价格分：

【投标人报价信息】
{bidder_info_str}

【价格评价标准】
{price_rule.description}

【价格分满分】
{price_max_score}分

【计算要求】
1. 根据价格评价标准计算每个投标人的价格分
2. 价格分必须是0-{price_max_score}之间的数字（满分为{price_max_score}分）
3. 最低价的投标人应该得到最高分（{price_max_score}分）
4. 严格按照价格评价标准中的计算公式进行计算

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{"投标人1": 价格分1, "投标人2": 价格分2, "投标人3": 价格分3}}

示例（假设满分为40分）：
{{"公司A": 38.2, "公司B": 40.0, "公司C": 35.3}}"""

            self.logger.info(
                f'开始计算价格分 - 投标人数量: {len(valid_bidder_prices)}, 满分: {price_max_score}分'
            )

            # 4. 调用AI大模型计算价格分
            try:
                ai_response = self.ai_analyzer.analyze_text(prompt)
                self.logger.info('AI大模型响应接收成功')

                # 解析AI响应
                price_scores = self._parse_price_scores_from_ai_response(ai_response)

                # 验证和修正价格分
                validated_scores = {}
                for bidder_name, score in price_scores.items():
                    if score > price_max_score:
                        self.logger.warning(
                            f'投标人 {bidder_name} 的AI计算价格分 {score} 超过最高分 {price_max_score}，自动修正为最高分'
                        )
                        validated_scores[bidder_name] = price_max_score
                    elif score < 0:
                        self.logger.warning(
                            f'投标人 {bidder_name} 的AI计算价格分 {score} 小于0，自动修正为0'
                        )
                        validated_scores[bidder_name] = 0
                    else:
                        validated_scores[bidder_name] = round(score, 2)

                price_scores = validated_scores
                self.logger.info(f'验证和修正后的价格分计算结果: {price_scores}')

            except Exception as e:
                self.logger.error(f'调用AI大模型计算价格分时出错: {e}')
                return False

            # 5. 更新每个投标人的价格分和总分
            updated_count = 0
            processed_bidders = {}

            for result in analysis_results:
                bidder_name = (
                    result.bidder_name
                    if result.bidder_name
                    else f'未知投标人_{result.id}'
                )
                if (
                    not bidder_name
                    or not str(bidder_name).strip()
                    or bidder_name == 'None'
                ):
                    bidder_name = f'未知投标人_{result.id}'

                if bidder_name in processed_bidders:
                    continue

                processed_bidders[bidder_name] = True

                new_price_score = price_scores.get(str(bidder_name), 0)
                self.logger.info(
                    f'投标人 [{str(bidder_name)}] 报价 {bidder_prices.get(str(bidder_name), "N/A")}，价格分 {new_price_score}'
                )

                try:
                    if int(getattr(result, 'project_id', 0)) != int(project_id):
                        continue

                    # 更新价格分
                    old_price_score = result.price_score or 0
                    setattr(result, 'price_score', new_price_score)
                    self.logger.info(
                        f'  更新价格分: {old_price_score} -> {new_price_score}'
                    )

                    # 更新总分
                    detailed_scores_list = []
                    if isinstance(result.detailed_scores, str):
                        try:
                            detailed_scores_list = json.loads(result.detailed_scores)
                        except json.JSONDecodeError:
                            self.logger.error(
                                f'解析投标人 {bidder_name} 的 detailed_scores 失败'
                            )
                    elif isinstance(result.detailed_scores, list):
                        detailed_scores_list = result.detailed_scores

                    other_scores_total = self._calculate_other_scores_total(
                        detailed_scores_list
                    )

                    new_total_score = other_scores_total + new_price_score
                    old_total_score = result.total_score or 0
                    setattr(result, 'total_score', round(new_total_score, 2))
                    self.logger.info(
                        f'  更新总分: {old_total_score} -> {new_total_score} (其他项总分: {other_scores_total})'
                    )

                    updated_count += 1

                except Exception as e:
                    self.logger.error(f'更新投标人 {bidder_name} 的价格分时出错: {e}')
                    continue

            self.db.commit()
            self.logger.info(f'成功更新了 {updated_count} 个投标方的价格分和总分')
            return True

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}')
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

            # 1. 获取需要综合分析的规则
            comprehensive_rules = (
                self.db.query(ScoringRule)
                .filter(
                    ScoringRule.project_id == project_id,
                    ScoringRule.needs_comprehensive_analysis == True,
                    ScoringRule.is_quantitative == True,
                )
                .all()
            )

            if not comprehensive_rules:
                self.logger.info(f'项目 {project_id} 没有需要综合分析的规则')
                return True

            self.logger.info(f'找到 {len(comprehensive_rules)} 个需要综合分析的规则')

            # 2. 对每个规则进行综合分析
            for rule in comprehensive_rules:
                self.logger.info(f'处理综合分析规则: {rule.Child_Item_Name}')

                # 提取预评价数据
                preliminary_data = []
                for result in analysis_results:
                    data = self._extract_preliminary_data(rule, result)
                    preliminary_data.append(data)
                    self.logger.info(
                        f'投标人 {data["bidder_name"]}: 预评分 {data["preliminary_score"]}/{data["max_score"]}'
                    )

                # 执行综合分析
                final_scores = self._perform_comprehensive_analysis(
                    rule, preliminary_data
                )

                # 更新分析结果
                success = self._update_analysis_results(project_id, rule, final_scores)
                if not success:
                    self.logger.error(f'更新综合分析结果失败: {rule.Child_Item_Name}')
                    return False

                self.logger.info(f'综合分析规则处理完成: {rule.Child_Item_Name}')

            return True

        except Exception as e:
            self.logger.error(f'计算综合分析规则时出错: {e}')
            if self.db:
                self.db.rollback()
            return False

    def _extract_bidder_prices(
        self, analysis_results: List[AnalysisResult]
    ) -> Dict[str, float]:
        """
        从分析结果中提取投标人报价

        Args:
            analysis_results: 分析结果列表

        Returns:
            Dict[str, float]: 投标人名称到报价的映射
        """
        bidder_prices = {}
        for result in analysis_results:
            bidder_name = result.bidder_name
            extracted_price = result.extracted_price
            if bidder_name and extracted_price is not None:
                bidder_prices[bidder_name] = float(extracted_price)
        return bidder_prices

    def _parse_price_scores_from_ai_response(self, ai_response):
        """
        从AI响应中解析价格分

        Args:
            ai_response (str): AI大模型的响应

        Returns:
            dict: 投标人名称到价格分的映射
        """
        import re
        import json

        price_scores = {}
        try:
            # 尝试清理响应，移除可能的代码块标记
            cleaned_response = ai_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith('```'):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # 移除控制字符
            cleaned_response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned_response)

            # 使用正则表达式查找被大括号包围的JSON块
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = cleaned_response

            # 尝试修复JSON格式问题
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON
            data = json.loads(json_str)

            if isinstance(data, dict):
                for name, score in data.items():
                    if isinstance(score, (int, float)):
                        price_scores[str(name)] = float(score)
                    elif isinstance(score, dict) and 'score' in score:
                        score_value = score.get('score', 0)
                        if isinstance(score_value, (int, float)):
                            price_scores[str(name)] = float(score_value)
                    else:
                        self.logger.warning(
                            f'跳过无效的分数值：投标人 "{name}" 的分数 "{score}" 不是数字。'
                        )

                self.logger.info(f'成功从AI响应中解析出价格分: {price_scores}')
                return price_scores
            else:
                return {}
        except Exception as e:
            self.logger.error(
                f'解析AI响应时发生未知错误: {e}。完整的原始AI响应: {ai_response}'
            )
            return {}

    def _calculate_other_scores_total(self, detailed_scores_list):
        """
        计算除价格分外的其他所有项得分总和

        Args:
            detailed_scores_list: 详细评分列表

        Returns:
            float: 其他项得分总和
        """
        other_scores_total = 0
        if isinstance(detailed_scores_list, list):
            for score_item in detailed_scores_list:
                if isinstance(score_item, dict):
                    # 跳过价格分项
                    if score_item.get('is_price_criteria', False):
                        continue
                    score = score_item.get('score', 0)
                    if isinstance(score, (int, float)):
                        other_scores_total += score
        return other_scores_total

    def _extract_preliminary_data(
        self, rule: ScoringRule, analysis_result: AnalysisResult
    ) -> Dict[str, Any]:
        """
        从单个投标文件的分析结果中提取该规则的预评价数据

        Args:
            rule: 评分规则
            analysis_result: 分析结果

        Returns:
            Dict[str, Any]: 预评价数据
        """
        try:
            # 从详细评分中找到对应规则的预评价数据
            detailed_scores = getattr(analysis_result, 'detailed_scores', [])
            if not isinstance(detailed_scores, list):
                detailed_scores = []

            for score_item in detailed_scores:
                if (
                    isinstance(score_item, dict)
                    and score_item.get('Child_Item_Name') == rule.Child_Item_Name
                ):
                    return {
                        'bidder_name': analysis_result.bidder_name,
                        'preliminary_score': score_item.get('score', 0),
                        'preliminary_reason': score_item.get('reason', ''),
                        'max_score': rule.Child_max_score or 0,
                    }

            # 如果没有找到，返回默认值
            return {
                'bidder_name': analysis_result.bidder_name,
                'preliminary_score': 0,
                'preliminary_reason': '未分析',
                'max_score': rule.Child_max_score or 0,
            }
        except Exception as e:
            self.logger.error(f'提取预评价数据时出错: {e}')
            return {
                'bidder_name': analysis_result.bidder_name,
                'preliminary_score': 0,
                'preliminary_reason': f'提取失败: {str(e)}',
                'max_score': rule.Child_max_score or 0,
            }

    def _perform_comprehensive_analysis(
        self, rule: ScoringRule, preliminary_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        对需要综合分析的规则执行综合分析，重新计算得分

        Args:
            rule: 评分规则
            preliminary_data: 所有投标人的预评价数据

        Returns:
            Dict[str, float]: 每个投标人的最终得分
        """
        try:
            self.logger.info(f'开始对规则 "{rule.Child_Item_Name}" 进行综合分析')

            # 构造发送给AI的prompt
            prompt = self._create_comprehensive_analysis_prompt(rule, preliminary_data)

            # 调用AI大模型进行综合分析
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            final_scores = self._parse_comprehensive_analysis_response(
                ai_response, preliminary_data
            )

            self.logger.info(
                f'规则 "{rule.Child_Item_Name}" 综合分析完成，结果: {final_scores}'
            )
            return final_scores
        except Exception as e:
            self.logger.error(f'执行综合分析时出错: {e}')
            # 回退到简单的排名计算
            return self._fallback_ranking_calculation(rule, preliminary_data)

    def _create_comprehensive_analysis_prompt(
        self, rule: ScoringRule, preliminary_data: List[Dict[str, Any]]
    ) -> str:
        """
        创建综合分析的AI prompt

        Args:
            rule: 评分规则
            preliminary_data: 预评价数据

        Returns:
            str: AI prompt
        """
        # 构造投标人预评价信息
        bidder_info = []
        for data in preliminary_data:
            bidder_info.append(
                f'{data["bidder_name"]}: 预评分 {data["preliminary_score"]}/{data["max_score"]}分, '
                f'评分理由: {data["preliminary_reason"]}'
            )

        bidder_info_str = '\n'.join(bidder_info)

        prompt = f"""你是一个专业的评标专家，请根据以下信息对投标人的{rule.Child_Item_Name}进行综合评分：

【评分规则】
规则名称: {rule.Child_Item_Name}
规则描述: {rule.description}
满分: {rule.Child_max_score}分

【各投标人预评价结果】
{bidder_info_str}

【评分要求】
1. 根据评分规则和各投标人的预评价结果，对所有投标人进行综合评分
2. 评分应考虑相对排名、相对优势等因素
3. 最终得分必须在0-{rule.Child_max_score}分之间
4. 评分应体现投标人之间的相对差异

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{"投标人1": 最终得分1, "投标人2": 最终得分2, "投标人3": 最终得分3}}

示例（假设满分为10分）：
{{"公司A": 8.5, "公司B": 9.2, "公司C": 7.8}}"""

        return prompt

    def _parse_comprehensive_analysis_response(
        self, response: str, preliminary_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        解析综合分析的AI响应

        Args:
            response: AI响应
            preliminary_data: 预评价数据

        Returns:
            Dict[str, float]: 解析后的得分
        """
        try:
            import json
            import re

            # 尝试直接解析JSON
            response = response.strip()
            if response.startswith('```json'):
                response = response[7:]
            if response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]

            # 移除控制字符
            response = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)

            data = json.loads(response)

            # 验证数据格式
            if not isinstance(data, dict):
                raise ValueError('响应不是字典格式')

            # 验证投标人名称是否匹配
            bidder_names = {data['bidder_name'] for data in preliminary_data}
            response_names = set(data.keys())

            if bidder_names != response_names:
                self.logger.warning(
                    f'投标人名称不匹配，预评价: {bidder_names}, 响应: {response_names}'
                )

            # 验证得分范围
            max_score = (
                max([data['max_score'] for data in preliminary_data])
                if preliminary_data
                else 10
            )
            validated_scores = {}
            for bidder_name, score in data.items():
                if not isinstance(score, (int, float)):
                    self.logger.warning(f'投标人 {bidder_name} 的得分不是数字: {score}')
                    validated_scores[bidder_name] = 0
                elif score < 0:
                    validated_scores[bidder_name] = 0
                elif score > max_score:
                    validated_scores[bidder_name] = max_score
                else:
                    validated_scores[bidder_name] = round(float(score), 2)

            return validated_scores
        except Exception as e:
            self.logger.error(f'解析综合分析响应时出错: {e}')
            # 返回默认值
            return {
                data['bidder_name']: data['preliminary_score']
                for data in preliminary_data
            }

    def _fallback_ranking_calculation(
        self, rule: ScoringRule, preliminary_data: List[Dict[str, Any]]
    ) -> Dict[str, float]:
        """
        回退的排名计算方法

        Args:
            rule: 评分规则
            preliminary_data: 预评价数据

        Returns:
            Dict[str, float]: 基于排名的得分
        """
        try:
            self.logger.info(f'使用回退排名计算方法处理规则 "{rule.Child_Item_Name}"')

            # 按预评分排序
            sorted_data = sorted(
                preliminary_data, key=lambda x: x['preliminary_score'], reverse=True
            )

            max_score = rule.Child_max_score or 10
            scores = {}

            # 简单的线性排名得分计算
            total_bidders = len(sorted_data)
            for i, data in enumerate(sorted_data):
                # 线性分配得分：第一名满分，最后一名0分
                score = (
                    max_score * (total_bidders - i - 1) / (total_bidders - 1)
                    if total_bidders > 1
                    else max_score
                )
                scores[data['bidder_name']] = round(score, 2)

            return scores
        except Exception as e:
            self.logger.error(f'回退排名计算失败: {e}')
            # 返回预评分作为最终得分
            return {
                data['bidder_name']: data['preliminary_score']
                for data in preliminary_data
            }

    def _update_analysis_results(
        self, project_id: int, rule: ScoringRule, final_scores: Dict[str, float]
    ) -> bool:
        """
        更新分析结果中的综合评分

        Args:
            project_id: 项目ID
            rule: 评分规则
            final_scores: 最终得分

        Returns:
            bool: 是否更新成功
        """
        if not self.db:
            self.logger.error('数据库会话未提供')
            return False

        try:
            # 获取项目的所有分析结果
            analysis_results = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            updated_count = 0
            for result in analysis_results:
                bidder_name = result.bidder_name
                if bidder_name in final_scores:
                    # 更新详细评分
                    detailed_scores = getattr(result, 'detailed_scores', [])
                    if not isinstance(detailed_scores, list):
                        detailed_scores = []

                    # 查找并更新对应规则的评分
                    for score_item in detailed_scores:
                        if (
                            isinstance(score_item, dict)
                            and score_item.get('Child_Item_Name')
                            == rule.Child_Item_Name
                        ):
                            score_item['score'] = final_scores[bidder_name]
                            score_item['reason'] = (
                                f'综合分析后得分，原预评分: {score_item.get("score", 0)}'
                            )
                            updated_count += 1
                            break

                    # 更新定量规则分析结果
                    quantitative_results = getattr(
                        result, 'quantitative_analysis_results', {}
                    )
                    if rule.Child_Item_Name in quantitative_results:
                        quantitative_results[rule.Child_Item_Name]['score'] = (
                            final_scores[bidder_name]
                        )
                        quantitative_results[rule.Child_Item_Name]['reason'] = (
                            f'综合分析后得分，原预评分: {quantitative_results[rule.Child_Item_Name].get("score", 0)}'
                        )

                    # 更新总分
                    self._update_total_score(
                        result, rule.Child_Item_Name, final_scores[bidder_name]
                    )

            self.db.commit()
            self.logger.info(f'成功更新 {updated_count} 个分析结果的综合评分')
            return True
        except Exception as e:
            self.logger.error(f'更新分析结果时出错: {e}')
            if self.db:
                self.db.rollback()
            return False

    def _update_total_score(
        self, analysis_result: AnalysisResult, rule_name: str, new_score: float
    ):
        """
        更新分析结果的总分

        Args:
            analysis_result: 分析结果
            rule_name: 规则名称
            new_score: 新得分
        """
        try:
            # 从详细评分中找到旧得分
            old_score = 0
            detailed_scores = getattr(analysis_result, 'detailed_scores', [])
            if isinstance(detailed_scores, list):
                for score_item in detailed_scores:
                    if (
                        isinstance(score_item, dict)
                        and score_item.get('Child_Item_Name') == rule_name
                    ):
                        old_score = score_item.get('score', 0)
                        break

            # 更新总分
            current_total = getattr(analysis_result, 'total_score', 0) or 0
            new_total = current_total - old_score + new_score
            setattr(analysis_result, 'total_score', new_total)

            self.logger.debug(
                f'更新投标人 {analysis_result.bidder_name} 的总分: {current_total} -> {new_total}'
            )
        except Exception as e:
            self.logger.error(f'更新总分时出错: {e}')

    def _update_project_status(self, project_id: int):
        """
        更新项目状态

        Args:
            project_id: 项目ID
        """
        try:
            if not self.db:
                self.logger.error('数据库会话未提供')
                return

            # 使用统一的项目状态管理器
            from modules.project_status_manager import ProjectStatusManager

            status_manager = ProjectStatusManager(db_session=self.db)
            status_manager.update_project_status(project_id, 'completed')
        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}')
            if self.db:
                self.db.rollback()
