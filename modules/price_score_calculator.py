"""
价格分计算模块
负责在所有投标方分析完成后，根据评标规则进行综合价格分计算
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

from modules.database import SessionLocal, AnalysisResult, ScoringRule, TenderProject
from modules.price_calculator_helpers import PriceScoreCalculatorHelpers
from modules.local_ai_analyzer import LocalAIAnalyzer


class PriceScoreCalculator(PriceScoreCalculatorHelpers):
    """价格分计算器"""

    def __init__(self, db_session=None):
        # 先初始化logger，再调用父类的__init__()
        self.logger = logging.getLogger(__name__)
        super().__init__()
        self.db_session = db_session
        # 初始化AI分析器
        self.ai_analyzer = LocalAIAnalyzer()

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

    def calculate_project_price_scores(self, project_id: int) -> bool:
        """
        计算项目中所有投标人的价格分（统一计算，不针对单个投标人）

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否计算成功
        """
        try:
            self.logger.info(f'开始计算项目 {project_id} 的价格分')

            # 使用数据库会话上下文管理器
            with self._get_db_session() as db:
                # 1. 获取项目信息
                project = (
                    db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
                if not project:
                    self.logger.error(f'项目 {project_id} 不存在')
                    return False

                # 2. 获取评分规则
                scoring_rules = (
                    db.query(ScoringRule)
                    .filter(ScoringRule.project_id == project_id)
                    .all()
                )
                price_rule = next(
                    (rule for rule in scoring_rules if rule.is_price_criteria), None
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
                    f'找到价格评分规则: 满分 {price_rule.Parent_max_score}, 公式: {price_rule.price_formula}, 描述: {price_rule.description}'
                )

                # 3. 获取所有分析结果
                analysis_results = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.project_id == project_id)
                    .all()
                )

                if not analysis_results:
                    self.logger.warning(f'项目 {project_id} 没有找到分析结果')
                    return False

                # 4. 仅提取当前项目的投标人报价
                bidder_prices = self._extract_bidder_prices(analysis_results)
                self.logger.info(
                    f'提取到 {len(bidder_prices)} 个投标人的报价: {bidder_prices}'
                )

                # 5. 计算所有投标人的价格分（统一计算）
                price_scores = self._calculate_price_scores(
                    bidder_prices, price_rule.Parent_max_score, formula_info
                )
                self.logger.info(f'计算出价格分: {price_scores}')

                # 若无法计算价格分（例如缺少有效公式或AI失败），使用默认计算方法
                if not price_scores:
                    self.logger.warning(
                        '价格分未通过AI计算，使用默认计算方法。'
                    )
                    # 使用默认计算方法：满足招标文件要求且投标报价最低的投标报价为评标基准价，其价格分为满分
                    if bidder_prices:
                        min_price = min(bidder_prices.values())
                        price_scores = {}
                        for bidder, price in bidder_prices.items():
                            if price == min_price:
                                # 最低报价得满分
                                price_scores[bidder] = price_rule.Parent_max_score
                                self.logger.info(
                                    f'投标人 {bidder} 报价为最低价 {price}，得满分 {price_rule.Parent_max_score}'
                                )
                            else:
                                # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*满分
                                score = (min_price / price) * price_rule.Parent_max_score
                                price_scores[bidder] = round(score, 2)
                                self.logger.info(f'投标人 {bidder} 报价 {price}，得分 {price_scores[bidder]}')

                # 6. 更新每个投标人的价格分和总分
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
                    new_price_score = price_scores.get(bidder_name, 0)
                    self.logger.info(
                        f'投标人 [{bidder_name}] 报价 {bidder_prices.get(bidder_name, "N/A")}，价格分 {new_price_score}'
                    )

                    try:
                        # 确保只更新当前项目的记录
                        if result.project_id != project_id:
                            self.logger.warning(
                                f'投标人 [{bidder_name}] 的记录不属于当前项目 {project_id}，跳过更新'
                            )
                            continue

                        # 更新价格分
                        old_price_score = result.price_score
                        result.price_score = new_price_score
                        self.logger.info(
                            f'  更新价格分: {old_price_score} -> {new_price_score}'
                        )

                        # 更新总分
                        old_total_score = result.total_score or 0

                        # 从详细评分中获取除价格分外的其他分数总和
                        other_scores_total = 0
                        if result.detailed_scores:
                            try:
                                detailed_scores = (
                                    json.loads(result.detailed_scores)
                                    if isinstance(result.detailed_scores, str)
                                    else result.detailed_scores
                                )
                                other_scores_total = self._calculate_other_scores_total(
                                    detailed_scores
                                )
                            except Exception as e:
                                self.logger.error(
                                    f'解析投标人 {bidder_name} 的详细评分时出错: {e}'
                                )

                        # 新总分 = 其他分数总和 + 新价格分
                        new_total_score = other_scores_total + new_price_score
                        result.total_score = round(new_total_score, 2)
                        self.logger.info(
                            f'  更新总分: {old_total_score} -> {new_total_score}'
                        )

                        updated_count += 1

                    except Exception as e:
                        self.logger.error(
                            f'更新投标人 {bidder_name} 的价格分时出错: {e}'
                        )
                        continue

                db.commit()
                self.logger.info(f'成功更新了 {updated_count} 个投标方的价格分和总分')
                self.logger.info('=' * 50)
                return True

        except Exception as e:
            self.logger.error(f'更新数据库中的价格分时出错: {e}')
            return False

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
            is_price_criteria = any(
                keyword in criteria_name
                for keyword in ['价格', 'price', '报价', '投标报价']
            ) or score.get('is_price_criteria', False)

            if is_price_criteria and 'score' in score:
                return float(score.get('score', 0.0))

            if 'children' in score and score['children']:
                child_price_score = self._find_existing_price_score(score['children'])
                # 假设只有一个价格项，找到就返回
                if child_price_score != 0.0:
                    return child_price_score

        return 0.0

    def _update_price_in_scores(
        self,
        scores: Union[List[Dict[str, Any]], Dict[str, Any]],
        new_price_score: float,
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
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
                if any(
                    keyword in key for keyword in ['价格', 'price', '报价', '投标报价']
                ):
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

            updated_scores.append(updated_score)

        return updated_scores

    def _calculate_price_scores(
        self,
        bidder_prices: Dict[str, float],
        max_score: float,
        formula: Optional[str] = None,
    ) -> Dict[str, float]:
        """
        根据价格计算公式计算各投标方的价格分

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula: 价格计算公式（可选）

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not bidder_prices:
            return {}

        # 如果有专门的价格计算公式或描述，使用特殊计算方法
        if formula:
            # 检查是否是AI生成的格式
            if isinstance(formula, dict):  # 处理包含formula和description的字典
                formula_info = formula
            elif isinstance(formula, str) and (
                '价格计算公式:' in formula or '1. 价格计算公式:' in formula
            ):
                # 解析AI返回的格式
                formula_info = self._parse_price_formula(formula, None)
            else:
                formula_info = {'formula': formula, 'description': ''}

            # 检查是否有公式或描述
            has_formula = (
                formula_info.get('formula')
                if isinstance(formula_info.get('formula'), str)
                else None
            )
            has_description = (
                formula_info.get('description')
                if isinstance(formula_info.get('description'), str)
                else None
            )

            if has_formula or has_description:
                return self._calculate_with_custom_formula(
                    bidder_prices, max_score, formula_info
                )

        # 没有提供公式或描述时，严格按规范：不允许默认计算，直接返回空结果
        self.logger.error(
            '未提供有效的价格计算公式或描述，按照规范禁止使用默认公式，价格分不计算。'
        )
        return {}

    def _parse_price_formula(
        self, formula_text: str, dummy_param
    ) -> Optional[Dict[str, Any]]:
        """
        解析AI返回的价格公式格式

        Args:
            formula_text: AI返回的公式文本
            dummy_param: 占位参数，为了与price_manager中的方法签名兼容

        Returns:
            Optional[Dict[str, Any]]: 解析后的公式信息
        """
        if not formula_text:
            return None

        formula_info = {'formula': formula_text, 'variables': {}}

        # 解析AI返回的格式
        if '价格计算公式:' in formula_text or '1. 价格计算公式:' in formula_text:
            lines = formula_text.split('\n')
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

        return formula_info

    def _calculate_with_custom_formula(
        self,
        bidder_prices: Dict[str, float],
        max_score: float,
        formula_info: Dict[str, Any],
    ) -> Dict[str, float]:
        """
        使用自定义公式计算价格分

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula_info: 公式信息

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        # 获取公式和描述
        formula = formula_info.get('formula', '')
        description = formula_info.get('description', '')

        # 优先使用公式，如果没有公式则使用描述
        price_formula = formula if formula else description

        self.logger.info(f'使用自定义价格计算规则: {price_formula}')

        # 记录价格计算规则
        self.logger.info(f'价格计算规则详情: {formula_info}')
        self.logger.info(f'投标方报价信息: {bidder_prices}')
        self.logger.info(f'价格分满分: {max_score}')

        # 如果没有提供有效的公式或描述，记录错误并返回空结果
        if not price_formula:
            self.logger.error('没有提供有效的价格计算公式或描述')
            return {}

        # 构造发送给AI大模型的prompt
        prompt = f"""
