#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:09:31
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-07 21:03:09
# 文件相对于项目的路径   : \AI_ENV2\modules\scoring_rules_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from models.database import ScoringRule


class ScoringRulesManager:
    """评分规则管理器，统一处理评分规则的保存和管理"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.logger = logging.getLogger(__name__)

    def save_scoring_rules(self, project_id: int, rules: List[Dict[str, Any]]) -> bool:
        """
        统一保存评分规则到数据库

        Args:
            project_id: 项目ID
            rules: 评分规则列表

        Returns:
            bool: 是否保存成功
        """
        try:
            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 先删除该项目已有的评分规则
            self.db.query(ScoringRule).filter(
                ScoringRule.project_id == project_id
            ).delete()

            # 过滤掉无效的规则（名称和描述都为None或空的规则）
            valid_rules = []
            for rule in rules:
                # 检查规则是否有效
                criteria_name = rule.get('criteria_name')
                description = rule.get('description', '')

                # 如果是价格规则，允许没有子项
                is_price_rule = bool(rule.get('is_price_criteria', False))

                # 检查是否有有效的子项
                children = rule.get('children') or []
                has_valid_children = any(
                    child.get('criteria_name')
                    and str(child.get('criteria_name')).strip()
                    for child in children
                )

                # 判断规则是否有效
                is_valid = (
                    (criteria_name and str(criteria_name).strip())  # 有有效的名称
                    or (description and str(description).strip())  # 有有效的描述
                    or is_price_rule  # 是价格规则
                    or has_valid_children  # 有有效的子项
                )

                if is_valid:
                    valid_rules.append(rule)
                else:
                    self.logger.warning(f'过滤掉无效的评分规则: {rule}')

            # 修复：记录将要保存的规则信息
            self.logger.info(f'准备保存 {len(valid_rules)} 条有效评分规则')
            for i, rule in enumerate(valid_rules):
                self.logger.info(
                    f'规则 {i + 1}: {rule["criteria_name"]}, 分数: {rule["max_score"]}, 是否价格规则: {rule["is_price_criteria"]}'
                )
                if rule.get('children'):
                    for j, child in enumerate(rule['children']):
                        self.logger.info(
                            f'  子项 {j + 1}: {child["criteria_name"]}, 分数: {child["max_score"]}'
                        )

            def save_rule_recursive(rule_data, project_id, parent_name=None):
                """递归保存评分规则（父项填 Parent_Item_Name，子项填 Child_Item_Name）"""
                # 再次检查规则数据是否有效
                criteria_name = rule_data.get('criteria_name')
                description = rule_data.get('description', '')
                is_price = bool(rule_data.get('is_price_criteria', False))
                children = rule_data.get('children') or []

                # 获取定性规则和定量规则标识
                is_qualitative = bool(rule_data.get('is_qualitative', False))
                is_quantitative = bool(rule_data.get('is_quantitative', False))

                # 获取否决项标识
                is_veto = bool(rule_data.get('is_veto', False))
                
                # 获取综合分析标识（从is_comprehensive字段转换）
                needs_comprehensive = bool(rule_data.get('is_comprehensive', False))

                # 如果规则名称和描述都为空且不是价格规则，跳过保存
                if (
                    (not criteria_name or not str(criteria_name).strip())
                    and (not description or not str(description).strip())
                    and not is_price
                    and not children
                ):
                    self.logger.warning(f'跳过保存无效规则: {rule_data}')
                    return

                if children or is_price:
                    # 保存父项（或价格父项）
                    db_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=str(rule_data.get('criteria_name') or ''),
                        Parent_max_score=int(rule_data.get('max_score') or 0),
                        description=str(rule_data.get('description') or ''),
                        rule_usage_description=str(rule_data.get('rule_usage_description') or ''),
                        is_price_criteria=is_price,
                        is_qualitative=is_qualitative,
                        is_quantitative=is_quantitative,
                        is_veto=is_veto,
                        needs_comprehensive_analysis=needs_comprehensive,
                    )
                    if is_price:
                        db_rule.price_formula = str(
                            rule_data.get('price_formula') or ''
                        )
                        # 对于价格规则，父项和子项是同一个规则
                        # 父项的Child_Item_Name和Child_max_score应设置为与父项相同
                        db_rule.Child_Item_Name = str(
                            rule_data.get('criteria_name') or ''
                        )
                        db_rule.Child_max_score = int(rule_data.get('max_score') or 0)
                    else:
                        # 对于非价格规则，父项的Child_Item_Name为空字符串，Child_max_score为0
                        db_rule.Child_Item_Name = ''  # 父项的Child_Item_Name为空字符串
                        db_rule.Child_max_score = 0  # 父项的Child_max_score为0

                    if self.db:
                        self.db.add(db_rule)
                        self.db.flush()
                        # 修复：记录保存的父项规则
                        self.logger.info(
                            f'保存父项规则: {db_rule.Parent_Item_Name}, 分数: {db_rule.Parent_max_score}'
                        )

                    # 特殊处理价格规则：不需要为价格规则创建额外的子项规则
                    # 因为价格规则的父项和子项是同一个规则
                    if not is_price:
                        # 递归保存普通子项，传递父项名称
                        for child_rule in children:
                            save_rule_recursive(
                                child_rule,
                                project_id,
                                parent_name=rule_data.get('criteria_name'),
                            )
                else:
                    # 保存子项（叶子）
                    # 检查子项是否有效
                    child_criteria_name = rule_data.get('criteria_name')
                    if not child_criteria_name or not str(child_criteria_name).strip():
                        self.logger.warning(f'跳过保存无效子项规则: {rule_data}')
                        return

                    db_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=str(parent_name or ''),
                        Parent_max_score=0,  # 子项的Parent_max_score为0
                        Child_Item_Name=str(rule_data.get('criteria_name') or ''),
                        Child_max_score=int(rule_data.get('max_score') or 0),
                        description=str(rule_data.get('description') or ''),
                        rule_usage_description=str(rule_data.get('rule_usage_description') or ''),
                        is_price_criteria=False,
                        is_qualitative=is_qualitative,
                        is_quantitative=is_quantitative,
                        is_veto=is_veto,
                        needs_comprehensive_analysis=needs_comprehensive,
                    )
                    if self.db:
                        self.db.add(db_rule)
                        self.db.flush()
                        # 修复：记录保存的子项规则
                        self.logger.info(
                            f'保存子项规则: {db_rule.Child_Item_Name}, 分数: {db_rule.Child_max_score}, 父项: {db_rule.Parent_Item_Name}'
                        )

            for rule_data in valid_rules:
                save_rule_recursive(rule_data, project_id)

            if self.db:
                self.db.commit()
            self.logger.info(
                f'成功保存 {len(valid_rules)} 条评分规则到数据库（过滤前共 {len(rules)} 条）'
            )

            # 新增：使用智能规则分类器对规则进行分类和标记
            try:
                from modules.intelligent_rules_classifier import (
                    IntelligentRulesClassifier,
                )

                classifier = IntelligentRulesClassifier(db_session=self.db)
                classification_success = classifier.classify_and_mark_rules(project_id)
                if classification_success:
                    self.logger.info(f'项目 {project_id} 的评分规则智能分类和标记完成')
                else:
                    self.logger.warning(
                        f'项目 {project_id} 的评分规则智能分类和标记失败'
                    )
            except Exception as e:
                self.logger.error(f'调用智能规则分类器时出错: {e}')

            return True

        except Exception as e:
            self.logger.error(f'保存评分规则到数据库时出错: {e}', exc_info=True)
            if self.db:
                try:
                    self.db.rollback()
                except:
                    pass
            return False

    def get_scoring_rules(self, project_id: int) -> List[ScoringRule]:
        """
        获取项目的评分规则

        Args:
            project_id: 项目ID

        Returns:
            List[ScoringRule]: 评分规则列表
        """
        try:
            if not self.db:
                self.logger.error('数据库会话未提供')
                return []

            rules = (
                self.db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .all()
            )
            # 过滤掉无效的规则（名称和描述都为None或空的规则）
            valid_rules = []
            for rule in rules:
                # 检查规则是否有效
                parent_name = rule.Parent_Item_Name
                child_name = rule.Child_Item_Name
                description = rule.description

                # 判断规则是否有效
                is_valid = (
                    (parent_name and str(parent_name).strip())  # 有有效的父项名称
                    or (child_name and str(child_name).strip())  # 有有效的子项名称
                    or (description and str(description).strip())  # 有有效的描述
                    or rule.is_price_criteria  # 是价格规则
                )

                if is_valid:
                    valid_rules.append(rule)
                else:
                    self.logger.warning(f'过滤掉无效的数据库评分规则: {rule}')

            return valid_rules
        except Exception as e:
            self.logger.error(f'获取评分规则时出错: {e}')
            return []
