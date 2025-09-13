"""
表格分析辅助模块
包含表格分析相关的辅助函数
"""

import re
import logging
from typing import List, Dict, Any, Tuple


class TableAnalyzerHelpers:
    """表格分析辅助类"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _extract_table_scoring_rules_structured(self, text: str) -> List[Dict[str, Any]]:
        """
        基于结构的表格评分规则提取方法
        通过查找包含"评价项目"、"评分标准"等关键词的表格结构来提取评分规则
        """
        # 查找可能的表格区域
        # 这里使用简单的行分组方法，实际项目中可能需要更复杂的表格识别逻辑
        lines = text.split('\n')
        table_regions = self._find_table_regions(lines)
        
        structured_rules = []
        for start, end in table_regions:
            region_lines = lines[start:end+1]
            # 尝试从表格区域提取评分规则
            rules = self._parse_table_region(region_lines)
            if rules:
                structured_rules.extend(rules)
                
        return structured_rules

    def _find_table_regions(self, lines: List[str]) -> List[Tuple[int, int]]:
        """
        查找可能的表格区域
        通过查找包含特定关键词的连续行来识别表格
        
        Args:
            lines: 文本行列表
            
        Returns:
            List[Tuple[int, int]]: 表格区域的起始和结束行索引
        """
        table_regions = []
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 查找表格开始标记
            if any(keyword in line for keyword in ['评价项目', '评分标准', '评审标准']):
                start = i
                # 查找表格结束标记（下一个标题或空行较多的区域）
                j = i + 1
                empty_line_count = 0
                while j < len(lines):
                    line_j = lines[j].strip()
                    if not line_j:
                        empty_line_count += 1
                        if empty_line_count > 2:  # 连续空行较多，认为表格结束
                            break
                    elif re.match(r'^[一二三四五六七八九十\d]+[、.．]', line_j):  # 新的章节标题
                        break
                    elif any(keyword in line_j for keyword in ['评价项目', '评分标准', '评审标准']) and j > i + 1:
                        # 另一个表格开始
                        break
                    j += 1
                
                end = j - 1
                table_regions.append((start, end))
                i = j
            else:
                i += 1
                
        return table_regions

    def _parse_table_region(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        解析表格区域并提取评分规则
        
        Args:
            lines: 表格区域的行列表
            
        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        # 简单实现：查找包含评分关键词的行
        rules = []
        for line in lines:
            # 匹配类似"xxx (5分)"的模式
            pattern = r'([^\n]*?[\u4e00-\u9fa5]+[^\n]*)\s*\((\d+(?:\.\d+)?)\s*分\)'
            matches = re.findall(pattern, line)
            for match in matches:
                criteria_name = match[0].strip()
                score_str = match[1]
                
                # 清理评分项名称
                criteria_name = self._clean_criteria_name(criteria_name)
                
                try:
                    score = float(score_str)
                    rule = {
                        'criteria_name': criteria_name,
                        'max_score': score,
                        'description': '',
                        'numbering': [len(rules) + 1],
                    }
                    rules.append(rule)
                except ValueError:
                    self.logger.warning(f'无法解析分数: {score_str}')
                    
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