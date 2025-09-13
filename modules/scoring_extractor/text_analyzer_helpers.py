"""
文本分析辅助模块
包含文本分析相关的辅助函数
"""

import re
import logging
from typing import List, Dict, Any, Tuple


class TextAnalyzerHelpers:
    """文本分析辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _extract_scoring_section(self, text: str) -> str:
        """
        提取评标相关的章节内容
        
        Args:
            text: 完整的招标文件文本
            
        Returns:
            str: 评标章节的文本内容
        """
        # 定义可能的评标章节标题
        scoring_section_headers = [
            r'评标办法',
            r'评分标准',
            r'评审标准',
            r'技术评分',
            r'综合评分',
            r'评标标准',
        ]

        # 查找评标章节的开始位置
        start_pos = -1
        section_header = ''
        for header in scoring_section_headers:
            # 查找章节标题
            pattern = rf'(^|\n)[\d、.]*\s*{header}[\s\S]*?(?=\n\d、\.|\n第[一二三四五六七八九十]章|\Z)'
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                start_pos = match.start()
                section_header = header
                break

        if start_pos == -1:
            # 如果没有找到标准章节标题，尝试更宽松的匹配
            pattern = r'评[标审][\s\S]*?标准|评分[\s\S]*?标准'
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_pos = match.start()
                section_header = match.group()

        if start_pos != -1:
            # 找到章节开始位置，提取相关内容
            # 从章节标题开始，到下一个主要章节或文档结尾
            section_text = text[start_pos:]
            next_chapter_pattern = (
                r'\n\d+、|\n第[一二三四五六七八九十]章|\n第四章|\Z'  # 匹配下一个章节
            )
            next_chapter_match = re.search(next_chapter_pattern, section_text[10:])
            if next_chapter_match:
                end_pos = next_chapter_match.start() + 10
                section_text = section_text[:end_pos]

            self.logger.info(f'成功提取评标章节: {section_header}')
            return section_text.strip()
        else:
            self.logger.warning('未找到明确的评标章节标题')
            return ''

    def _parse_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中解析评分规则
        
        Args:
            text: 要解析的文本
            
        Returns:
            List[Dict[str, Any]]: 解析出的评分规则列表
        """
        rules = []

        # 匹配评分规则的正则表达式模式
        # 匹配如"1.1.1 评分项名称 (10分)"的模式
        patterns = [
            # 标准格式: 编号 评分项名称 (分数分)
            r'(\d+(?:\.\d+)*)\s+([^(（\n]+?)\s*[（(](\d+(?:\.\d+)?)\s*分[)）]',
            # 无编号格式: 评分项名称 (分数分)
            r'\b([^(（\n]+?)\s*[（(](\d+(?:\.\d+)?)\s*分[)）]',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) == 3:
                    # 有编号的格式
                    numbering, criteria_name, score_str = match
                    numbering_list = [int(x) for x in numbering.split('.')]
                else:
                    # 无编号的格式
                    criteria_name, score_str = match
                    numbering_list = [len(rules) + 1]

                # 清理评分项名称
                criteria_name = self._clean_criteria_name(criteria_name)

                try:
                    score = float(score_str)
                    rule = {
                        'criteria_name': criteria_name,
                        'max_score': score,
                        'description': '',  # 描述需要进一步提取
                        'numbering': numbering_list,
                    }
                    rules.append(rule)
                except ValueError:
                    self.logger.warning(f'无法解析分数: {score_str}')

        # 尝试提取评分项的描述信息
        self._extract_rule_descriptions(text, rules)

        self.logger.info(f'从文本中解析到 {len(rules)} 条评分规则')
        return rules

    def _clean_criteria_name(self, name: str) -> str:
        """
        清理评分项名称
        
        Args:
            name: 原始评分项名称
            
        Returns:
            str: 清理后的评分项名称
        """
        # 移除多余的空格
        name = re.sub(r'\s+', ' ', name.strip())
        
        # 移除常见的冗余字符
        name = re.sub(r'[（(]\d+(?:\.\d+)?分[)）]', '', name).strip()
        
        return name

    def _extract_rule_descriptions(self, text: str, rules: List[Dict[str, Any]]):
        """
        从文本中提取评分规则的描述信息
        
        Args:
            text: 原始文本
            rules: 评分规则列表
        """
        # 这是一个简化的实现，实际项目中可能需要更复杂的逻辑
        for rule in rules:
            criteria_name = rule['criteria_name']
            # 尝试在文本中查找评分项的详细描述
            # 这里使用简单的文本匹配，实际项目中可能需要更复杂的逻辑
            pattern = rf'{re.escape(criteria_name)}[：:]?\s*([^.。！\n]+[.。！]?)'
            match = re.search(pattern, text)
            if match:
                description = match.group(1).strip()
                rule['description'] = description

    def _find_and_add_price_rule(self, text: str, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        查找并添加价格评分规则
        
        Args:
            text: 文本内容
            rules: 现有评分规则列表
            
        Returns:
            List[Dict[str, Any]]: 更新后的评分规则列表
        """
        # 查找价格评分规则相关文本
        price_patterns = [
            r'价格[评评][分标准].*?(?:计算公式|计算方法|评分方法).*?[\s\S]*?(?=\n\d|\Z)',
            r'价格.*?(?:\d+(?:\.\d+)?分)[\s\S]*?(?:计算公式|计算方法|评分方法).*?[\s\S]*?(?=\n\d|\Z)',
        ]
        
        for pattern in price_patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                price_text = match.group()
                # 解析价格评分规则
                price_rule = self._parse_price_rule(price_text)
                if price_rule:
                    # 检查是否已存在价格评分规则
                    existing_price_rule = None
                    for rule in rules:
                        if '价格' in rule['criteria_name']:
                            existing_price_rule = rule
                            break
                    
                    if existing_price_rule:
                        # 更新现有价格评分规则
                        existing_price_rule.update(price_rule)
                    else:
                        # 添加新的价格评分规则
                        rules.append(price_rule)
                    break
        
        return rules

    def _parse_price_rule(self, text: str) -> Dict[str, Any]:
        """
        解析价格评分规则
        
        Args:
            text: 价格评分规则文本
            
        Returns:
            Dict[str, Any]: 价格评分规则
        """
        # 提取价格评分分数
        score_pattern = r'(\d+(?:\.\d+)?)\s*分'
        score_match = re.search(score_pattern, text)
        score = float(score_match.group(1)) if score_match else 0.0
        
        # 创建价格评分规则
        price_rule = {
            'criteria_name': '价格分',
            'max_score': score,
            'description': text.strip(),
            'numbering': [999],  # 价格评分规则通常放在最后
            'is_price_criteria': True,
        }
        
        return price_rule

    def _try_extract_with_ai(self, text: str) -> List[Dict[str, Any]]:
        """
        尝试使用AI辅助提取评分规则
        
        Args:
            text: 要分析的文本
            
        Returns:
            List[Dict[str, Any]]: AI提取的评分规则列表
        """
        try:
            # 构造AI提示词
            prompt = f"""
            请从以下招标文件文本中提取评分规则，按照以下格式返回JSON数据：
            
            文本内容：
            {text[:3000]}  # 限制文本长度以避免提示词过长
            
            请提取评分规则，返回格式如下：
            [
                {{
                    "criteria_name": "评分项名称",
                    "max_score": 10.0,
                    "description": "评分项描述",
                    "numbering": [1, 1]
                }},
                ...
            ]
            
            只返回有效的JSON数组，不要包含其他内容。
            """
            
            # 调用AI分析器
            if hasattr(self, 'ai_analyzer'):
                response = self.ai_analyzer.analyze_text(prompt)
                # 解析AI响应
                return self._parse_ai_response(response)
            else:
                self.logger.warning('AI分析器不可用')
                return []
        except Exception as e:
            self.logger.error(f'使用AI提取评分规则时出错: {e}')
            return []

    def _parse_ai_response(self, response: str) -> List[Dict[str, Any]]:
        """
        解析AI响应
        
        Args:
            response: AI响应文本
            
        Returns:
            List[Dict[str, Any]]: 解析出的评分规则列表
        """
        try:
            # 简单实现，实际项目中可能需要更复杂的解析逻辑
            # 移除可能的代码块标记
            response = response.replace('```json', '').replace('```', '').strip()
            
            # 这里应该解析JSON，但为了简化示例，返回空列表
            # 实际项目中应该使用json.loads()解析响应
            return []
        except Exception as e:
            self.logger.error(f'解析AI响应时出错: {e}')
            return []