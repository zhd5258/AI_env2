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
需要综合计算的规则必须同时满足以下条件：
1. 必须基于所有投标人的相对表现进行排名或比较的规则（如技术方案相对优劣排名）
2. 需要考虑全局数据进行相对评估的规则（如各投标人交付期的相对优势）
3. 需要进行横向比较确定优劣的规则（如性能指标相对排名）
4. 价格分规则（通常需要综合计算）

不需要综合计算的规则包括：
1. 只需要按统一标准判断是否符合的规则（如是否采用推荐品牌、是否满足能效标准等）
2. 只需要与招标文件要求对比的规则（如技术参数负偏离情况）
3. 只需要统计数量或满足程度的规则（如额外服务项数量、满足标准的项目数等）
4. 只需要绝对标准评分的规则（如单个项目的得分）

【具体示例】
需要综合计算的规则示例：
- "有同类型项目业绩"：需要根据所有投标人提供的项目业绩进行排名比较，第一名得5分，第二名得3分，第三名得1分
- "售后服务方案评分"：需要对所有投标人的售后服务方案进行横向比较排名
- "价格分"：需要基于所有投标人的报价计算相对得分

不需要综合计算的规则示例：
- "PLC、触摸屏、变频器采用推荐品牌"：只需要判断是否在推荐品牌列表内，不需要横向比较
- "采用节能环保方案"：只需要判断是否满足能效标准，不需要横向比较
- "为本项目提供的高于投标文件要求的服务"：只需要统计额外服务项数量，不需要横向比较
- "投标产品技术性能指标"：只需要与招标文件要求对比，不需要投标人之间比较

