"""
评分规则解析模块
集中处理评分规则的解析逻辑，避免重复实现
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from modules.local_ai_analyzer import LocalAIAnalyzer
from .utils import normalize_text, clean_criteria_name


class ScoringRuleParser:
    """评分规则解析器"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # 不再需要AI分析器
        # self.ai_analyzer = LocalAIAnalyzer()

    def parse_scoring_rules_from_table_data(
        self, structured_tables: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        从结构化表格数据中解析评分规则

        Args:
            structured_tables: 结构化表格数据列表

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        scoring_rules = []

        for table in structured_tables:
            headers = table.get('headers', [])
            rows = table.get('rows', [])

            # 检查是否为评分规则表格（包含评价项目和评价标准）
            if '评价项目' in headers and '评价标准' in headers:
                # 解析评分规则
                rules = self._extract_rules_from_scoring_table(headers, rows)
                scoring_rules.extend(rules)

        # 对评分规则进行后处理，特别是对价格规则进行特殊处理
        processed_rules = self._post_process_rules(scoring_rules)

        return processed_rules

    def _extract_rules_from_scoring_table(
        self, headers: List[str], rows: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        从评分表格中提取规则

        Args:
            headers: 表头列表
            rows: 行数据列表

        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        rules = []
        # 找到评价项目和评价标准列的索引
        project_col_index = None
        detail_col_index = None  # 第二列（明细项）
        standard_col_index = None
        score_col_index = None

        for i, header in enumerate(headers):
            # 标准化表头文本
            normalized_header = normalize_text(header)
            if '评价项目' in normalized_header:
                project_col_index = i
            elif i == 1:  # 第二列通常是明细项
                detail_col_index = i
            elif '评价标准' in normalized_header:
                standard_col_index = i
            elif '分值' in normalized_header or '分数' in normalized_header or '得分' in normalized_header:
                score_col_index = i

        # 如果没有找到评价标准列，尝试查找包含"标准"的列
        if standard_col_index is None:
            for i, header in enumerate(headers):
                normalized_header = normalize_text(header)
                if '标准' in normalized_header:
                    standard_col_index = i
                    break

        if project_col_index is None:
            self.logger.warning('未找到评价项目列')
            return rules

        # 用于追踪当前父项信息
        current_parent_name = ''
        current_parent_score = 0.0
        numbering_counter = 1

        # 处理每一行数据
        for row in rows:
            row_values = list(row.values())
            
            # 获取各列的值并标准化
            project_value = normalize_text(row_values[project_col_index]) if project_col_index < len(row_values) else ''
            detail_value = normalize_text(row_values[detail_col_index]) if detail_col_index is not None and detail_col_index < len(row_values) else ''
            standard_value = normalize_text(row_values[standard_col_index]) if standard_col_index is not None and standard_col_index < len(row_values) else ''
            score_value = normalize_text(row_values[score_col_index]) if score_col_index is not None and score_col_index < len(row_values) else ''

            # 清理数据并应用文本规范化
            project_value = self._clean_text(project_value)
            detail_value = self._clean_text(detail_value)
            standard_value = self._clean_text(standard_value)
            score_value = self._clean_text(score_value)

            # 判断是父项还是子项
            is_parent_item = bool(project_value)  # 如果评价项目列有值，则为父项

            if is_parent_item:
                # 这是父项（大项）
                current_parent_name = project_value
                current_parent_score = self._extract_score_from_text(project_value)

                # 检查是否为价格评分规则
                is_price_criteria = self._is_price_criteria(
                    project_value, standard_value
                )

                # 特别处理价格评分规则，直接从文本中提取公式而不是使用AI
                price_formula = None
                if is_price_criteria:
                    # 对于价格规则，我们需要从整行数据中提取完整的价格评价规则
                    price_evaluation_rule = (
                        self._extract_full_price_evaluation_rule(row_values)
                    )
                    price_formula = self._extract_formula_from_text(
                        price_evaluation_rule
                    )

                # 创建评分规则（父项）
                rule = {
                    'criteria_name': project_value,
                    'max_score': current_parent_score,
                    'description': standard_value
                    if not detail_value
                    else '',  # 父项通常没有详细描述
                    'is_price_criteria': is_price_criteria,
                    'price_formula': price_formula,
                    'numbering': [numbering_counter],
                }
                numbering_counter += 1
                rules.append(rule)

                # 如果有明细项，也创建子项（但价格规则除外）
                if detail_value and not is_price_criteria:
                    detail_score = self._extract_score_from_text(detail_value)
                    is_detail_price_criteria = self._is_price_criteria(
                        detail_value, standard_value
                    )

                    child_rule = {
                        'criteria_name': detail_value,
                        'max_score': detail_score,
                        'description': standard_value,
                        'is_price_criteria': is_detail_price_criteria,
                        'price_formula': price_formula if is_detail_price_criteria else None,
                        'numbering': [numbering_counter, 1],  # 子项编号
                    }
                    rules.append(child_rule)
                    numbering_counter += 1
            else:
                # 这是子项（明细项）
                if detail_value:
                    detail_score = self._extract_score_from_text(detail_value)
                    is_detail_price_criteria = self._is_price_criteria(
                        detail_value, standard_value
                    )

                    child_rule = {
                        'criteria_name': detail_value,
                        'max_score': detail_score,
                        'description': standard_value,
                        'is_price_criteria': is_detail_price_criteria,
                        'price_formula': None,
                        'numbering': [numbering_counter],  # 子项编号
                    }
                    rules.append(child_rule)
                    numbering_counter += 1

        return rules

    def _post_process_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        对评分规则进行后处理

        Args:
            rules: 原始评分规则列表

        Returns:
            List[Dict[str, Any]]: 处理后的评分规则列表
        """
        if not rules:
            return rules

        # 处理最后一个规则（价格规则）
        if rules and rules[-1].get('is_price_criteria', False):
            price_rule = rules[-1]
            # 如果价格规则有子项，则进行特殊处理
            if price_rule.get('children', []):
                children = price_rule['children']
                # 取第一个子项的信息
                if children:
                    first_child = children[0]
                    # 将子项的名称赋值给父项的描述
                    price_rule['description'] = first_child.get('criteria_name', '')
                    # 清空子项列表
                    price_rule['children'] = []

        return rules

    def _extract_full_price_evaluation_rule(self, row_values: List[str]) -> str:
        """
        从表格行的所有单元格中提取完整的价格评价规则
        根据项目需求，需要从存储评标规则的表格中的最后一行的全部单元格的内容合成一个完整的价格评价规则

        Args:
            row_values: 表格行的所有单元格值

        Returns:
            str: 完整的价格评价规则
        """
        # 将所有单元格的内容连接起来形成完整的价格评价规则
        full_rule = ' '.join(
            [str(value).strip() for value in row_values if value and str(value).strip()]
        )
        self.logger.info(f'提取到完整的价格评价规则: {full_rule}')
        return full_rule

    def _extract_formula_from_text(self, text: str) -> str:
        """
        从文本中提取价格计算公式，不再使用AI大模型

        Args:
            text: 包含价格计算公式的文本

        Returns:
            str: 提取到的价格计算公式
        """
        if not text:
            return ''

        # 首先尝试提取"价格计算公式:"后的内容
        if '价格计算公式:' in text:
            parts = text.split('价格计算公式:', 1)  # 只分割一次
            if len(parts) > 1:
                formula = parts[1].strip()
                # 如果公式中包含换行符，只取第一行
                if '\n' in formula:
                    formula = formula.split('\n', 1)[0]
                return formula

        # 如果没有找到特定格式，尝试提取包含数学符号的内容作为公式
        possible_formulas = []
        formula_patterns = [
            r'投标报价得分\s*[:：]?\s*[=＝][^;\n]*',
            r'价格分\s*[:：]?\s*[=＝][^;\n]*',
            r'得分\s*[:：]?\s*[=＝][^;\n]*',
            r'评标基准价\s*[:：]?\s*[=＝][^;\n]*',
            r'[评标基准价投标报价价格分得分][\s\S]*?[=＝][\s\S]*?',
        ]

        for pattern in formula_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                possible_formulas.append(match.group(0))

        # 返回最可能的公式，否则返回前200个字符
        return possible_formulas[0] if possible_formulas else text[:200]

    def _extract_score_from_text(self, text: str) -> float:
        """
        从文本中提取分数值

        Args:
            text: 包含分数的文本

        Returns:
            float: 提取到的分数值
        """
        if not text:
            return 0.0

        # 匹配分数模式，如：(20分)、（20分）、20分、满分20分等
        patterns = [
            r'[（(]([\d\.]+)分[)）]',
            r'满分([\d\.]+)分',
            r'标准分([\d\.]+)分',
            r'([\d\.]+)分',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue

        return 0.0

    def _is_price_criteria(self, project_value: str, standard_value: str) -> bool:
        """
        判断是否为价格评分标准

        Args:
            project_value: 项目名称
            standard_value: 标准描述

        Returns:
            bool: 是否为价格评分标准
        """
        price_keywords = ['价格', '报价', '投标报价', '评标价', '评标基准价']
        text_to_check = (project_value + ' ' + standard_value).lower()
        return any(keyword in text_to_check for keyword in price_keywords)

    def _clean_text(self, text: str) -> str:
        """
        清理文本，移除多余空格和特殊字符

        Args:
            text: 要清理的文本

        Returns:
            str: 清理后的文本
        """
        if not text:
            return ''

        # 使用新的标准化函数处理全角字符和特殊空格
        text = normalize_text(text)
        
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text.strip())

        # 移除常见的前缀和后缀
        text = re.sub(r'^[（\(]*\d+[\.\-]?\d*[）\)]*\s*', '', text)
        text = re.sub(r'\s*[（\(]*\d+分?[）\)]*$', '', text)

        # 移除特殊字符
        text = re.sub(r'[※★▲●○◆■□△▽◇◆]', '', text)

        return text.strip()
