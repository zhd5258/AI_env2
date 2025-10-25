#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
智能规则分类器模块
使用AI大模型对评分规则进行智能分类和标记
"""

import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models.database import ScoringRule
from modules.local_ai_analyzer import LocalAIAnalyzer


class IntelligentRulesClassifier:
    """智能规则分类器，使用AI大模型对评分规则进行智能分类和标记"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.ai_analyzer = LocalAIAnalyzer()
        self.logger = logging.getLogger(__name__)

    def classify_and_mark_rules(self, project_id: int) -> bool:
        """
        对项目中的评分规则进行智能分类和标记

        Args:
            project_id: 项目ID

        Returns:
            bool: 是否成功分类和标记
        """
        try:
            self.logger.info(f'开始对项目 {project_id} 的评分规则进行智能分类和标记')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 1. 获取项目中的所有评分规则
            scoring_rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .all()
            )

            if not scoring_rules:
                self.logger.warning(f'项目 {project_id} 没有找到评分规则')
                return True

            self.logger.info(f'找到 {len(scoring_rules)} 条评分规则')

            # 2. 分离定量规则和定性规则
            quantitative_rules = [
                rule for rule in scoring_rules if rule.is_quantitative
            ]
            qualitative_rules = [rule for rule in scoring_rules if rule.is_qualitative]

            self.logger.info(f'定量规则数量: {len(quantitative_rules)}')
            self.logger.info(f'定性规则数量: {len(qualitative_rules)}')

            # 3. 对定量规则进行智能分类，判断哪些需要综合计算
            if quantitative_rules:
                self._classify_quantitative_rules(quantitative_rules)

            # 4. 对定性规则进行智能筛选，删除无效规则
            if qualitative_rules:
                self._filter_qualitative_rules(qualitative_rules)

            # 5. 提交更改到数据库
            self.db.commit()
            self.logger.info(f'项目 {project_id} 的评分规则分类和标记完成')
            return True

        except Exception as e:
            self.logger.error(
                f'对项目 {project_id} 的评分规则进行智能分类和标记时出错: {e}'
            )
            if self.db:
                self.db.rollback()
            return False

    def _classify_quantitative_rules(self, quantitative_rules: List[ScoringRule]):
        """
        对定量规则进行智能分类，判断哪些需要综合计算

        Args:
            quantitative_rules: 定量规则列表
        """
        try:
            self.logger.info(f'开始对 {len(quantitative_rules)} 条定量规则进行智能分类')

            # 1. 构造发送给AI大模型的prompt
            rules_info = []
            for rule in quantitative_rules:
                rule_info = {
                    '规则名称': rule.Child_Item_Name or rule.Parent_Item_Name,
                    '规则描述': rule.description or '',
                    '满分': rule.Child_max_score or rule.Parent_max_score,
                    '是否价格规则': rule.is_price_criteria,
                }
                rules_info.append(rule_info)

            prompt = f"""你是一个专业的评标专家，请根据以下评分规则信息，判断哪些规则需要对全部投标文件进行综合计算（类似于价格分的计算方式）：

【评分规则列表】
{json.dumps(rules_info, ensure_ascii=False, indent=2)}

【判断标准】
需要综合计算的规则通常具有以下特征：
1. 需要根据所有投标人的相对表现进行排名的规则（如技术方案相对优劣排名）
2. 需要考虑全局数据的规则（如各投标人交付期的相对优势）
3. 需要进行横向比较的规则（如性能指标相对排名）
4. 价格分规则（通常需要综合计算）

【输出要求】
请返回一个JSON对象，包含以下字段：
1. "需要综合计算的规则": 一个数组，包含需要综合计算的规则名称
2. "理由": 对每个需要综合计算的规则给出判断理由

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{
  "需要综合计算的规则": ["规则名称1", "规则名称2"],
  "理由": {{
    "规则名称1": "判断理由1",
    "规则名称2": "判断理由2"
  }}
}}

示例：
{{
  "需要综合计算的规则": ["技术方案排名评分", "交付期相对优势"],
  "理由": {{
    "技术方案排名评分": "需要根据所有投标人的技术方案相对优劣进行排名",
    "交付期相对优势": "需要比较各投标人的交付期相对优势"
  }}
}}"""

            self.logger.info('构造AI prompt完成，开始调用AI大模型进行分类')

            # 输出发送给AI大模型的完整prompt
            self.logger.info('=== 发送给AI大模型的完整prompt ===')
            self.logger.info(prompt)
            self.logger.info('=== prompt结束 ===')

            # 2. 调用AI大模型进行分类
            ai_response = self.ai_analyzer.analyze_text(prompt)
            self.logger.info('AI大模型响应接收成功')

            # 输出AI大模型的完整响应
            self.logger.info('=== AI大模型的完整响应 ===')
            self.logger.info(ai_response)
            self.logger.info('=== 响应结束 ===')

            # 3. 解析AI响应
            classification_result = self._parse_classification_response(ai_response)

            # 4. 标记需要综合计算的规则
            if classification_result and '需要综合计算的规则' in classification_result:
                rules_needing_comprehensive_analysis = classification_result[
                    '需要综合计算的规则'
                ]
                reasons = classification_result.get('理由', {})

                self.logger.info(
                    f'AI大模型识别出需要综合计算的规则: {rules_needing_comprehensive_analysis}'
                )

                for rule in quantitative_rules:
                    rule_name = rule.Child_Item_Name or rule.Parent_Item_Name
                    if rule_name in rules_needing_comprehensive_analysis:
                        rule.needs_comprehensive_analysis = True
                        reason = reasons.get(rule_name, 'AI大模型判断需要综合计算')
                        self.logger.info(
                            f'标记规则 "{rule_name}" 需要综合计算: {reason}'
                        )
                        # 输出规则的详细信息
                        self.logger.info(
                            f'规则详细信息 - 名称: {rule_name}, 描述: {rule.description}, 满分: {rule.Child_max_score}, 是否价格规则: {rule.is_price_criteria}'
                        )
                    else:
                        rule.needs_comprehensive_analysis = False
                        self.logger.info(f'规则 "{rule_name}" 不需要综合计算')

                self.logger.info(
                    f'成功标记 {len(rules_needing_comprehensive_analysis)} 条规则需要综合计算'
                )
            else:
                self.logger.warning('AI大模型未返回有效的分类结果')

            # 5. 特殊处理：确保所有价格规则都被标记为需要综合分析
            price_rules = [
                rule for rule in quantitative_rules if rule.is_price_criteria
            ]
            for rule in price_rules:
                rule_name = rule.Child_Item_Name or rule.Parent_Item_Name
                if not rule.needs_comprehensive_analysis:
                    rule.needs_comprehensive_analysis = True
                    self.logger.info(f'强制标记价格规则 "{rule_name}" 需要综合计算')

        except Exception as e:
            self.logger.error(f'对定量规则进行智能分类时出错: {e}')

    def _filter_qualitative_rules(self, qualitative_rules: List[ScoringRule]):
        """
        对定性规则进行智能筛选，删除无效规则

        Args:
            qualitative_rules: 定性规则列表
        """
        try:
            self.logger.info(f'开始对 {len(qualitative_rules)} 条定性规则进行智能筛选')

            # 1. 构造发送给AI大模型的prompt
            rules_info = []
            for rule in qualitative_rules:
                rule_info = {
                    '规则名称': rule.Child_Item_Name or rule.Parent_Item_Name,
                    '规则描述': rule.description or '',
                    '是否否决项': rule.is_veto,
                }
                rules_info.append(rule_info)

            prompt = f"""你是一个专业的评标专家，请根据以下定性规则信息，筛选出有效的评分规则，识别并标记无效或不合适的规则：

【定性规则列表】
{json.dumps(rules_info, ensure_ascii=False, indent=2)}

【筛选标准】
有效的定性规则应该具有以下特征：
1. 有明确的评判标准和要求
2. 可以明确判断符合或不符合
3. 与评标内容相关

无效或不合适的规则通常具有以下特征：
1. 内容空洞，没有具体评判标准
2. 与评标内容无关
3. 表述模糊，无法明确判断
4. 重复或冗余的规则

【输出要求】
请返回一个JSON对象，包含以下字段：
1. "无效规则": 一个数组，包含无效或不合适的规则名称
2. "理由": 对每个无效规则给出判断理由

【重要】请严格按照以下JSON格式返回结果，不要返回任何解释文字：
{{
  "无效规则": ["规则名称1", "规则名称2"],
  "理由": {{
    "规则名称1": "判断理由1",
    "规则名称2": "判断理由2"
  }}
}}

示例：
{{
  "无效规则": ["无意义的规则", "重复的规则"],
  "理由": {{
    "无意义的规则": "内容空洞，没有具体评判标准",
    "重复的规则": "与前面的规则重复"
  }}
}}"""

            self.logger.info('构造AI prompt完成，开始调用AI大模型进行筛选')

            # 输出发送给AI大模型的prompt（略去标书的文本）
            self.logger.info(
                f'发送给AI大模型的prompt: {prompt[:500]}...'
            )  # 只显示前500个字符避免日志过长

            # 2. 调用AI大模型进行筛选
            ai_response = self.ai_analyzer.analyze_text(prompt)
            self.logger.info('AI大模型响应接收成功')

            # 3. 解析AI响应
            filtering_result = self._parse_filtering_response(ai_response)

            # 4. 删除无效规则
            if filtering_result and '无效规则' in filtering_result:
                invalid_rules = filtering_result['无效规则']
                reasons = filtering_result.get('理由', {})

                deleted_count = 0
                for rule in qualitative_rules:
                    rule_name = rule.Child_Item_Name or rule.Parent_Item_Name
                    if rule_name in invalid_rules:
                        self.logger.info(
                            f'删除无效规则 "{rule_name}": {reasons.get(rule_name, "AI大模型判断为无效规则")}'
                        )
                        if self.db:
                            self.db.delete(rule)
                        deleted_count += 1

                self.logger.info(f'成功删除 {deleted_count} 条无效规则')
            else:
                self.logger.warning('AI大模型未返回有效的筛选结果')

        except Exception as e:
            self.logger.error(f'对定性规则进行智能筛选时出错: {e}')

    def _parse_classification_response(self, response: str) -> Dict[str, Any]:
        """
        解析分类的AI响应

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 解析后的分类结果
        """
        try:
            import re
            import json

            # 尝试清理响应，移除可能的代码块标记
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
            return data
        except Exception as e:
            self.logger.error(f'解析分类AI响应时出错: {e}')
            return {}

    def _parse_filtering_response(self, response: str) -> Dict[str, Any]:
        """
        解析筛选的AI响应

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 解析后的筛选结果
        """
        try:
            import re
            import json

            # 尝试清理响应，移除可能的代码块标记
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
            return data
        except Exception as e:
            self.logger.error(f'解析筛选AI响应时出错: {e}')
            return {}
