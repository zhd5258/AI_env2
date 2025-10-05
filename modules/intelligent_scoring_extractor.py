#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-05 20:33:07
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-05 20:33:10
#文件相对于项目的路径   : \AI_env2\modules\intelligent_scoring_extractor.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能评分规则提取器
负责从招标文件中提取评分规则
"""

import re
import logging
from typing import List, Dict, Any


class IntelligentScoringExtractor:
    """智能评分规则提取器"""
    
    def __init__(self, pages_text: List[str] = None, pdf_path: str = ""):
        """
        初始化评分规则提取器
        
        Args:
            pages_text: 按页分割的文本列表
            pdf_path: PDF文件路径（可选）
        """
        self.pages = pages_text or []
        self.pdf_path = pdf_path
        self.logger = logging.getLogger(__name__)
        
    def extract_scoring_rules(self) -> List[Dict[str, Any]]:
        """
        从招标文件中提取评分规则
        
        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        rules = []
        self.logger.info("开始提取评分规则...")
        
        try:
            # 1. 查找评分表标题
            start_page_index, end_page_index = self._find_scoring_section()
            
            if start_page_index == -1:
                self.logger.warning("未找到评标办法章节")
                return []
                
            # 2. 提取评分表内容
            table_text = self._extract_table_content(start_page_index, end_page_index)
            
            # 3. 解析表格内容
            rules = self._parse_scoring_table(table_text)
            
        except Exception as e:
            self.logger.error(f"提取评分规则时出错: {e}")
            
        return rules
    
    def _find_scoring_section(self) -> tuple:
        """
        查找评标办法章节
        
        Returns:
            tuple: (起始页索引, 结束页索引)
        """
        # 查找评标办法等类似章节的标题
        section_patterns = [
            r'第[一二三四五六七八九十]+章.*评标办法',
            r'第[一二三四五六七八九十]+章.*评审办法',
            r'第[三四五]章.*评分',
            r'[三四五][\.、\s]*评标办法',
            r'[三四五][\.、\s]*评审办法',
            r'[三四五][\.、\s]*评分'
        ]
        
        start_page_index = -1
        end_page_index = -1
        
        # 查找起始位置
        for i, page_text in enumerate(self.pages):
            for pattern in section_patterns:
                if re.search(pattern, page_text):
                    start_page_index = i
                    self.logger.info(f'在第 {i + 1} 页找到评标办法章节标题')
                    break
            if start_page_index != -1:
                break
                
        if start_page_index == -1:
            return -1, -1
            
        # 查找结束位置（下一个章节或文件结尾）
        end_patterns = [
            r'第[一二三四五六七八九十]+章',
            r'第[五六七八九十]+[\.、\s]*'
        ]
        
        for i in range(start_page_index + 1, len(self.pages)):
            page_text = self.pages[i]
            for pattern in end_patterns:
                if re.search(pattern, page_text):
                    end_page_index = i - 1
                    break
            if end_page_index != -1:
                break
                
        if end_page_index == -1:
            end_page_index = len(self.pages) - 1
            
        # 限制最多处理5页，避免包含过多无关内容
        end_page_index = min(end_page_index, start_page_index + 4)
        
        return start_page_index, end_page_index
    
    def _extract_table_content(self, start_page_index: int, end_page_index: int) -> str:
        """
        提取表格内容
        
        Args:
            start_page_index: 起始页索引
            end_page_index: 结束页索引
            
        Returns:
            str: 表格文本内容
        """
        # 合并多页内容
        table_text = "\n".join(self.pages[start_page_index:end_page_index + 1])
        
        # 查找表格开始位置（包含表头关键词）
        table_start_patterns = [
            r'评价项目[\s\S]*评价标准',
            r'评分项[\s\S]*评分标准',
            r'评审因素[\s\S]*评审标准'
        ]
        
        table_start_pos = 0
        for pattern in table_start_patterns:
            match = re.search(pattern, table_text)
            if match:
                table_start_pos = match.start()
                break
                
        # 查找表格结束位置（下一章节或文件结尾）
        table_end_pos = len(table_text)
        end_patterns = [
            r'第[一二三四五六七八九十]+章',
            r'[六七八九十][\.、\s]*',
            r'总得分'
        ]
        
        for pattern in end_patterns:
            match = re.search(pattern, table_text[table_start_pos:])
            if match:
                table_end_pos = table_start_pos + match.start()
                break
                
        # 返回表格内容
        return table_text[table_start_pos:table_end_pos] if table_start_pos < len(table_text) else ""
    
    def _parse_scoring_table(self, table_text: str) -> List[Dict[str, Any]]:
        """
        解析评分表格
        
        Args:
            table_text: 表格文本内容
            
        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        rules = []
        lines = table_text.split('\n')
        
        current_parent = None
        parent_score = 0
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 跳过表头行
            if re.search(r'评价项目|评价标准|评分项|评分标准|评审因素|评审标准', line) and len(line) < 20:
                continue
                
            # 特殊处理：检查是否为复合行（包含多个评分项）
            compound_rules = self._parse_compound_line(line)
            if compound_rules:
                for i, rule_data in enumerate(compound_rules):
                    # 判断是父项还是子项
                    if self._is_parent_item(rule_data['name']):
                        # 父项
                        current_parent = rule_data['name']
                        parent_score = rule_data['max_score']
                        rules.append({
                            "criteria_name": rule_data['name'],
                            "max_score": rule_data['max_score'],
                            "description": "",
                            "is_price_criteria": "价格" in rule_data['name'] or "价格分" in rule_data['name'],
                            "is_veto": False
                        })
                    else:
                        # 子项
                        rules.append({
                            "criteria_name": rule_data['name'],
                            "max_score": rule_data['max_score'],
                            "description": rule_data['description'],
                            "is_price_criteria": False,
                            "is_veto": False,
                            "parent_name": current_parent
                        })
            else:
                # 解析单行内容
                rule = self._parse_table_row(line)
                if rule:
                    # 判断是父项还是子项
                    if self._is_parent_item(rule['name']):
                        # 父项
                        current_parent = rule['name']
                        parent_score = rule['max_score']
                        rules.append({
                            "criteria_name": rule['name'],
                            "max_score": rule['max_score'],
                            "description": "",
                            "is_price_criteria": "价格" in rule['name'] or "价格分" in rule['name'],
                            "is_veto": False
                        })
                    else:
                        # 子项
                        rules.append({
                            "criteria_name": rule['name'],
                            "max_score": rule['max_score'],
                            "description": rule['description'],
                            "is_price_criteria": False,
                            "is_veto": False,
                            "parent_name": current_parent
                        })
                    
        # 构建完整的父子项结构
        return self._build_rules_hierarchy(rules)
    
    def _is_parent_item(self, name: str) -> bool:
        """
        判断是否为父项
        
        Args:
            name: 项目名称
            
        Returns:
            bool: 是否为父项
        """
        parent_keywords = [
            '商务部分', '技术部分', '价格分', '服务部分', 
            '价格', '商务', '技术', '服务'
        ]
        
        for keyword in parent_keywords:
            if keyword in name:
                return True
                
        # 如果名称中包含较大的分值，也可能是父项
        score_pattern = r'[\(（](\d+(?:\.\d+)?)\s*分[\)\)]'
        match = re.search(score_pattern, name)
        if match and float(match.group(1)) > 10:
            return True
            
        # 特殊处理：检查是否包含'部分'且有分值
        if '部分' in name:
            score_pattern2 = r'(\d+(?:\.\d+)?)\s*分'
            match2 = re.search(score_pattern2, name)
            if match2:
                return True
            
        return False
    
    def _build_rules_hierarchy(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        构建评分规则的层级结构
        
        Args:
            rules: 扁平化的规则列表
            
        Returns:
            List[Dict[str, Any]]: 层级化的规则列表
        """
        # 分离父项和子项
        parent_rules = [rule for rule in rules if rule.get('description') == '']
        child_rules = [rule for rule in rules if rule.get('description') != '']
        
        # 构建层级结构
        result = []
        
        for parent_rule in parent_rules:
            # 添加父项
            parent_rule['children'] = []
            
            # 查找对应的子项
            parent_name = parent_rule['criteria_name']
            for child_rule in child_rules:
                # 首先检查明确的父项关联
                if child_rule.get('parent_name') == parent_name:
                    parent_rule['children'].append({
                        'criteria_name': child_rule['criteria_name'],
                        'max_score': child_rule['max_score'],
                        'description': child_rule['description'],
                        'is_price_criteria': child_rule['is_price_criteria'],
                        'is_veto': child_rule['is_veto']
                    })
                # 如果没有明确的父项关联，尝试通过名称匹配
                elif self._is_related_to_parent(child_rule['criteria_name'], parent_name):
                    parent_rule['children'].append({
                        'criteria_name': child_rule['criteria_name'],
                        'max_score': child_rule['max_score'],
                        'description': child_rule['description'],
                        'is_price_criteria': child_rule['is_price_criteria'],
                        'is_veto': child_rule['is_veto']
                    })
                # 特殊处理：检查是否在父项之后但在下一个父项之前
                # 注意：这里应该更谨慎，避免将其他父项的子项错误关联
                # 暂时注释掉这个逻辑，避免错误关联
                    
            result.append(parent_rule)
            
        # 处理没有父项的独立规则
        for child_rule in child_rules:
            if not child_rule.get('parent_name'):
                result.append({
                    'criteria_name': child_rule['criteria_name'],
                    'max_score': child_rule['max_score'],
                    'description': child_rule['description'],
                    'is_price_criteria': child_rule['is_price_criteria'],
                    'is_veto': child_rule['is_veto'],
                    'children': []
                })
                
        # 特殊处理价格规则
        self._process_price_rules(result)
        
        return result
    
    def _extract_parent_name(self, name: str) -> str:
        """
        从名称中提取父项名称
        
        Args:
            name: 包含父项信息的名称
            
        Returns:
            str: 父项名称
        """
        parent_keywords = ['商务部分', '技术部分', '价格分', '服务部分']
        
        for keyword in parent_keywords:
            if keyword in name:
                # 提取父项名称部分
                pattern = r'(' + keyword + r'.*?)[\(（]\d+(?:\.\d+)?\s*分[\)\)]'
                match = re.search(pattern, name)
                if match:
                    return match.group(1).strip()
                else:
                    return keyword
                    
        return name
    
    def _extract_parent_score(self, name: str) -> float:
        """
        从名称中提取父项分值
        
        Args:
            name: 包含父项信息的名称
            
        Returns:
            float: 父项分值
        """
        score_pattern = r'[\(（](\d+(?:\.\d+)?)\s*分[\)\)]'
        match = re.search(score_pattern, name)
        if match:
            return float(match.group(1))
        return 0.0
    
    def _get_parent_keyword(self, name: str) -> str:
        """
        获取名称中的父项关键词
        
        Args:
            name: 项目名称
            
        Returns:
            str: 父项关键词，如果没有则返回空字符串
        """
        parent_keywords = ['商务部分', '技术部分', '价格分', '服务部分']
        
        for keyword in parent_keywords:
            if keyword in name:
                return keyword
                
        return ""
    
    def _contains_parent_name(self, name: str) -> bool:
        """
        检查名称是否包含父项名称
        
        Args:
            name: 项目名称
            
        Returns:
            bool: 是否包含父项名称
        """
        parent_keywords = ['商务部分', '技术部分', '价格分', '服务部分']
        
        for keyword in parent_keywords:
            # 检查是否包含父项名称
            if keyword in name:
                return True
                
        return False
    
    def _is_related_to_parent(self, child_name: str, parent_name: str) -> bool:
        """
        判断子项是否与父项相关
        
        Args:
            child_name: 子项名称
            parent_name: 父项名称
            
        Returns:
            bool: 是否相关
        """
        # 更精确的匹配逻辑
        # 检查是否包含父项关键词
        if '商务' in parent_name and '商务' in child_name:
            return True
        if '技术' in parent_name and '技术' in child_name:
            return True
        if '服务' in parent_name and '服务' in child_name:
            return True
        if '价格' in parent_name and '价格' in child_name:
            return True
            
        # 检查是否在父项名称附近（用于处理换行等情况）
        parent_clean = re.sub(r'[^\u4e00-\u9fff]', '', parent_name)
        child_clean = re.sub(r'[^\u4e00-\u9fff]', '', child_name)
        
        if parent_clean in child_clean or child_clean in parent_clean:
            return True
            
        return False
    
    def _process_price_rules(self, rules: List[Dict[str, Any]]) -> None:
        """
        处理价格规则，提取价格公式
        
        Args:
            rules: 规则列表
        """
        for rule in rules:
            if rule.get('is_price_criteria', False):
                # 从描述中提取价格公式
                description = rule.get('description', '')
                formula_pattern = r'投标报价得分.*?[=＝].*?[\d\s\*\/\(\)\+\-\.]+'
                match = re.search(formula_pattern, description)
                if match:
                    rule['price_formula'] = match.group(0)
                else:
                    # 默认价格公式
                    rule['price_formula'] = '投标报价得分＝(评标基准价/投标报价)×价格权重×100'
    
    def _parse_compound_line(self, line: str) -> List[Dict[str, Any]]:
        """
        解析复合行（包含多个评分项的行）
        
        Args:
            line: 行文本
            
        Returns:
            List[Dict[str, Any]]: 解析结果列表
        """
        # 清理文本
        line = re.sub(r'\s+', ' ', line.strip())
        
        # 查找所有评分项模式
        # 例如：XXX(5分) YYY(10分)
        pattern = r'(.+?)[\(（](\d+(?:\.\d+)?)\s*分[\)\)]'
        matches = re.findall(pattern, line)
        
        if len(matches) <= 1:
            return []  # 不是复合行
            
        # 解析每个评分项
        rules = []
        start_pos = 0
        
        for i, match in enumerate(matches):
            name = match[0].strip()
            max_score = float(match[1])
            
            # 提取描述（到下一个评分项或行尾）
            if i < len(matches) - 1:
                # 到下一个评分项
                next_pos = line.find(matches[i+1][0], start_pos)
                description = line[start_pos + len(match[0]) + len(match[1]) + 4:next_pos].strip()
            else:
                # 到行尾
                description = line[start_pos + len(match[0]) + len(match[1]) + 4:].strip()
                
            # 清理描述
            description = re.sub(r'^[\)\)]*', '', description).strip()
            description = re.sub(r'\s+', ' ', description).strip()
            
            # 更新起始位置
            start_pos = line.find(name, start_pos) + len(name)
            
            rules.append({
                "name": name,
                "max_score": max_score,
                "description": description
            })
            
        return rules
    
    def _parse_table_row(self, line: str) -> Dict[str, Any]:
        """
        解析表格行
        
        Args:
            line: 行文本
            
        Returns:
            Dict[str, Any]: 解析结果
        """
        # 清理文本
        line = re.sub(r'\s+', ' ', line.strip())
        
        # 提取评分项名称、分值和描述
        # 匹配格式如：商务部分(18分) 或 企业证书，认证体系（5 分）
        pattern = r'(.+?)[\(（](\d+(?:\.\d+)?)\s*[分\)\)](.*)'
        match = re.search(pattern, line)
        
        if not match:
            # 尝试匹配没有括号的格式
            pattern2 = r'(.+?)\s+(\d+(?:\.\d+)?)\s*分(.*)'
            match = re.search(pattern2, line)
            if not match:
                return None
            
        name = match.group(1).strip()
        max_score = float(match.group(2))
        description = match.group(3).strip() if len(match.groups()) > 2 else ""
        
        # 清理名称：替换中文标点为英文标点
        name = re.sub(r'[，,]', ',', name)
        name = re.sub(r'[：:]', ':', name)
        name = re.sub(r'[；;]', ';', name)
        
        # 过滤掉多余的空格和换行符
        name = re.sub(r'\s+', ' ', name).strip()
        
        # 清理描述
        description = re.sub(r'^[\)\)]*', '', description).strip()
        description = re.sub(r'\s+', ' ', description).strip()
        
        return {
            "name": name,
            "max_score": max_score,
            "description": description
        }
