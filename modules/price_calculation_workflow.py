#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
价格计算工作流模块
实现统一的价格提取和计算流程
"""

import os
import logging
import glob
import json
import datetime
from typing import Dict, List, Tuple, Optional, Any
from sqlalchemy.orm import Session

from models.database import BidDocument, AnalysisResult, ScoringRule
from modules.unified_extractor import UnifiedExtractor, create_bidder_price_array
from modules.local_ai_analyzer import LocalAIAnalyzer
from modules.workflow_status import (
    WorkflowStatus,
    AnalysisTaskStatus,
    PriceCalculationStatus,
)

logger = logging.getLogger(__name__)


class PriceCalculationWorkflow:
    """价格计算工作流，实现统一的价格提取和计算流程"""

    def __init__(self, db_session: Session):
        self.db = db_session
        self.logger = logging.getLogger(__name__)
        self.ai_analyzer = LocalAIAnalyzer()

    def _log_price_calculation_failure_details(self, project_id: int):
        """记录价格分计算失败的详细信息，用于调试"""
        try:
            self.logger.info(f'=== 价格分计算失败详细信息 (项目 {project_id}) ===')

            # 检查项目是否存在
            from models.database import TenderProject, ScoringRule, AnalysisResult

            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            if not project:
                self.logger.error(f'项目 {project_id} 不存在')
                return

            # 检查评分规则
            scoring_rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .all()
            )

            price_rule = None
            for rule in scoring_rules:
                if getattr(rule, 'is_price_criteria', False):
                    price_rule = rule
                    break

            if not price_rule:
                self.logger.error(f'项目 {project_id} 没有找到价格评分规则')
                # 记录所有评分规则的信息用于调试
                for rule in scoring_rules:
                    rule_id = (
                        getattr(rule, 'id', 'N/A') if hasattr(rule, 'id') else 'N/A'
                    )
                    child_item_name = (
                        getattr(rule, 'Child_Item_Name', 'N/A')
                        if hasattr(rule, 'Child_Item_Name')
                        else 'N/A'
                    )
                    is_price_criteria = (
                        getattr(rule, 'is_price_criteria', 'N/A')
                        if hasattr(rule, 'is_price_criteria')
                        else 'N/A'
                    )
                    self.logger.info(
                        f'评分规则详情: id={rule_id}, '
                        f'Child_Item_Name={child_item_name}, '
                        f'is_price_criteria={is_price_criteria}'
                    )
            else:
                child_max_score = (
                    getattr(price_rule, 'Child_max_score', 'N/A')
                    if hasattr(price_rule, 'Child_max_score')
                    else 'N/A'
                )
                price_formula = (
                    getattr(price_rule, 'price_formula', 'N/A')
                    if hasattr(price_rule, 'price_formula')
                    else 'N/A'
                )
                description = (
                    getattr(price_rule, 'description', 'N/A')
                    if hasattr(price_rule, 'description')
                    else 'N/A'
                )
                self.logger.info(
                    f'找到价格评分规则: 满分 {child_max_score}, '
                    f'公式: {price_formula}, '
                    f'描述: {description}'
                )

            # 检查分析结果
            analysis_results = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            if not analysis_results:
                self.logger.error(f'项目 {project_id} 没有找到分析结果')
            else:
                self.logger.info(
                    f'项目 {project_id} 找到 {len(analysis_results)} 个分析结果'
                )
                for result in analysis_results:
                    result_id = (
                        getattr(result, 'id', 'N/A') if hasattr(result, 'id') else 'N/A'
                    )
                    bidder_name = getattr(
                        result,
                        'bidder_name',
                        f'未知投标人_{result_id}',
                    )
                    price = getattr(result, 'extracted_price', 'N/A')
                    self.logger.info(f'投标人 [{bidder_name}] 提取价格: {price}')

            self.logger.info('=== 价格分计算失败详细信息结束 ===')
        except Exception as e:
            self.logger.error(f'记录价格分计算失败详细信息时出错: {e}')

    def execute_workflow(self, project_id: int) -> bool:
        """
        执行价格计算工作流

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功执行
        """
        try:
            self.logger.info(f'开始执行项目 {project_id} 的价格计算工作流')

            # 检查必要参数
            if not project_id:
                self.logger.error('价格计算工作流触发条件不满足：缺少项目ID')
                return False

            self.logger.info('=== 开始联合提取器工作 ===')

            # 1. 遍历output目录下的md文件，提取投标人信息
            self.logger.info(f'步骤1: 提取项目 {project_id} 的所有投标人信息')
            bidders_info = self._extract_all_bidders_info(project_id)
            if not bidders_info:
                self.logger.warning(f'项目 {project_id} 未提取到任何投标人信息')
                return False

            self.logger.info(f'成功提取到 {len(bidders_info)} 个投标人的信息')

            # 2. 创建投标人价格数组
            self.logger.info('步骤2: 创建投标人价格数组')
            bidder_price_dict = create_bidder_price_array(bidders_info)
            self.logger.info(f'投标人价格数组: {bidder_price_dict}')

            # 打印每个投标人的详细信息
            self.logger.info('=== 全部投标人信息 ===')
            for bidder in bidders_info:
                self.logger.info(
                    f'投标人: {bidder["bidder_name"]}, 投标总价: {bidder["bid_price"]}'
                )
            self.logger.info('=== 投标人信息结束 ===')

            # 检查是否有足够的投标人信息
            if len(bidder_price_dict) < 2:
                self.logger.warning(
                    f'项目 {project_id} 投标人数量不足2个，无法计算价格分'
                )
                # 即使投标人数量不足，也要继续执行，因为可能需要更新项目状态
                # return False

            # 3. 获取价格评分规则
            self.logger.info(f'步骤3: 获取项目 {project_id} 的价格评分规则')
            price_rule = self._get_price_scoring_rule(project_id)
            if not price_rule:
                self.logger.error(f'项目 {project_id} 没有找到价格评分规则')
                return False

            # 4. 调用价格分计算器模块进行计算和保存
            self.logger.info('步骤4: 调用价格分计算器进行计算和保存')
            from modules.price_score_calculator import PriceScoreCalculator

            price_calculator = PriceScoreCalculator(db_session=self.db)
            calculation_success = price_calculator.calculate_project_price_scores(
                project_id
            )

            if not calculation_success:
                self.logger.error(f'项目 {project_id} 的价格分计算和保存失败')
                return False

            # 5. 更新项目状态
            self.logger.info('步骤5: 更新项目状态')
            self._update_project_status(project_id)

            self.logger.info(f'项目 {project_id} 价格计算工作流执行完成')
            return True

        except Exception as e:
            self.logger.error(f'执行价格计算工作流时出错: {e}', exc_info=True)
            return False

    def _extract_all_bidders_info(self, project_id: int) -> List[Dict[str, Any]]:
        """
        遍历output目录下的md文件，提取所有投标人的信息

        Args:
            project_id: 项目ID

        Returns:
            List[Dict[str, Any]]: 投标人信息列表
        """
        self.logger.info(f'开始提取项目 {project_id} 的所有投标人信息')

        # 获取项目下的所有投标文件
        bid_documents = (
            self.db.query(BidDocument)
            .filter(BidDocument.project_id == project_id)
            .all()
        )

        # 创建统一提取器实例
        unified_extractor = UnifiedExtractor(db_session=self.db)

        bidders_info = []

        # 遍历每个投标文件
        self.logger.info(f'项目 {project_id} 共有 {len(bid_documents)} 个投标文件')
        for bid_doc in bid_documents:
            try:
                self.logger.info(f'处理投标文件: {bid_doc.file_path}')

                # 提取投标人名称和价格
                bidder_name, bid_price = unified_extractor.extract_bidder_info(
                    bid_doc.file_path
                )

                # 确保投标人名称不为空
                if (
                    not bidder_name
                    or not bidder_name.strip()
                    or bidder_name == '未知投标方'
                ):
                    # 尝试从数据库中获取投标人名称
                    if (
                        bid_doc.bidder_name
                        and bid_doc.bidder_name.strip()
                        and bid_doc.bidder_name != '未知投标方'
                    ):
                        bidder_name = bid_doc.bidder_name
                        self.logger.info(f'使用数据库中的投标人名称: {bidder_name}')
                    else:
                        # 使用文件名作为最后的备用方案
                        filename = os.path.basename(str(bid_doc.file_path))
                        bidder_name = os.path.splitext(filename)[0]
                        bid_doc_id = (
                            getattr(bid_doc, 'id', 'N/A')
                            if hasattr(bid_doc, 'id')
                            else 'N/A'
                        )
                        if not bidder_name or not bidder_name.strip():
                            bidder_name = f'投标人_{bid_doc_id}'
                        self.logger.info(f'使用文件名作为备用投标人名称: {bidder_name}')

                # 确保bid_price是float类型
                if bid_price is None:
                    # 尝试从数据库中获取价格
                    if (
                        bid_doc.analysis_result
                        and bid_doc.analysis_result.extracted_price is not None
                    ):
                        bid_price = float(bid_doc.analysis_result.extracted_price)
                        self.logger.info(f'使用数据库中的价格: {bid_price}')
                    else:
                        # 如果价格提取失败，尝试重新提取价格
                        self.logger.warning(
                            f'投标文件 {bid_doc.file_path} 的价格提取失败，尝试重新提取'
                        )
                        try:
                            # 重新提取价格
                            re_extracted_price = unified_extractor.extract_bid_price(
                                bid_doc.file_path
                            )
                            if (
                                re_extracted_price is not None
                                and re_extracted_price > 0
                            ):
                                bid_price = float(re_extracted_price)
                                self.logger.info(f'重新提取到价格: {bid_price}')

                                # 立即保存价格到数据库
                                if bid_doc.analysis_result:
                                    bid_doc.analysis_result.extracted_price = bid_price
                                    self.db.commit()
                                    self.logger.info(
                                        f'已将价格 {bid_price} 保存到数据库'
                                    )
                                else:
                                    self.logger.warning(
                                        '分析结果对象不存在，无法保存价格'
                                    )
                            else:
                                # 如果重新提取也失败，记录错误但不使用默认值
                                self.logger.error(
                                    f'投标文件 {bid_doc.file_path} 的价格提取完全失败'
                                )
                                self.logger.error(
                                    '这可能导致价格分计算失败，请检查文件内容'
                                )
                                # 不设置默认值，让后续逻辑处理
                                continue
                        except Exception as e:
                            self.logger.error(f'重新提取价格时出错: {e}')
                            self.logger.error(
                                f'投标文件 {bid_doc.file_path} 的价格提取失败'
                            )
                            continue
                else:
                    # 确保价格是float类型
                    bid_price = float(bid_price)
                    # 验证价格是否合理
                    if bid_price <= 0:
                        self.logger.warning(
                            f'投标人 {bidder_name} 的价格 {bid_price} 不合理，可能提取失败'
                        )
                    else:
                        # 价格合理，保存到数据库
                        if bid_doc.analysis_result:
                            bid_doc.analysis_result.extracted_price = bid_price
                            self.db.commit()
                            self.logger.info(f'已将价格 {bid_price} 保存到数据库')
                        else:
                            self.logger.warning('分析结果对象不存在，无法保存价格')

                # 保存到数据库
                unified_extractor.save_bidder_info_to_db(
                    bid_doc.id, bidder_name, bid_price
                )

                # 添加到结果列表
                bidders_info.append(
                    {
                        'bid_document_id': bid_doc.id,
                        'bidder_name': bidder_name,
                        'bid_price': bid_price,
                        'file_path': bid_doc.file_path,
                    }
                )

                self.logger.info(f'成功提取投标人信息: {bidder_name} - {bid_price}')

            except Exception as e:
                self.logger.error(
                    f'处理投标文件 {bid_doc.file_path} 时出错: {e}', exc_info=True
                )
                # 即使单个文件处理失败，也继续处理其他文件
                continue

        self.logger.info(f'完成提取，共处理 {len(bidders_info)} 个投标人')
        return bidders_info

    def _get_price_scoring_rule(self, project_id: int) -> Optional[ScoringRule]:
        """
        获取项目的价格评分规则

        Args:
            project_id: 项目ID

        Returns:
            Optional[ScoringRule]: 价格评分规则
        """
        try:
            scoring_rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .all()
            )

            # 查找价格评分规则
            price_rule = None
            for rule in scoring_rules:
                if getattr(rule, 'is_price_criteria', False):
                    price_rule = rule
                    break

            # 如果没有找到价格评分规则，记录详细信息
            if not price_rule:
                self.logger.error(f'项目 {project_id} 没有找到价格评分规则')
                # 记录所有评分规则的信息用于调试
                for rule in scoring_rules:
                    rule_id = (
                        getattr(rule, 'id', 'N/A') if hasattr(rule, 'id') else 'N/A'
                    )
                    child_item_name = (
                        getattr(rule, 'Child_Item_Name', 'N/A')
                        if hasattr(rule, 'Child_Item_Name')
                        else 'N/A'
                    )
                    is_price_criteria = (
                        getattr(rule, 'is_price_criteria', 'N/A')
                        if hasattr(rule, 'is_price_criteria')
                        else 'N/A'
                    )
                    self.logger.info(
                        f'评分规则详情: id={rule_id}, '
                        f'Child_Item_Name={child_item_name}, '
                        f'is_price_criteria={is_price_criteria}'
                    )
            else:
                rule_id = (
                    getattr(price_rule, 'id', 'N/A')
                    if hasattr(price_rule, 'id')
                    else 'N/A'
                )
                child_item_name = (
                    getattr(price_rule, 'Child_Item_Name', 'N/A')
                    if hasattr(price_rule, 'Child_Item_Name')
                    else 'N/A'
                )
                child_max_score = (
                    getattr(price_rule, 'Child_max_score', 'N/A')
                    if hasattr(price_rule, 'Child_max_score')
                    else 'N/A'
                )
                self.logger.info(
                    f'找到价格评分规则: id={rule_id}, '
                    f'Child_Item_Name={child_item_name}, '
                    f'Child_max_score={child_max_score}'
                )

            return price_rule
        except Exception as e:
            self.logger.error(f'获取价格评分规则时出错: {e}', exc_info=True)
            return None

    def _construct_ai_prompt(
        self, bidder_price_dict: Dict[str, float], price_rule: ScoringRule
    ) -> str:
        """
        构造发送给AI大模型的prompt

        Args:
            bidder_price_dict: 投标人价格字典
            price_rule: 价格评分规则

        Returns:
            str: 构造的prompt
        """
        try:
            # 格式: "投标人1：投标总价1,投标人2：投标总价2,投标人3：投标总价3,......."
            bidder_info_str = ','.join(
                [f'{name}：{price}' for name, price in bidder_price_dict.items()]
            )

            # 获取价格分的最高分
            price_max_score = getattr(price_rule, 'Child_max_score', None)
            # 检查Parent_max_score作为备选
            parent_max_score = getattr(price_rule, 'Parent_max_score', None)

            # 如果Child_max_score为0或None，检查Parent_max_score
            if price_max_score is None or price_max_score == 0:
                if parent_max_score is not None and parent_max_score > 0:
                    price_max_score = float(parent_max_score)
                else:
                    # 如果都没有有效值，使用默认值40
                    price_max_score = 40
            else:
                price_max_score = float(price_max_score)

            # 确保价格最高分是有效的
            if price_max_score <= 0:
                price_max_score = 40
                self.logger.warning('价格规则的最高分值无效，使用默认值40分')

            # 获取价格评分规则的描述
            price_description = getattr(price_rule, 'description', '未提供评分标准')

            # 构造发送给AI大模型的prompt
            prompt = f"""你是一个专业的评标专家，请根据以下信息计算各投标人的价格分：

