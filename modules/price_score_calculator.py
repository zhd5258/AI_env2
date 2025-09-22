"""
价格分计算模块
负责在所有投标方分析完成后，根据评标规则进行综合价格分计算
"""

import logging
import json
from typing import List, Dict, Any, Optional, Union
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
        优化：确保只使用AI大模型进行价格分计算，不使用默认计算方法
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
                    f'找到价格评分规则: 满分 {price_rule.Child_max_score}, 公式: {price_rule.price_formula}, 描述: {price_rule.description}'
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
                # 可选：记录保证金候选（不参与总价计算，便于调试与后续使用）
                try:
                    from modules.enhanced_price_extractor import EnhancedPriceExtractor

                    extractor = EnhancedPriceExtractor()
                    # 这里无法直接拿到每家PDF文本，保持接口稳定，仅打印提示
                    self.logger.info(
                        '已加载保证金提取器（仅用于后续接入文本源时区分总价/保证金）。'
                    )
                except Exception as _:
                    pass
                self.logger.info(
                    f'提取到 {len(bidder_prices)} 个投标人的报价: {bidder_prices}'
                )

                # 5. 构造发送给AI大模型的完整prompt
                # 格式: "投标人1：投标总价1,投标人2：投标总价2,投标人3：投标总价3,......."
                bidder_info_str = ','.join(
                    [f'{name}：{price}' for name, price in bidder_prices.items()]
                )

                # 优化：简化prompt内容
                prompt = f"""你是一个评标专家，现在各投标人的投标总价为：『{bidder_info_str}』,价格评价标准为：『{price_rule.description}』,请计算各投标人的价格分。请返回格式为JSON格式：『投标人1：价格分1,投标人2：价格分2,投标人3：价格分3,.......』,请返回结果。"""

                self.logger.info('=' * 50)
                self.logger.info('发送给AI大模型的价格分计算请求:')
                self.logger.info(f'投标人报价信息: {bidder_info_str}')
                self.logger.info(f'价格评价标准: {price_rule.description}')
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
                    price_scores = self._parse_price_scores_from_ai_response(
                        ai_response
                    )
                    self.logger.info(f'解析后的价格分计算结果: {price_scores}')

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
                        old_price_score = result.price_score or 0  # 处理 None 情况
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
        注意：根据新规范，此方法不再使用，价格分计算已移至calculate_project_price_scores方法中统一处理

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula: 价格计算公式（可选）

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        # 根据新规范，此方法已废弃，仅作兼容性保留
        self.logger.warning('调用了已废弃的 _calculate_price_scores 方法')
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
        注意：根据新规范，此方法不再使用，价格分计算已移至calculate_project_price_scores方法中统一处理

        Args:
            bidder_prices: 投标方价格字典
            max_score: 价格分满分
            formula_info: 公式信息

        Returns:
            Dict[str, float]: 投标方名称到价格分的映射
        """
        # 根据新规范，此方法已废弃，仅作兼容性保留
        self.logger.warning('调用了已废弃的 _calculate_with_custom_formula 方法')
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

            # 清理响应文本，移除可能的代码块标记
            clean_response = ai_response.strip()
            if clean_response.startswith('```json'):
                clean_response = clean_response[7:]
            if clean_response.endswith('```'):
                clean_response = clean_response[:-3]
            clean_response = clean_response.strip()

            parsed_results = json.loads(clean_response)
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
                    # 清理匹配到的JSON文本
                    clean_match = match.strip()
                    if clean_match.startswith('```json'):
                        clean_match = clean_match[7:]
                    if clean_match.endswith('```'):
                        clean_match = clean_match[:-3]
                    clean_match = clean_match.strip()

                    parsed_results = json.loads(clean_match)
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

        # 方法4: 尝试按逗号分隔解析
        try:
            # 按逗号分隔，然后解析每个部分
            parts = ai_response.strip().split(',')
            result = {}
            for part in parts:
                # 匹配 投标人名称：分数 格式
                match = re.search(r'([^：:]+)[：:]\s*([0-9]+\.?[0-9]*)', part)
                if match:
                    bidder_name = match.group(1).strip()
                    score = float(match.group(2))
                    result[bidder_name] = score

            if result:
                self.logger.info(f'成功通过方法4解析AI响应: {result}')
                return result
        except Exception as e:
            self.logger.debug(f'方法4解析失败: {e}')

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
