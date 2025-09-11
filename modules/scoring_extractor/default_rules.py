import logging
from typing import List, Dict, Any


class DefaultRulesMixin:
    """默认规则混入类，提供默认评分规则和格式转换功能"""
    
    def _get_default_scoring_rules(self) -> List[Dict[str, Any]]:
        """返回默认的评分规则，确保总分为100分"""
        self.logger.info('使用默认评分规则')
        return [
            {
                'numbering': ['1'],
                'criteria_name': '技术方案',
                'max_score': 60.0,
                'weight': 1.0,
                'description': '技术方案评分',
                'category': '评标办法',
                'children': [
                    {
                        'numbering': ['1', '1'],
                        'criteria_name': '技术方案完整性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'description': '技术方案完整性评分',
                        'category': '评标办法',
                        'children': [],
                        'is_price_criteria': False,
                    },
                    {
                        'numbering': ['1', '2'],
                        'criteria_name': '技术方案可行性',
                        'max_score': 30.0,
                        'weight': 1.0,
                        'description': '技术方案可行性评分',
                        'category': '评标办法',
                        'children': [],
                        'is_price_criteria': False,
                    },
                ],
                'is_price_criteria': False,
            },
            {
                'numbering': ['2'],
                'criteria_name': '价格分',
                'max_score': 40.0,
                'weight': 1.0,
                'description': '价格分计算公式：评标基准价为各有效投标人投标报价的算术平均值，价格分=评标基准价/投标报价*价格分值',
                'category': '评标办法',
                'children': [],
                'is_price_criteria': True,
            },
        ]
        
    def _convert_to_standard_format(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将提取的评分规则转换为标准格式"""
        standard_rules = []
        
        for rule in rules:
            # 跳过价格分规则，单独处理
            if rule.get('is_price_criteria'):
                continue
                
            standard_rule = {
                'item': rule.get('criteria_name', ''),
                'max_score': rule.get('max_score', 0),
                'description': rule.get('description', '')
            }
            standard_rules.append(standard_rule)
            
        return standard_rules

    def extract_scoring_rules_standard_format(self) -> List[Dict[str, Any]]:
        """
        提取评分规则并转换为标准格式
        """
        # 提取评分规则
        rules = self.extract_scoring_rules()
        
        # 转换为标准格式
        standard_rules = self._convert_to_standard_format(rules)
        
        return standard_rules