【投标人报价信息】
{bidder_info_str}

【价格评价标准】
{price_description}

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

            # 注意：此方法已废弃，价格分计算现在由 PriceScoreCalculator 统一处理
            # 保留此方法以避免破坏现有代码，但实际不会被调用
            self.logger.debug('构造AI prompt完成（已废弃的方法）')
            return prompt
        except Exception as e:
            self.logger.error(f'构造AI prompt时出错: {e}', exc_info=True)
            # 返回一个默认的prompt
            default_prompt = """你是一个专业的评标专家，请根据以下信息计算各投标人的价格分：
【投标人报价信息】
公司A：1000000,公司B：950000,公司C：1100000
【价格评价标准】
价格分计算方法：满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分；其他投标人的价格分按下列公式计算：投标报价得分=（评标基准价／投标报价）×价格权重×100
【价格分满分】
40分
【计算要求】
1. 根据价格评价标准计算每个投标人的价格分
2. 价格分必须是0-40之间的数字（满分为40分）
3. 最低价的投标人应该得到最高分（40分）
4. 严格按照价格评价标准中的计算公式进行计算
【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{"投标人1": 价格分1, "投标人2": 价格分2, "投标人3": 价格分3}
示例（假设满分为40分）：
{"公司A": 38.2, "公司B": 40.0, "公司C": 35.3}"""
            self.logger.info('=== 发送给AI大模型的默认Prompt ===')
            self.logger.info(default_prompt)
            self.logger.info('=== 默认Prompt结束 ===')
            return default_prompt

    def _update_project_status(self, project_id: int):
        """
        更新项目状态

        Args:
            project_id: 项目ID
        """
        try:
            # 使用统一的项目状态管理器
            from modules.project_status_manager import ProjectStatusManager

            status_manager = ProjectStatusManager(db_session=self.db)
            return status_manager.update_project_status(project_id, 'price_calculated')
        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}', exc_info=True)
            return False
