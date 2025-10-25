#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-22 20:44:33
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-22 20:44:36
# 文件相对于项目的路径   : \AI_ENV2\modules\comprehensive_analysis_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
综合分析管理器模块
处理需要对全部投标文件进行综合计算的特殊定量规则
"""

import logging
import json
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from models.database import ScoringRule, AnalysisResult
from modules.local_ai_analyzer import LocalAIAnalyzer


class ComprehensiveAnalysisManager:
    """综合分析管理器，处理需要对全部投标文件进行综合计算的特殊定量规则"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.ai_analyzer = LocalAIAnalyzer()
        self.logger = logging.getLogger(__name__)

    def get_comprehensive_analysis_rules(self, project_id: int) -> List[ScoringRule]:
        """
        获取项目中需要综合分析的规则

        Args:
            project_id: 项目ID

        Returns:
            List[ScoringRule]: 需要综合分析的规则列表
        """
        if not self.db:
            self.logger.error('数据库会话未提供')
            return []

        try:
            rules = (
                self.db.query(ScoringRule)
                .filter(
                    ScoringRule.project_id == project_id,
                    ScoringRule.needs_comprehensive_analysis == True,
                    ScoringRule.is_quantitative == True,
                )
                .all()
            )
            return rules
        except Exception as e:
            self.logger.error(f'获取综合分析规则时出错: {e}')
            return []

    def extract_preliminary_data(
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

    def perform_comprehensive_analysis(
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
            self.logger.debug(
                f'规则详细信息: ID={rule.id}, 满分={rule.Child_max_score}, 描述={rule.description}'
            )

            # 检查预评价数据是否有效
            if not preliminary_data:
                self.logger.warning(f'规则 "{rule.Child_Item_Name}" 没有预评价数据')
                return {}

            self.logger.info(f'预评价数据数量: {len(preliminary_data)}')
            for i, data in enumerate(preliminary_data):
                self.logger.debug(f'预评价数据[{i}]: {data}')

            # 构造发送给AI的prompt
            prompt = self._create_comprehensive_analysis_prompt(rule, preliminary_data)
            self.logger.debug(f'发送给AI的prompt: {prompt}')

            # 调用AI大模型进行综合分析
            self.logger.info('开始调用AI大模型进行综合分析')
            ai_response = self.ai_analyzer.analyze_text(prompt)
            self.logger.info('AI大模型响应接收成功')
            self.logger.debug(f'AI响应内容: {ai_response}')

            # 检查AI响应是否为空
            if not ai_response or not ai_response.strip():
                self.logger.error(f'规则 "{rule.Child_Item_Name}" AI返回空响应')
                raise Exception('AI返回空响应')

            # 解析AI响应
            final_scores = self._parse_comprehensive_analysis_response(
                ai_response, preliminary_data
            )
            self.logger.info(f'解析后的最终得分: {final_scores}')

            # 再次检查解析结果是否有效
            if not final_scores:
                self.logger.warning(
                    f'规则 "{rule.Child_Item_Name}" AI分析返回异常结果，使用回退排名计算方法'
                )
                return self._fallback_ranking_calculation(rule, preliminary_data)

            self.logger.info(
                f'规则 "{rule.Child_Item_Name}" 综合分析完成，结果: {final_scores}'
            )
            return final_scores
        except Exception as e:
            self.logger.error(f'执行综合分析时出错: {e}', exc_info=True)
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
            all_scores_are_max = True  # 标记是否所有分数都是满分

            for bidder_name, score in data.items():
                if not isinstance(score, (int, float)):
                    self.logger.warning(f'投标人 {bidder_name} 的得分不是数字: {score}')
                    validated_scores[bidder_name] = 0
                    all_scores_are_max = False  # 不是满分
                elif score < 0:
                    validated_scores[bidder_name] = 0
                    all_scores_are_max = False  # 不是满分
                elif score > max_score:
                    validated_scores[bidder_name] = max_score
                    # 如果满分等于最大分数，则标记为满分
                    if max_score == score:
                        pass  # 保持all_scores_are_max为True
                    else:
                        all_scores_are_max = False  # 不是满分
                else:
                    validated_scores[bidder_name] = round(float(score), 2)
                    # 如果有任何一个分数不是满分，则标记为False
                    if score < max_score:
                        all_scores_are_max = False

            # 如果所有投标人都得到了满分，可能是AI计算错误
            if all_scores_are_max and len(validated_scores) > 1:
                self.logger.warning(
                    '所有投标人都得到了满分，可能是AI计算错误，将使用回退排名计算方法'
                )
                # 返回空字典，让调用方使用回退方法
                return {}

            return validated_scores
        except Exception as e:
            self.logger.error(f'解析综合分析响应时出错: {e}')
            # 返回空字典，让调用方使用回退方法
            return {}

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
            self.logger.debug(
                f'规则详细信息: ID={rule.id}, 满分={rule.Child_max_score}, 描述={rule.description}'
            )
            self.logger.debug(f'预评价数据: {preliminary_data}')

            # 检查输入数据是否有效
            if not preliminary_data:
                self.logger.warning(
                    f'规则 "{rule.Child_Item_Name}" 没有预评价数据，无法进行回退计算'
                )
                return {}

            # 过滤掉无效的预评价数据
            valid_data = [
                data
                for data in preliminary_data
                if data.get('preliminary_score') is not None
            ]
            if not valid_data:
                self.logger.warning(
                    f'规则 "{rule.Child_Item_Name}" 没有有效的预评价数据，无法进行回退计算'
                )
                return {}

            self.logger.info(f'有效预评价数据数量: {len(valid_data)}')

            # 按预评分排序
            sorted_data = sorted(
                valid_data, key=lambda x: x['preliminary_score'], reverse=True
            )

            self.logger.info(f'排序后的数据: {sorted_data}')

            max_score = rule.Child_max_score or 10
            self.logger.info(f'规则满分: {max_score}')
            scores = {}

            # 简单的线性排名得分计算
            total_bidders = len(sorted_data)
            self.logger.info(f'投标人总数: {total_bidders}')

            if total_bidders == 0:
                self.logger.warning('没有投标人数据，返回空结果')
                return {}
            elif total_bidders == 1:
                # 只有一个投标人，直接给满分
                bidder_name = sorted_data[0]['bidder_name']
                scores[bidder_name] = max_score
                self.logger.info(
                    f'只有一个投标人 {bidder_name}，直接给满分 {max_score}'
                )
            else:
                # 多个投标人，按排名分配得分
                for i, data in enumerate(sorted_data):
                    bidder_name = data['bidder_name']
                    preliminary_score = data['preliminary_score']
                    # 线性分配得分：第一名满分，最后一名0分
                    # 注意：这里是 (total_bidders - i - 1) 是为了第一名得满分
                    score = (
                        max_score * (total_bidders - i - 1) / (total_bidders - 1)
                        if total_bidders > 1
                        else max_score
                    )
                    scores[bidder_name] = round(score, 2)
                    self.logger.debug(
                        f'投标人 {bidder_name} 预评分 {preliminary_score}, 排名 {i + 1}, 最终得分 {scores[bidder_name]}'
                    )

            self.logger.info(f'回退计算结果: {scores}')
            return scores
        except Exception as e:
            self.logger.error(f'回退排名计算失败: {e}', exc_info=True)
            # 返回预评分作为最终得分（作为最后的备选方案）
            try:
                result = {}
                for data in preliminary_data:
                    bidder_name = data.get('bidder_name')
                    preliminary_score = data.get('preliminary_score', 0)
                    if bidder_name is not None:
                        # 确保分数在合理范围内
                        if isinstance(preliminary_score, (int, float)):
                            if preliminary_score < 0:
                                result[bidder_name] = 0
                            elif preliminary_score > (rule.Child_max_score or 10):
                                result[bidder_name] = rule.Child_max_score or 10
                            else:
                                result[bidder_name] = round(float(preliminary_score), 2)
                        else:
                            result[bidder_name] = 0
                self.logger.info(f'使用预评分作为最终得分: {result}')
                return result
            except Exception as fallback_e:
                self.logger.error(
                    f'使用预评分作为最终得分也失败了: {fallback_e}', exc_info=True
                )
                return {}

    def update_analysis_results(
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
