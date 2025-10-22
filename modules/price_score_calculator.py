"""
价格分计算器模块
负责计算投标人的价格得分
"""

import json
import logging
from typing import Dict, Any, Optional, List
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
            # 过滤掉无效的投标人名称
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
            price_max_score = price_rule.Child_max_score or 40  # 默认40分

            # 构造发送给AI大模型的prompt
            # 恢复投标总价信息，因为价格分计算需要这些信息
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

            # 简化日志记录，避免重复输出
            self.logger.info(
                f'开始计算价格分 - 投标人数量: {len(valid_bidder_prices)}, 满分: {price_max_score}分'
            )
            self.logger.debug(f'投标人报价信息: {bidder_info_str}')
            self.logger.debug(f'价格评价标准: {price_rule.description}')
            self.logger.debug(f'完整prompt: {prompt}')

            # 6. 调用AI大模型计算价格分
            try:
                ai_response = self.ai_analyzer.analyze_text(prompt)

                # 简化AI响应日志记录
                self.logger.info('AI大模型响应接收成功')
                self.logger.debug(f'AI响应内容: {ai_response}')

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
                # 修复：即使AI计算失败，也要尝试使用默认计算方法
                self.logger.info('AI价格分计算失败，尝试使用默认计算方法')
                price_scores = self._calculate_price_scores_default(
                    valid_bidder_prices, price_rule
                )
                if not price_scores:
                    return False

            # 7. 如果AI计算失败，使用默认计算方法
            if not price_scores:
                self.logger.warning('AI价格分计算失败，使用默认计算方法')
                price_scores = self._calculate_price_scores_default(
                    valid_bidder_prices, price_rule
                )
                if not price_scores:
                    self.logger.error('默认价格分计算也失败')
                    return False

            # 8. 更新每个投标人的价格分和总分
            updated_count = 0
            self.logger.info(f'开始更新 {len(price_scores)} 个投标人的价格分和总分')

            # 创建一个映射，用于跟踪已处理的投标人
            processed_bidders = {}

            for result in analysis_results:
                # 使用投标人名称，如果为空则使用"未知投标人_序号"作为备用
                bidder_name = (
                    result.bidder_name
                    if result.bidder_name
                    else f'未知投标人_{result.id}'
                )
                # 确保投标人名称不是None或空字符串
                if (
                    not bidder_name
                    or not str(bidder_name).strip()
                    or bidder_name == 'None'
                ):
                    bidder_name = f'未知投标人_{result.id}'

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
                    # 重新计算总分，而不是在旧总分上修改
                    # 1. 计算其他所有项得分之和
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

                    # 2. 新总分 = 其他项得分 + 新价格分
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
            self.logger.info('=' * 50)
            return True

        except Exception as e:
            self.logger.error(f'计算项目 {project_id} 的价格分时出错: {e}')
            return False

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
            # 使用我们改进的JSON修复函数
            result = self._fix_and_parse_json_response(ai_response)

            if isinstance(result, dict):
                # 验证数据格式并转换为所需类型
                for name, score in result.items():
                    if isinstance(score, (int, float)):
                        price_scores[str(name)] = float(score)
                    elif isinstance(score, dict) and 'score' in score:
                        # 如果分数在嵌套字典中
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
                # 如果修复函数返回的不是字典，返回空字典
                return {}
        except Exception as e:
            self.logger.error(
                f'解析AI响应时发生未知错误: {e}。完整的原始AI响应: {ai_response}'
            )
            return {}

    def _fix_and_parse_json_response(self, response):
        """
        修复并解析AI返回的JSON响应
        """
        try:
            import re
            import json

            # 首先尝试清理响应，移除可能的代码块标记
            cleaned_response = response.strip()
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
            # re.DOTALL 使得 '.' 可以匹配包括换行在内的任意字符
            json_match = re.search(r'\{.*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
            else:
                # 如果没有找到JSON块，直接使用清理后的响应
                json_str = cleaned_response

            # 尝试修复JSON格式问题
            # 1. 确保字符串以闭合的大括号结尾
            if not json_str.rstrip().endswith('}'):
                # 查找最后一个闭合的大括号的位置
                last_brace_pos = json_str.rfind('}')
                if last_brace_pos != -1:
                    # 在最后一个闭合大括号后添加缺失的闭合大括号
                    json_str = json_str[: last_brace_pos + 1] + '}'

            # 2. 确保所有引号都是成对出现的
            quote_count = json_str.count('"')
            if quote_count % 2 != 0:
                # 如果引号数量是奇数，尝试在末尾添加一个引号
                json_str = json_str.rstrip() + '"'

            # 3. 修复缺少逗号的问题 - 在 }" 和 " 之间添加逗号（如果它们在同一行）
            json_str = re.sub(r'(\}"\s*)\n\s*"', r'\1,\n"', json_str)

            # 4. 修复多余的逗号问题 - 移除对象或数组末尾的逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 5. 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON
            data = json.loads(json_str)
            return data
        except Exception as e:
            self.logger.error(f'修复JSON时出错: {e}')
            # 如果修复失败，尝试使用更简单的修复方法
            try:
                import re

                # 尝试提取所有的键值对
                pattern = r'"([^"]+)"\s*:\s*([0-9.]+)'
                matches = re.findall(pattern, response)

                result = {}
                for match in matches:
                    key, score = match
                    result[key] = float(score)

                if result:
                    return result
            except Exception as e2:
                self.logger.error(f'简单修复方法也失败了: {e2}')

            # 如果所有方法都失败，返回空字典
            return {}

    def _calculate_price_scores_default(
        self, bidder_prices: Dict[str, float], price_rule
    ) -> Dict[str, float]:
        """
        使用默认方法计算价格分（当AI计算失败时使用）

        Args:
            bidder_prices: 投标人报价字典
            price_rule: 价格评分规则

        Returns:
            Dict[str, float]: 投标人名称到价格分的映射
        """
        try:
            self.logger.info('使用默认方法计算价格分')

            if not bidder_prices:
                self.logger.error('没有投标人报价用于默认价格分计算')
                return {}

            # 获取有效的投标人报价
            valid_prices = {
                name: price
                for name, price in bidder_prices.items()
                if price is not None and isinstance(price, (int, float)) and price > 0
            }

            if not valid_prices:
                self.logger.error('没有有效的投标人报价用于默认价格分计算')
                return {}

            # 获取价格分满分
            max_score = price_rule.Child_max_score or 40

            # 根据公式计算价格分
            # 假设公式是: 投标报价得分＝(评标基准价/投标报价)×价格权重×100
            if '评标基准价' in (price_rule.description or ''):
                # 如果描述中提到了评标基准价，需要先计算评标基准价
                # 简化处理：使用最低价作为评标基准价
                benchmark_price = min(valid_prices.values())
                price_scores = {}

                for bidder_name, price in valid_prices.items():
                    try:
                        # 投标报价得分＝(评标基准价/投标报价)×价格权重×100
                        # 简化处理：假设价格权重为1
                        score = (benchmark_price / price) * max_score
                        price_scores[bidder_name] = round(score, 2)
                    except Exception as e:
                        self.logger.error(
                            f'计算投标人 {bidder_name} 的价格分时出错: {e}'
                        )
                        price_scores[bidder_name] = 0

                self.logger.info(f'默认方法计算的价格分: {price_scores}')
                return price_scores
            else:
                # 如果没有明确的公式，使用简单的低价高分规则
                min_price = min(valid_prices.values())
                max_price = max(valid_prices.values())
                price_range = max_price - min_price

                price_scores = {}
                for bidder_name, price in valid_prices.items():
                    try:
                        if price_range > 0:
                            # 线性计算：最低价得满分，最高价得0分
                            score = ((max_price - price) / price_range) * max_score
                        else:
                            # 所有价格相同，都得满分
                            score = max_score
                        price_scores[bidder_name] = round(score, 2)
                    except Exception as e:
                        self.logger.error(
                            f'计算投标人 {bidder_name} 的价格分时出错: {e}'
                        )
                        price_scores[bidder_name] = 0

                self.logger.info(f'默认方法计算的价格分: {price_scores}')
                return price_scores

        except Exception as e:
            self.logger.error(f'默认价格分计算出错: {e}')
            return {}
