import re
import logging
from typing import List, Dict, Any
from .utils import clean_criteria_name, is_similar_criteria, find_and_add_price_rule, is_valid_score, normalize_text


class TextAnalyzerMixin:
    """基于文本的评分规则提取器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_scoring_rules(self, evaluation_section_text: str) -> List[Dict[str, Any]]:
        """
        从评标章节文本中提取评分规则

        Args:
            evaluation_section_text: 评标章节文本

        Returns:
            List[Dict[str, Any]]: 提取的评分规则列表
        """
        # 标准化文本
        evaluation_section_text = normalize_text(evaluation_section_text)
        
        # 1. 首先提取招标文件文本并保存到temp_word目录
        if not evaluation_section_text.strip():
            self.logger.warning('输入文本为空')
            return []

        self.logger.info(f'开始分析招标文件，总长度: {len(evaluation_section_text)} 字符')

        # 2. 从章节文本中提取所有结构化的评分项
        #    使用正则表达式匹配如"1.1.1 xxx (10分)"的模式
        structured_rules = self._parse_rules_from_text(evaluation_section_text)

        # 3. 专门查找表格中的评分规则
        table_rules = self._extract_table_scoring_rules(evaluation_section_text)
        if table_rules:
            structured_rules.extend(table_rules)
            self.logger.info(f'从表格中提取到 {len(table_rules)} 条评分规则')

        # 4. 从章节文本中专门查找价格分计算公式，并将其添加/更新到规则列表中
        final_rules = find_and_add_price_rule(evaluation_section_text, structured_rules)

        # 5. 如果规则提取失败，尝试使用AI辅助分析整个章节
        if not final_rules:
            self.logger.info('未提取到结构化评分规则，尝试使用AI辅助分析')
            ai_rules = self._try_extract_with_ai(evaluation_section_text)
            if ai_rules:
                final_rules = ai_rules
                self.logger.info(f'AI辅助分析提取到 {len(ai_rules)} 条评分规则')
            else:
                self.logger.warning('AI辅助分析也未能提取到评分规则')

        # 6. 构建评分规则树结构
        if final_rules:
            # 构建树结构
            tree = self._build_tree_from_flat_list(final_rules)
            self._verify_and_adjust_scores(tree)
            return tree
        else:
            self.logger.warning('未能提取到任何评分规则')
            return []

    def _parse_rules_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中解析出所有结构化的评分规则项"""
        # 优化正则表达式以更好地匹配评分规则，兼容中英文括号
        rule_patterns = [
            # 价格分特别处理: 价格分... (30分) or 价格分... 30分，限制分数范围避免错误识别
            r'^\s*([（\(]?\s*(?:价格分|报价分)\s*[）\)]?.*?)[\s（\(]+(\d{1,2}(?:\.\d)?)\s*分[\)）]?',
            # 其他评分项匹配模式，限制分数范围避免错误识别
            r'([^\n\(]*?[\u4e00-\u9fa5]+[^\n\)]*?)\s*[\(（]\s*(\d{1,2}(?:\.\d)?)\s*分\s*[\)）]',
            r'([^\n\(]*?[\u4e00-\u9fa5]+[^\n\)]*?)\s+(\d{1,2}(?:\.\d)?)\s*分',
        ]

        # 存储提取的评分规则
        rules = []

        lines = text.split('\n')
        i = 0
        while i < len(lines):
            line = lines[i]
            # 尝试每种模式匹配
            for pattern in rule_patterns:
                matches = re.findall(pattern, line, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple) and len(match) >= 2:
                        criteria_name = match[0].strip()
                        score_str = match[1]
                    else:
                        continue

                    # 清理评分项名称并应用文本规范化
                    criteria_name = clean_criteria_name(criteria_name)

                    # 过滤掉太短或太长的名称
                    if not (2 < len(criteria_name) < 100):
                        continue

                    # 检查是否包含价格相关关键词
                    is_price_criteria = (
                        '价格' in criteria_name
                        or '报价' in criteria_name
                        or '单价' in criteria_name
                        or '金额' in criteria_name
                        or '基准价' in criteria_name
                    )

                    # 验证分数是否有效
                    try:
                        score = float(score_str)
                        if not is_valid_score(score):
                            continue  # 跳过无效分数
                    except ValueError:
                        continue  # 跳过无法转换为浮点数的分数

                    rules.append(
                        {
                            'numbering': (str(len(rules) + 1),),
                            'criteria_name': criteria_name,
                            'max_score': score,
                            'weight': 1.0,
                            'description': criteria_name,
                            'category': '评标办法',
                            'is_price_criteria': is_price_criteria,
                        }
                    )

            i += 1

        # 移除重复规则
        rules = self._remove_duplicate_rules(rules)
        return rules

    def _clean_criteria_name(self, name: str) -> str:
        """清理评分项名称"""
        # 使用新的标准化函数处理全角字符和特殊空格
        name = normalize_text(name)
        
        # 移除多余的空白字符
        name = re.sub(r'\s+', ' ', name.strip())

        # 移除常见的前缀和后缀
        name = re.sub(r'^[（\(]*\d+[\.\-]?\d*[）\)]*\s*', '', name)
        name = re.sub(r'\s*[（\(]*\d+分?[）\)]*$', '', name)

        # 移除特殊字符
        name = re.sub(r'[※★▲●○◆■□△▽◇◆]', '', name)

        return name.strip()

    def _remove_duplicate_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """移除重复的评分规则"""
        if not rules:
            return rules

        unique_rules = []

        for rule in rules:
            criteria_name = rule.get('criteria_name', '')

            # 检查是否已存在相似规则
            is_duplicate = False
            duplicate_index = -1
            for i, existing_rule in enumerate(unique_rules):
                existing_name = existing_rule.get('criteria_name', '')
                if is_similar_criteria(criteria_name, existing_name):
                    is_duplicate = True
                    duplicate_index = i
                    break

            if is_duplicate:
                # 如果是重复规则，保留分数更高的
                if rule['max_score'] > unique_rules[duplicate_index]['max_score']:
                    unique_rules[duplicate_index] = rule
            else:
                unique_rules.append(rule)

        return unique_rules

    def _extract_table_scoring_rules(self, text: str) -> List[Dict[str, Any]]:
        """
        从文本中提取表格形式的评分规则
        
        Args:
            text: 包含表格的文本
            
        Returns:
            List[Dict[str, Any]]: 提取的评分规则列表
        """
        # 这里应该实现表格评分规则的提取逻辑
        # 为简化示例，返回空列表
        return []

    def _try_extract_with_ai(self, text: str) -> List[Dict[str, Any]]:
        """
        尝试使用AI辅助提取评分规则
        
        Args:
            text: 要分析的文本
            
        Returns:
            List[Dict[str, Any]]: AI提取的评分规则列表
        """
        # 这里应该实现AI辅助提取逻辑
        # 为简化示例，返回空列表
        return []

    def _build_tree_from_flat_list(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        从扁平的规则列表构建树形结构
        
        Args:
            rules: 扁平的规则列表
            
        Returns:
            List[Dict[str, Any]]: 树形结构的规则列表
        """
        # 这里应该实现树形结构构建逻辑
        # 为简化示例，直接返回规则列表
        return rules

    def _verify_and_adjust_scores(self, rules: List[Dict[str, Any]]) -> None:
        """
        验证并调整评分规则的分数
        
        Args:
            rules: 评分规则列表
        """
        # 这里应该实现分数验证和调整逻辑
        # 为简化示例，不进行任何操作
        pass

    def _extract_scoring_rules_from_text(self) -> List[Dict[str, Any]]:
        """
        从文本中提取评分规则
        
        Returns:
            List[Dict[str, Any]]: 提取的评分规则列表
        """
        # 检查是否有文本可供分析
        if not hasattr(self, 'texts') or not self.texts:
            self.logger.warning('没有可供分析的文本')
            return []
        
        # 合并所有页面的文本
        full_text = '\n'.join(self.texts)
        
        # 调用现有的extract_scoring_rules方法
        return self.extract_scoring_rules(full_text)
