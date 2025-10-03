import re
import logging
import json
from typing import List, Dict, Any


class AIAnalyzerMixin:
    """AI分析混入类，提供AI辅助评分规则提取功能"""
    
    def _ai_analyze_scoring_rules(
        self, scoring_section: str, extracted_rules: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """使用AI辅助分析评分规则，确保总分不超过100分"""
        try:
            # 构建AI分析提示词
            prompt = f"""
请分析以下招标文件中的评分规则，并返回正确的评分规则结构。

招标文件内容：
{scoring_section}

当前提取的评分规则：
{json.dumps(extracted_rules, ensure_ascii=False, indent=2)}

请仔细分析并返回正确的评分规则，要求：
1. 总分必须等于100分
2. 保持规则的层级结构
3. 确保父项分数等于子项分数之和
4. 如果发现重复或错误的规则，请修正
5. 对于价格分规则，请保留"is_price_rule": true标记
6. 只返回JSON格式的评分规则，不要包含其他内容

返回格式示例：
[
  {{
    "criteria_name": "技术方案",
    "max_score": 60,
    "weight": 1.0,
    "children": [
      {{
        "criteria_name": "技术方案完整性",
        "max_score": 30,
        "weight": 1.0,
        "children": []
      }},
      {{
        "criteria_name": "技术方案可行性",
        "max_score": 30,
        "weight": 1.0,
        "children": []
      }}
    ]
  }},
  {{
    "criteria_name": "商务报价",
    "max_score": 40,
    "weight": 1.0,
    "children": []
  }}
]
"""

            # 调用AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            if ai_response and not ai_response.startswith('Error:'):
                try:
                    # 尝试从AI响应中提取JSON
                    json_match = re.search(r'\[.*\]', ai_response, re.DOTALL)
                    if json_match:
                        ai_rules = json.loads(json_match.group())

                        # 验证AI返回的规则
                        total_score = sum(rule['max_score'] for rule in ai_rules)
                        if abs(total_score - 100.0) < 0.1:  # 允许小的浮点数误差
                            self.logger.info('AI分析完成，总分: %s', total_score)
                            return ai_rules
                        else:
                            self.logger.warning(
                                'AI返回的规则总分不正确: %s，使用原始规则', total_score
                            )
                    else:
                        self.logger.warning(
                            'AI响应中未找到有效的JSON格式，使用原始规则'
                        )
                except json.JSONDecodeError as e:
                    self.logger.warning('AI响应JSON解析失败: %s，使用原始规则', e)
            else:
                self.logger.warning('AI分析失败: %s，使用原始规则', ai_response)

        except Exception as e:
            self.logger.error('AI分析过程中发生错误: %s，使用原始规则', e)

        # 如果AI分析失败，返回原始规则
        return extracted_rules

    def _ai_extract_rules(self, text: str) -> List[Dict[str, Any]]:
        """使用AI辅助从文本中提取评分规则"""
        try:
            # 如果文本太长，进行截取以避免超出AI模型的处理能力
            max_length = 15000  # 限制在15000字符以内
            if len(text) > max_length:
                self.logger.info(
                    f'文本长度 {len(text)} 超过限制，截取前 {max_length} 个字符'
                )
                text = text[:max_length]

            # 构建AI分析提示词 - 增强提示词以更好地处理各种格式
            prompt = f"""
你是一个专业的招投标评标专家，请从以下招标文件内容中提取评分规则，并以指定的JSON格式返回。

招标文件内容：
{text}

请仔细分析并返回评分规则，要求：
1. 总分必须等于100分
2. 保持规则的层级结构
3. 确保父项分数等于子项分数之和
4. 正确识别价格分规则并标记"is_price_criteria": true
5. 只返回JSON格式的评分规则，不要包含其他内容
6. 如果内容中包含表格形式的评分标准，请特别注意提取
7. 注意识别"评价项目"、"评价内容"、"评分标准"、"评标办法"等标题下的内容
8. 价格分通常包含"价格"、"报价"、"基准价"等关键词
9. 请分析整个文档内容，不要只关注某一部分
10. 如果找不到明确的评分规则，请根据文档内容推断合理的评分标准

返回格式示例：
[
  {{
    "numbering": ["1"],
    "criteria_name": "技术方案",
    "max_score": 60,
    "weight": 1.0,
    "description": "技术方案评分",
    "category": "评标办法",
    "children": [
      {{
        "numbering": ["1", "1"],
        "criteria_name": "技术方案完整性",
        "max_score": 30,
        "weight": 1.0,
        "description": "技术方案完整性评分",
        "category": "评标办法",
        "children": [],
        "is_price_criteria": false
      }},
      {{
        "numbering": ["1", "2"],
        "criteria_name": "技术方案可行性",
        "max_score": 30,
        "weight": 1.0,
        "description": "技术方案可行性评分",
        "category": "评标办法",
        "children": [],
        "is_price_criteria": false
      }}
    ],
    "is_price_criteria": false
  }},
  {{
    "numbering": ["2"],
    "criteria_name": "价格分",
    "max_score": 40,
    "weight": 1.0,
    "description": "价格分计算公式...",
    "category": "评标办法",
    "children": [],
    "is_price_criteria": true
  }}
]
"""

            # 调用AI分析
            ai_response = self.ai_analyzer.analyze_text(prompt)

            # 解析AI响应
            if ai_response and not ai_response.startswith('Error:'):
                try:
                    # 尝试从AI响应中提取JSON
                    # 更宽松的JSON提取，处理可能的格式问题
                    json_match = re.search(r'\[[\s\S]*\]', ai_response, re.DOTALL)
                    if not json_match:
                        # 如果没有找到方括号，尝试查找大括号包围的对象数组
                        json_match = re.search(r'\{{[\s\S]*\}}', ai_response, re.DOTALL)

                    if json_match:
                        json_str = json_match.group()
                        # 清理JSON字符串，移除可能的注释和多余内容
                        json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
                        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

                        ai_rules = json.loads(json_str)

                        # 验证AI返回的规则
                        if isinstance(ai_rules, list) and len(ai_rules) > 0:
                            total_score = sum(
                                rule.get('max_score', 0) for rule in ai_rules
                            )
                            if abs(total_score - 100.0) < 10.0:  # 放宽到10分的误差
                                self.logger.info(
                                    f'AI辅助提取完成，提取到 {len(ai_rules)} 条规则，总分: {total_score}'
                                )
                                return ai_rules
                            else:
                                self.logger.warning(
                                    f'AI返回的规则总分不正确: {total_score}，使用默认规则'
                                )
                        else:
                            self.logger.warning(
                                'AI响应中未找到有效的规则列表，使用默认规则'
                            )
                    else:
                        self.logger.warning(
                            'AI响应中未找到有效的JSON格式，使用默认规则'
                        )
                        # 尝试直接解析整个响应
                        try:
                            ai_rules = json.loads(ai_response)
                            if isinstance(ai_rules, list) and len(ai_rules) > 0:
                                self.logger.info(
                                    f'直接解析AI响应成功，提取到 {len(ai_rules)} 条规则'
                                )
                                return ai_rules
                        except json.JSONDecodeError:
                            pass
                except json.JSONDecodeError as e:
                    self.logger.warning(f'AI响应JSON解析失败: {e}，使用默认规则')
                    self.logger.debug(f'AI响应内容: {ai_response}')
            else:
                self.logger.warning(f'AI分析失败: {ai_response}，使用默认规则')

        except Exception as e:
            self.logger.error(f'AI分析过程中发生错误: {e}', exc_info=True)

        # 如果AI分析失败，返回默认规则
        return self._get_default_scoring_rules()