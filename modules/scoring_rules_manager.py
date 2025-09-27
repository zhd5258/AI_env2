#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-26 18:09:31
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-26 18:09:34
# 文件相对于项目的路径   : \AI_env2\modules\scoring_rules_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from modules.database import ScoringRule


class ScoringRulesManager:
    """评分规则管理器，统一处理评分规则的保存和管理"""

    def __init__(self, db_session: Session = None):
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

            def save_rule_recursive(rule_data, project_id, parent_name=None):
                """递归保存评分规则（父项填 Parent_Item_Name，子项填 Child_Item_Name）"""
                is_price = bool(rule_data.get('is_price_criteria', False))
                children = rule_data.get('children') or []

                if children or is_price:
                    # 保存父项（或价格父项）
                    db_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=rule_data.get('criteria_name'),
                        Parent_max_score=rule_data.get('max_score'),
                        description=rule_data.get('description', ''),
                        is_price_criteria=is_price,
                    )
                    if is_price:
                        db_rule.price_formula = rule_data.get('price_formula')
                    db_rule.Child_Item_Name = None
                    db_rule.Child_max_score = None

                    self.db.add(db_rule)
                    self.db.flush()

                    # 递归保存子项，传递父项名称
                    for child_rule in children:
                        save_rule_recursive(
                            child_rule,
                            project_id,
                            parent_name=rule_data.get('criteria_name'),
                        )
                else:
                    # 保存子项（叶子）
                    db_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=parent_name,
                        Parent_max_score=None,
                        Child_Item_Name=rule_data.get('criteria_name'),
                        Child_max_score=rule_data.get('max_score'),
                        description=rule_data.get('description', ''),
                        is_price_criteria=False,
                    )
                    self.db.add(db_rule)
                    self.db.flush()

            for rule_data in rules:
                save_rule_recursive(rule_data, project_id)

            self.db.commit()
            self.logger.info(f'成功保存 {len(rules)} 条评分规则到数据库')
            return True

        except Exception as e:
            self.logger.error(f'保存评分规则到数据库时出错: {e}', exc_info=True)
            if self.db:
                self.db.rollback()
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
            return rules
        except Exception as e:
            self.logger.error(f'获取评分规则时出错: {e}', exc_info=True)
            return []
