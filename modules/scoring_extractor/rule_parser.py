"""
评分规则解析模块
集中处理评分规则的解析逻辑，避免重复实现
"""

import re
import logging
from typing import List, Dict, Any, Tuple


class ScoringRuleParser:
    """评分规则解析器"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def parse_scoring_rules_from_table_data(self, structured_tables: List[Dict]) -> List[Dict[str, Any]]:
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
            if "评价项目" in headers and "评价标准" in headers:
                # 解析评分规则
                rules = self._extract_rules_from_scoring_table(headers, rows)
                scoring_rules.extend(rules)
        
        # 对评分规则进行后处理，特别是对价格规则进行特殊处理
        processed_rules = self._post_process_rules(scoring_rules)
        
        return processed_rules
    
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
    
    def _extract_rules_from_scoring_table(self, headers: List[str], rows: List[Dict]) -> List[Dict[str, Any]]:
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
            if "评价项目" in header:
                project_col_index = i
            elif i == 1:  # 第二列通常是明细项
                detail_col_index = i
            elif "评价标准" in header:
                standard_col_index = i
            elif "分值" in header or "分数" in header or "得分" in header:
                score_col_index = i
        
        # 如果没有找到评价标准列，尝试查找包含"标准"的列
        if standard_col_index is None:
            for i, header in enumerate(headers):
                if "标准" in header:
                    standard_col_index = i
                    break
        
        if project_col_index is None:
            self.logger.warning("未找到评价项目列")
            return rules
            
        # 用于追踪当前父项信息
        current_parent_name = ""
        current_parent_score = 0.0
        numbering_counter = 1
            
        # 解析每一行
        for row_idx, row in enumerate(rows):
            try:
                # 获取行数据
                row_values = list(row.values())
                if len(row_values) <= project_col_index:
                    continue
                    
                project_value = row_values[project_col_index] if project_col_index < len(row_values) else ""
                detail_value = row_values[detail_col_index] if detail_col_index is not None and detail_col_index < len(row_values) else ""
                standard_value = row_values[standard_col_index] if standard_col_index is not None and standard_col_index < len(row_values) else ""
                score_value = row_values[score_col_index] if score_col_index is not None and score_col_index < len(row_values) else ""
                
                # 清理数据
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
                    is_price_criteria = self._is_price_criteria(project_value, standard_value)
                    
                    # 特别处理价格评分规则
                    price_formula = None
                    if is_price_criteria:
                        price_formula = self._extract_price_formula(standard_value)
                    
                    # 创建评分规则（父项）
                    rule = {
                        "criteria_name": project_value,
                        "max_score": current_parent_score,
                        "description": standard_value if not detail_value else "",  # 父项通常没有详细描述
                        "is_price_criteria": is_price_criteria,
                        "price_formula": price_formula,
                        "numbering": [numbering_counter]
                    }
                    numbering_counter += 1
                    rules.append(rule)
                    
                    # 如果有明细项，也创建子项（但价格规则除外）
                    if detail_value and not is_price_criteria:
                        detail_score = self._extract_score_from_text(detail_value)
                        is_detail_price_criteria = self._is_price_criteria(detail_value, standard_value)
                        
                        child_rule = {
                            "criteria_name": detail_value,
                            "max_score": detail_score,
                            "description": standard_value,
                            "is_price_criteria": is_detail_price_criteria,
                            "price_formula": price_formula if is_detail_price_criteria else None,
                            "numbering": [numbering_counter - 1, 1]  # 作为父项的第一个子项
                        }
                        rules.append(child_rule)
                    elif detail_value and is_price_criteria:
                        # 对于价格规则，将detail_value作为描述而不是子项
                        rule["description"] = detail_value
                else:
                    # 这是子项（明细项）
                    if detail_value:
                        detail_score = self._extract_score_from_text(detail_value)
                        is_detail_price_criteria = self._is_price_criteria(detail_value, standard_value)
                        
                        # 子项继承父项的价格公式（如果是价格项）
                        price_formula = None
                        if is_detail_price_criteria:
                            price_formula = self._extract_price_formula(standard_value)
                        
                        child_rule = {
                            "criteria_name": detail_value,
                            "max_score": detail_score,
                            "description": standard_value,
                            "is_price_criteria": is_detail_price_criteria,
                            "price_formula": price_formula,
                            "numbering": [numbering_counter - 1, len([r for r in rules if r.get('numbering', [0])[0] == numbering_counter - 1 and len(r.get('numbering', [])) > 1]) + 1]
                        }
                        rules.append(child_rule)
                
            except Exception as e:
                self.logger.error(f"解析第{row_idx + 1}行评分规则时出错: {e}")
                continue
        
        return rules
    
    def _clean_text(self, text: str) -> str:
        """
        清理文本，移除多余的空格和换行符
        
        Args:
            text: 原始文本
            
        Returns:
            str: 清理后的文本
        """
        if not text:
            return ""
        # 移除首尾空格和换行符
        text = text.strip()
        # 将多个连续的空格或换行符合并为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _extract_score_from_text(self, text: str) -> float:
        """
        从文本中提取分数
        
        Args:
            text: 包含分数的文本
            
        Returns:
            float: 提取到的分数，如果未找到则返回0
        """
        if not text:
            return 0.0
            
        # 匹配分数模式，如"10分"、"(10分)"、"10.0分"等
        score_patterns = [
            r'(\d+(?:\.\d+)?)\s*分',  # 匹配"10分"格式
            r'\((\d+(?:\.\d+)?)\s*分\)',  # 匹配"(10分)"格式
            r'满分\s*(\d+(?:\.\d+)?)',  # 匹配"满分10"格式
        ]
        
        for pattern in score_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    continue
        
        return 0.0
    
    def _is_price_criteria(self, project_text: str, standard_text: str) -> bool:
        """
        判断是否为价格评分规则
        
        Args:
            project_text: 项目名称文本
            standard_text: 标准描述文本
            
        Returns:
            bool: 是否为价格评分规则
        """
        price_keywords = ["价格", "报价", "投标报价", "金额", "费用"]
        text_to_check = (project_text + " " + standard_text).lower()
        return any(keyword in text_to_check for keyword in price_keywords)
    
    def _extract_price_formula(self, standard_text: str) -> str:
        """
        从标准文本中提取价格计算公式
        
        Args:
            standard_text: 标准描述文本
            
        Returns:
            str: 价格计算公式
        """
        if not standard_text:
            return ""
            
        # 更全面地提取包含计算公式的内容
        # 实际项目中可能需要更复杂的公式解析逻辑
        formula_patterns = [
            r'投标报价得分[^\n]*?[=＝][^\n]*',  # 投标报价得分=...
            r'价格分[^\n]*?[=＝][^\n]*',       # 价格分=...
            r'得分[^\n]*?[=＝][^\n]*?投标.*?价.*?\/.*?投标.*?价.*?[\*×].*?100',  # 得分=...投标价/投标价*100
            r'评标基准价[^\n]*?[=＝][^\n]*',    # 评标基准价=...
            r'基准价[^\n]*?[=＝][^\n]*',       # 基准价=...
            r'投标报价得分.*?＝.*?评标基准价.*?／.*?投标报价.*?×.*?价格分值',  # 完整公式模式
        ]
        
        for pattern in formula_patterns:
            match = re.search(pattern, standard_text, re.IGNORECASE)
            if match:
                return match.group(0)
        
        # 如果未找到特定公式，返回整个标准文本（限制长度）
        return standard_text[:100] if len(standard_text) > 100 else standard_text
