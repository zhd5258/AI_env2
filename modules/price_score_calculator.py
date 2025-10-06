"""
价格分计算器模块
负责计算投标人的价格得分
"""

import json
import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from models.database import AnalysisResult, ScoringRule, TenderProject
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.price_calculator_helpers import PriceScoreCalculatorHelpers


class PriceScoreCalculator(PriceScoreCalculatorHelpers):
    """价格分计算器类"""

    def __init__(self, db_session: Optional[Session] = None):
        super().__init__()
        self.db = db_session
        self.ai_analyzer = LocalAIAnalyzer()
        self.logger = logging.getLogger(__name__)

    def calculate_project_price_scores(self, project_id: int) -> bool:
        """
        计算项目中所有投标人的价格分（统一计算，不针对单个投标人）
        使用AI大模型进行价格分计算，不使用默认计算方法

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功计算价格分
        """
        try:
            self.logger.info(f'开始计算项目 {project_id} 的价格分')

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

            # 2. 获取评分规则
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
                return False

            # 构造包含公式和描述的字典
            formula_info = {
                'formula': price_rule.price_formula,
                'description': price_rule.description,
            }

            self.logger.info(
                f'找到价格评分规则: 满分 {price_rule.Child_max_score}, 公式: {price_rule.price_formula}, 描述: {price_rule.description}'
            )

            # 3. 获取所有分析结果
            analysis_results = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            if not analysis_results:
                self.logger.warning(f'项目 {project_id} 没有找到分析结果')
                return False

            # 4. 提取投标人报价
            bidder_prices = self._extract_bidder_prices(analysis_results)
            self.logger.info(
                f'提取到 {len(bidder_prices)} 个投标人的报价: {bidder_prices}'
            )

            # 5. 构造发送给AI大模型的完整prompt
            # 格式: "投标人1：投标总价1,投标人2：投标总价2,投标人3：投标总价3,......."
            bidder_info_str = ','.join(
                [f'{name}：{price}' for name, price in bidder_prices.items()]
            )

            # 获取价格分的最高分
            price_max_score = price_rule.Child_max_score or 40  # 默认40分

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

            self.logger.info('=' * 50)
            self.logger.info('发送给AI大模型的价格分计算请求:')
            self.logger.info(f'投标人报价信息: {bidder_info_str}')
            self.logger.info(f'价格评价标准: {price_rule.description}')
            self.logger.info(f'价格分满分: {price_max_score}分')
            self.logger.info('完整prompt:')
            self.logger.info(prompt)
            self.logger.info('=' * 50)

            # 6. 调用AI大模型计算价格分
            try:
                ai_response = self.ai_analyzer.analyze_text(prompt)

                # 记录AI大模型的返回值
                self.logger.info('=' * 50)
                self.logger.info('AI大模型返回的完整响应:')
                self.logger.info(ai_response)
                self.logger.info('=' * 50)

                # 解析AI响应
                price_scores = self._parse_price_scores_from_ai_response(ai_response)

                # 验证和修正价格分，确保不超过最高分
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

            # 7. 如果AI计算失败，不使用默认计算方法，直接返回False
            if not price_scores:
                self.logger.error('AI价格分计算失败，按照规范不使用默认计算方法')
                return False

            # 8. 更新每个投标人的价格分和总分
            updated_count = 0
            self.logger.info('=' * 50)
            self.logger.info('开始更新各投标人的价格分和总分:')

            # 创建一个映射，用于跟踪已处理的投标人
            processed_bidders = {}

            for result in analysis_results:
                bidder_name = result.bidder_name

                # 检查是否已经处理过该投标人
                if bidder_name in processed_bidders:
                    self.logger.info(f'投标人 [{bidder_name}] 已经处理过，跳过')
                    continue

                # 标记该投标人已处理
                processed_bidders[bidder_name] = True

                # 获取该投标人的价格分（严格按当前项目进行匹配）
                new_price_score = price_scores.get(str(bidder_name), 0)
                self.logger.info(
                    f'投标人 [{str(bidder_name)}] 报价 {bidder_prices.get(str(bidder_name), "N/A")}，价格分 {new_price_score}'
                )

                try:
                    # 确保只更新当前项目的记录
                    if int(getattr(result, 'project_id', 0)) != int(project_id):
                        self.logger.warning(
                            f'投标人 [{bidder_name}] 的记录不属于当前项目 {project_id}，跳过更新'
                        )
                        continue

                    # 更新价格分
                    old_price_score = result.price_score or 0  # 处理 None 情况
                    setattr(result, 'price_score', new_price_score)
                    self.logger.info(
                        f'  更新价格分: {old_price_score} -> {new_price_score}'
                    )

                    # 更新总分
                    old_total_score = result.total_score or 0

                    # 从详细评分中获取除价格分外的其他分数总和
                    other_scores_total = 0
                    if result.detailed_scores is not None:
                        try:
                            # 解析JSON字符串格式的detailed_scores
                            if isinstance(result.detailed_scores, str):
                                detailed_scores = json.loads(result.detailed_scores)
                            elif isinstance(result.detailed_scores, list):
                                detailed_scores = result.detailed_scores
                            else:
                                detailed_scores = []

                            other_scores_total = self._calculate_other_scores_total(
                                detailed_scores
                            )
                            self.logger.info(
                                f'投标人 {bidder_name} 的子项得分总和: {other_scores_total}'
                            )
                        except Exception as e:
                            self.logger.error(
                                f'解析投标人 {bidder_name} 的详细评分时出错: {e}'
                            )

                    # 新总分 = 其他分数总和 + 新价格分
                    new_total_score = other_scores_total + new_price_score
                    setattr(result, 'total_score', round(new_total_score, 2))
                    self.logger.info(
                        f'  更新总分: {old_total_score} -> {new_total_score}'
                    )

                    updated_count += 1

                except Exception as e:
                    self.logger.error(f'更新投标人 {bidder_name} 的价格分时出错: {e}')
                    continue

            self.db.commit()
            self.logger.info(f'成功更新了 {updated_count} 个投标方的价格分和总分')
            self.logger.info('=' * 50)
            return True

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}')
            return False

    def _parse_price_scores_from_ai_response(
        self, ai_response: str
    ) -> Dict[str, float]:
        """
        解析AI大模型返回的价格分计算结果

        Args:
            ai_response: AI大模型的响应

        Returns:
            Dict[str, float]: 投标人名称到价格分的映射
        """
        try:
            # 清理响应文本
            clean_response = ai_response.strip()

            # 如果响应包含JSON代码块标记，移除它们
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.startswith('```'):
                clean_response = clean_response[3:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            # 尝试多种解析方式
            price_scores = {}

            # 方式1：尝试从响应中提取JSON部分
            try:
                # 使用正则表达式提取JSON部分，忽略垃圾数据
                import re

                # 更强大的JSON提取正则，支持嵌套和中文字符
                json_match = re.search(r'\{[\s\S]*?\}', clean_response)
                if json_match:
                    json_str = json_match.group()
                    # 进一步清理，移除可能的"分"字并转换为数值
                    json_str = re.sub(
                        r'<\|endoftext\|>.*$', '', json_str, flags=re.DOTALL
                    )
                    json_str = json_str.strip()
                    self.logger.info(f'提取到JSON字符串: {json_str}')
                    json_data = json.loads(json_str)
                    if isinstance(json_data, dict):
                        for name, score in json_data.items():
                            if isinstance(score, (int, float)):
                                price_scores[str(name)] = float(score)
                        self.logger.info(f'JSON解析成功: {price_scores}')
                        return price_scores
                else:
                    # 如果没有找到JSON格式，尝试直接解析整个响应
                    json_data = json.loads(clean_response)
                    if isinstance(json_data, dict):
                        for name, score in json_data.items():
                            if isinstance(score, (int, float)):
                                price_scores[str(name)] = float(score)
                        self.logger.info(f'直接JSON解析成功: {price_scores}')
                        return price_scores
            except json.JSONDecodeError:
                self.logger.warning('JSON解析失败，尝试文本解析')

            # 方式2：文本解析
            # 响应格式应该是："投标人1：价格分1,投标人2：价格分2,投标人3：价格分3,......."
            bidder_results = clean_response.split(',')
            for result in bidder_results:
                # 分割投标人名称和价格分
                if '：' in result:
                    parts = result.split('：')
                    if len(parts) == 2:
                        bidder_name = parts[0].strip()
                        score_str = parts[1].strip()

                        # 移除可能的"分"字并转换为数值
                        score_str = score_str.replace('分', '').strip()
                        try:
                            score = float(score_str)
                            price_scores[bidder_name] = score
                        except ValueError:
                            self.logger.warning(
                                f'无法解析投标人 {bidder_name} 的价格分: {score_str}'
                            )
                            continue
                elif ':' in result:
                    parts = result.split(':')
                    if len(parts) == 2:
                        bidder_name = parts[0].strip()
                        score_str = parts[1].strip()

                        # 移除可能的"分"字并转换为数值
                        score_str = score_str.replace('分', '').strip()
                        try:
                            score = float(score_str)
                            price_scores[bidder_name] = score
                        except ValueError:
                            self.logger.warning(
                                f'无法解析投标人 {bidder_name} 的价格分: {score_str}'
                            )
                            continue

            self.logger.info(f'文本解析成功: {price_scores}')
            return price_scores
        except Exception as e:
            self.logger.error(f'解析AI响应时出错: {e}')
            return {}

    def _calculate_other_scores_total(self, detailed_scores: list) -> float:
        """
        计算除价格分外的其他分数总和

        Args:
            detailed_scores: 详细评分列表

        Returns:
            float: 其他分数总和
        """
        total = 0
        try:
            for item in detailed_scores:
                # 跳过价格分项 - 修正字段名检查
                if (
                    item.get('is_price_criteria')
                    or '价格' in item.get('Child_Item_Name', '')
                    or '价格' in item.get('criteria_name', '')
                ):
                    continue

                # 累加分数
                score = item.get('score', 0)
                if isinstance(score, (int, float)):
                    total += score

                # 递归处理子项
                if 'children' in item and isinstance(item['children'], list):
                    total += self._calculate_other_scores_total(item['children'])
        except Exception as e:
            self.logger.error(f'计算其他分数总和时出错: {e}')

        return total
