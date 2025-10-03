import re
import logging
from typing import List, Dict, Any, Tuple


class StructureHandlerMixin:
    """结构处理混入类，提供评分规则结构处理和验证功能"""
    
    def _build_tree_from_flat_list(
        self, flat_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """从扁平的规则列表构建层级树结构，确保正确区分子项和母项"""
        if not flat_list:
            return []

        # 按编号排序，确保层级关系正确
        flat_list.sort(key=lambda x: x['numbering'])

        tree = []
        # 使用一个栈来追踪当前层级的父节点
        parent_stack: List[Dict[str, Any]] = []

        for item in flat_list:
            item['children'] = []

        for item in flat_list:
            item['children'] = []
            level = len(item['numbering'])

            # 根据当前项的层级调整父节点栈
            # 只有当父节点的层级小于当前项时才保留
            while parent_stack and len(parent_stack[-1]['numbering']) >= level:
                parent_stack.pop()

            if not parent_stack:
                # 如果栈为空，说明是顶级节点
                tree.append(item)
            else:
                # 否则，是栈顶节点的子节点
                parent_stack[-1]['children'].append(item)

            # 将当前项压入栈，作为后续节点的潜在父节点
            parent_stack.append(item)

        # 验证层级结构，确保没有重叠
        self._validate_tree_structure(tree)

        return tree

    def _validate_tree_structure(self, tree: List[Dict[str, Any]]):
        """验证树结构，确保没有重叠和错误"""
        for rule in tree:
            if rule['children']:
                # 检查子项分数之和是否等于父项分数
                children_sum = sum(child['max_score'] for child in rule['children'])
                if abs(rule['max_score'] - children_sum) > 0.1:
                    self.logger.warning(
                        f"父项 '{rule['criteria_name']}' 分数 ({rule['max_score']}) "
                        f'与子项分数之和 ({children_sum}) 不匹配'
                    )

                # 递归验证子项
                self._validate_tree_structure(rule['children'])
                
    def _verify_and_adjust_scores(self, rules: List[Dict[str, Any]]):
        """递归验证并调整父项的分数，确保总分不超过100分"""
        total_score = 0
        price_score = 0
        non_price_rules = []
        
        # 分离价格分和非价格分规则
        for rule in rules:
            # 如果是价格评分规则，单独记录
            if rule.get('is_price_criteria'):
                price_score = rule['max_score']
            else:
                non_price_rules.append(rule)
                if rule['children']:
                    # 递归处理子项
                    self._verify_and_adjust_scores(rule['children'])

                    # 计算子项分数之和
                    children_score_sum = sum(
                        child['max_score'] for child in rule['children']
                    )

                    # 如果父项分数与子项之和不匹配，进行调整
                    if abs(rule['max_score'] - children_score_sum) > 0.1:  # 使用浮点数容差
                        self.logger.warning(
                            f"调整父项 '{rule['criteria_name']}' 的分数: {rule['max_score']} -> {children_score_sum}"
                        )
                        rule['max_score'] = children_score_sum
                total_score += rule['max_score']

        # 检查总分是否为100分
        calculated_total = total_score + price_score
        if abs(calculated_total - 100.0) > 0.1:
            self.logger.warning(f'总分 {calculated_total} 不等于100，需要调整')
            # 检查是否包含价格分且价格分较高（超过30分）
            if price_score > 30:
                # 价格分通常不需要调整，保持原样
                # 调整非价格分部分，使其与价格分总和为100
                target_non_price_score = 100.0 - price_score
                if total_score > 0:
                    adjustment_factor = target_non_price_score / total_score
                    for rule in non_price_rules:
                        rule['max_score'] *= adjustment_factor
                        if rule['children']:
                            # 同时调整子项分数
                            for child in rule['children']:
                                child['max_score'] *= adjustment_factor
                    self.logger.info(f'已调整非价格分部分，调整因子: {adjustment_factor}')
                    
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
                if self._is_similar_criteria(criteria_name, existing_name):
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