【常见误判情况说明】
以下规则经常被错误地判断为需要综合计算，请特别注意：
1. "为本项目提供的高于投标文件要求的服务"：虽然描述中提到"相对评估"，但实际上只是统计额外服务项数量，每个项目1分，属于绝对标准评分
2. "采用节能环保方案"：虽然描述中提到"横向比较"，但实际只需要判断是否满足能效等级和环保标准，属于统一标准判断
3. "PLC、触摸屏、变频器采用推荐品牌"：虽然描述中提到"统一比对"，但实际只需要判断是否在推荐范围内，属于统一标准判断
4. "投标产品技术性能指标"：虽然描述中提到"基于所有投标文件的对比"，但实际只需要和招标文件要求对比，属于标准对比

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
        import json
        import re

        # 初始化变量
        cleaned_response = ''

        try:
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
            # 1. 修复多余的逗号问题 - 移除对象或数组末尾的逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 2. 修复未闭合的字符串 - 确保所有引号都是成对出现的
            # 查找所有引号的位置
            quote_positions = [i for i, char in enumerate(json_str) if char == '"']
            if len(quote_positions) % 2 != 0:
                # 如果引号数量是奇数，尝试在末尾添加一个引号
                # 但要确保不是在转义字符后面添加
                if not json_str.endswith('\\'):
                    json_str = json_str.rstrip() + '"'

            # 3. 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f'JSON解析错误: {e}')
            self.logger.error(f'响应内容: {response}')
            self.logger.error(f'清理后的内容: {cleaned_response}')
            # 尝试更强大的修复方法
            return self._fix_broken_json(response)
        except Exception as e:
            self.logger.error(f'解析分类AI响应时出错: {e}')
            self.logger.error(f'响应内容: {response}')
            return {}

    def _fix_broken_json(self, response: str) -> Dict[str, Any]:
        """
        尝试修复损坏的JSON响应

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 修复后的结果
        """
        try:
            import re
            import json

            # 更强大的JSON修复方法
            # 1. 移除所有控制字符
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)

            # 2. 特殊处理：修复未闭合的字符串
            # 查找最后一个未闭合的字符串（以引号开始但没有结束的）
            # 从末尾开始查找，找到最后一个引号
            last_quote_pos = cleaned.rfind('"')
            if last_quote_pos != -1:
                # 检查这个引号后面是否有闭合的大括号
                after_quote = cleaned[last_quote_pos + 1 :].strip()
                if not after_quote.endswith('}') and not '}' in after_quote:
                    # 如果没有闭合的大括号，尝试添加
                    # 先添加缺失的引号（如果需要）
                    if cleaned.count('"') % 2 != 0:
                        cleaned = cleaned.rstrip() + '"'
                    # 然后添加缺失的大括号
                    cleaned = cleaned.rstrip() + '}'

            # 3. 尝试提取JSON对象
            # 查找第一个{和最后一个}的位置
            first_brace = cleaned.find('{')
            last_brace = cleaned.rfind('}')

            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_part = cleaned[first_brace : last_brace + 1]

                # 4. 修复常见的JSON问题
                # 修复未闭合的字符串 - 在行末添加缺失的引号和逗号
                lines = json_part.split('\n')
                fixed_lines = []
                for i, line in enumerate(lines):
                    # 如果一行以冒号结尾但没有闭合引号，尝试修复
                    if line.strip().endswith(':') and line.count('"') % 2 == 1:
                        # 查找该行中最后一个引号的位置
                        last_quote = line.rfind('"')
                        if last_quote != -1:
                            # 在最后一个引号后添加闭合引号
                            line = line[: last_quote + 1] + '"' + line[last_quote + 1 :]
                    # 如果一行有奇数个引号，尝试在行末添加引号
                    elif line.count('"') % 2 == 1 and not line.strip().endswith('\\'):
                        line = line.rstrip() + '"'
                    # 如果是最后一行且看起来像是未完成的对象，尝试闭合
                    elif (
                        i == len(lines) - 1
                        and line.strip()
                        and not line.strip().endswith('}')
                    ):
                        # 检查是否需要添加闭合括号
                        if '{' in line and not '}' in line:
                            line = line.rstrip() + '"}'
                    fixed_lines.append(line)

                json_part = '\n'.join(fixed_lines)

                # 5. 修复多余的逗号
                json_part = re.sub(r',(\s*[}\]])', r'\1', json_part)

                # 6. 确保对象正确闭合
                open_braces = json_part.count('{')
                close_braces = json_part.count('}')
                if open_braces > close_braces:
                    # 添加缺失的闭合大括号
                    json_part = json_part.rstrip() + '}' * (open_braces - close_braces)

                open_brackets = json_part.count('[')
                close_brackets = json_part.count(']')
                if open_brackets > close_brackets:
                    # 添加缺失的闭合方括号
                    json_part = json_part.rstrip() + ']' * (
                        open_brackets - close_brackets
                    )

                # 7. 特殊处理：确保所有字符串都正确闭合
                # 查找所有未闭合的字符串
                quote_count = json_part.count('"')
                if quote_count % 2 != 0:
                    # 查找最后一个引号
                    last_quote = json_part.rfind('"')
                    # 如果最后一个引号不在末尾，尝试在末尾添加引号
                    if last_quote < len(json_part) - 1:
                        json_part = json_part.rstrip() + '"'

                # 8. 尝试解析
                try:
                    result = json.loads(json_part)
                    self.logger.info('JSON修复成功')
                    return result
                except json.JSONDecodeError as e:
                    self.logger.error(f'修复后仍然无法解析JSON: {e}')
                    # 如果还是解析失败，尝试更激进的修复
                    # 移除所有可能造成问题的字符
                    json_part = re.sub(
                        r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', json_part
                    )
                    # 确保字符串正确闭合
                    json_part = re.sub(r'([^\\])"$', r'\1\"', json_part)
                    # 确保对象闭合
                    if not json_part.endswith('}'):
                        json_part = json_part.rstrip() + '}'
                    return json.loads(json_part)
            else:
                self.logger.error('无法从响应中提取有效的JSON对象')
                # 尝试直接修复原始响应
                return self._aggressive_json_fix(response)
        except Exception as e:
            self.logger.error(f'修复损坏的JSON时出错: {e}')
            return {}

    def _aggressive_json_fix(self, response: str) -> Dict[str, Any]:
        """
        激进的JSON修复方法

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 修复后的结果
        """
        try:
            import re
            import json

            # 1. 移除所有控制字符
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', response)

            # 2. 移除代码块标记
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.startswith('```'):
                cleaned = cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]

            # 3. 查找JSON对象的开始和结束
            first_brace = cleaned.find('{')
            if first_brace == -1:
                self.logger.error('响应中未找到JSON对象开始标记')
                return {}

            # 从第一个{开始处理
            json_content = cleaned[first_brace:]

            # 4. 确保字符串正确闭合
            quote_positions = [i for i, char in enumerate(json_content) if char == '"']
            if len(quote_positions) % 2 != 0:
                # 添加缺失的引号
                json_content = json_content.rstrip() + '"'

            # 5. 确保对象正确闭合
            open_braces = json_content.count('{')
            close_braces = json_content.count('}')
            if open_braces > close_braces:
                json_content = json_content.rstrip() + '}' * (
                    open_braces - close_braces
                )

            open_brackets = json_content.count('[')
            close_brackets = json_content.count(']')
            if open_brackets > close_brackets:
                json_content = json_content.rstrip() + ']' * (
                    open_brackets - close_brackets
                )

            # 6. 移除可能导致问题的尾部内容
            # 查找最后一个有效的JSON结束位置
            last_valid_end = max(json_content.rfind('}'), json_content.rfind(']'))
            if last_valid_end != -1:
                json_content = json_content[: last_valid_end + 1]

            # 7. 尝试解析
            return json.loads(json_content)
        except Exception as e:
            self.logger.error(f'激进JSON修复失败: {e}')
            return {}

    def _parse_filtering_response(self, response: str) -> Dict[str, Any]:
        """
        解析筛选的AI响应

        Args:
            response: AI响应

        Returns:
            Dict[str, Any]: 解析后的筛选结果
        """
        import json
        import re

        # 初始化变量
        cleaned_response = ''

        try:
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
            # 1. 修复多余的逗号问题 - 移除对象或数组末尾的逗号
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

            # 2. 修复未闭合的字符串 - 确保所有引号都是成对出现的
            # 查找所有引号的位置
            quote_positions = [i for i, char in enumerate(json_str) if char == '"']
            if len(quote_positions) % 2 != 0:
                # 如果引号数量是奇数，尝试在末尾添加一个引号
                # 但要确保不是在转义字符后面添加
                if not json_str.endswith('\\'):
                    json_str = json_str.rstrip() + '"'

            # 3. 移除控制字符
            json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

            # 尝试解析修复后的JSON
            data = json.loads(json_str)
            return data
        except json.JSONDecodeError as e:
            self.logger.error(f'JSON解析错误: {e}')
            self.logger.error(f'响应内容: {response}')
            self.logger.error(f'清理后的内容: {cleaned_response}')
            # 尝试更强大的修复方法
            return self._fix_broken_json(response)
        except Exception as e:
            self.logger.error(f'解析筛选AI响应时出错: {e}')
            self.logger.error(f'响应内容: {response}')
            return {}