你是一个专业的评标专家，请根据以下价格评分规则和各投标人的投标报价，计算每个投标人的价格得分。

价格评分规则:
{price_formula}

各投标人报价信息:
{bidder_prices}

价格分满分: {max_score}

请严格按照以下JSON格式输出结果:
{{
    "投标人名称1": 得分1,
    "投标人名称2": 得分2,
    // ...更多投标人
}}

只输出JSON结果，不要包含其他解释性文字。
"""

        # 记录发送给AI大模型的信息
        self.logger.info('=' * 50)
        self.logger.info('发送给AI大模型的价格分计算请求:')
        self.logger.info(f'价格评分规则: {price_formula}')
        self.logger.info(f'投标人报价: {bidder_prices}')
        self.logger.info(f'价格分满分: {max_score}')
        self.logger.info('完整prompt:')
        self.logger.info(prompt)
        self.logger.info('=' * 50)

        try:
            # 调用AI大模型计算价格分
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 记录AI大模型的返回值
            self.logger.info('=' * 50)
            self.logger.info('AI大模型返回的完整响应:')
            self.logger.info(ai_response)
            self.logger.info('=' * 50)

            # 解析AI响应
            price_scores = self._parse_price_scores_from_ai_response(ai_response)

            # 记录解析后的价格分计算结果
            self.logger.info(f'解析后的价格分计算结果: {price_scores}')

            return price_scores
        except Exception as e:
            self.logger.error(f'调用AI大模型计算价格分时出错: {e}')
            return {}

    def _parse_price_scores_from_ai_response(
        self, ai_response: str
    ) -> Dict[str, float]:
        """
        从AI响应中解析价格分计算结果

        Args:
            ai_response: AI大模型的响应

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        if not ai_response:
            self.logger.warning('AI响应为空')
            return {}

        # 尝试多种方式解析响应
        parsed_results = {}

        # 方法1: 直接尝试解析整个响应为JSON
        try:
            import json

            parsed_results = json.loads(ai_response)
            if isinstance(parsed_results, dict):
                # 验证并转换结果
                result = {}
                for bidder, score in parsed_results.items():
                    if isinstance(score, (int, float)):
                        result[bidder] = float(score)
                self.logger.info(f'成功通过方法1解析AI响应: {result}')
                return result
        except json.JSONDecodeError:
            self.logger.debug('方法1解析失败，尝试方法2')

        # 方法2: 尝试从响应中提取JSON部分
        try:
            import json
            import re

            # 查找可能的JSON对象
            json_pattern = r'\{[^}]+\}'
            matches = re.findall(json_pattern, ai_response)

            for match in matches:
                try:
                    parsed_results = json.loads(match)
                    if isinstance(parsed_results, dict):
                        # 验证并转换结果
                        result = {}
                        for bidder, score in parsed_results.items():
                            if isinstance(score, (int, float)):
                                result[bidder] = float(score)
                        if result:  # 如果成功解析到结果
                            self.logger.info(f'成功通过方法2解析AI响应: {result}')
                            return result
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            self.logger.debug(f'方法2解析失败: {e}')

        # 方法3: 尝试按行解析，查找键值对
        try:
            lines = ai_response.strip().split('\n')
            result = {}
            for line in lines:
                # 匹配 "投标人名称": 分数 格式
                match = re.search(r'"([^"]+)"\s*:\s*([0-9]+\.?[0-9]*)', line)
                if match:
                    bidder_name = match.group(1)
                    score = float(match.group(2))
                    result[bidder_name] = score

            if result:
                self.logger.info(f'成功通过方法3解析AI响应: {result}')
                return result
        except Exception as e:
            self.logger.debug(f'方法3解析失败: {e}')

        self.logger.warning(f'无法解析AI响应为有效的价格分计算结果: {ai_response}')
        return {}

    def _calculate_other_scores_total(self, detailed_scores) -> float:
        """
        计算除价格分外的其他分数总和

        Args:
            detailed_scores: 详细评分数据

        Returns:
            float: 其他分数总和
        """
        total = 0
        if not detailed_scores:
            return total

        try:
            # 处理列表格式的详细评分
            if isinstance(detailed_scores, list):
                for item in detailed_scores:
                    # 跳过价格评分项
                    if item.get('is_price_criteria') or (
                        item.get('Child_Item_Name', '').startswith('价格')
                    ):
                        continue
                    # 累加其他评分项
                    score = item.get('score', 0)
                    if isinstance(score, (int, float)):
                        total += score
            # 处理字典格式的详细评分（旧格式兼容）
            elif isinstance(detailed_scores, dict):
                for key, score in detailed_scores.items():
                    # 跳过价格评分项
                    if key.startswith('价格'):
                        continue
                    if isinstance(score, (int, float)):
                        total += score
        except Exception as e:
            self.logger.error(f'计算其他分数总和时出错: {e}')

        return total


# 测试代码
if __name__ == '__main__':
    calculator = PriceScoreCalculator()
    # 这里可以添加测试代码
    pass
