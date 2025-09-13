import logging
from typing import List, Dict, Any
from contextlib import contextmanager


class DBHandlerMixin:
    """数据库处理混入类，提供评分规则保存到数据库的功能"""
    
    @contextmanager
    def _get_db_session(self):
        """
        数据库会话上下文管理器，确保会话正确关闭
        """
        from modules.database import SessionLocal
        db = SessionLocal()
        try:
            yield db
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    def save_scoring_rules_to_db(self, project_id: int, rules: List[Dict[str, Any]]) -> bool:
        """
        将评分规则保存到数据库，并按要求进行清理
        :param project_id: 项目ID
        :param rules: 评分规则列表
        :return: 是否保存成功
        """
        try:
            from modules.database import ScoringRule
            
            with self._get_db_session() as db:
                # 先删除该项目已有的评分规则
                db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
                
                # 第一步：按正常规则提取并存储全部规则
                self._save_scoring_rules_recursive(db, project_id, rules, None)
                db.commit()
                
            with self._get_db_session() as db:
                # 第二步：更新规则，处理父项信息继承
                self._update_parent_info_inheritance(db, project_id)
                db.commit()
                
                # 第三步：清理不完整的规则
                self._clean_incomplete_rules(db, project_id)
                db.commit()
                
            self.logger.info(f"成功将评分规则保存到数据库并完成清理，项目ID: {project_id}")
            return True
        except Exception as e:
            self.logger.error(f"保存评分规则到数据库时出错: {e}", exc_info=True)
            return False

    def _update_parent_info_inheritance(self, db, project_id: int):
        """
        更新父项信息继承
        :param db: 数据库会话
        :param project_id: 项目ID
        """
        from modules.database import ScoringRule
        
        # 获取所有规则并按ID排序
        all_rules = db.query(ScoringRule).filter(
            ScoringRule.project_id == project_id
        ).order_by(ScoringRule.id).all()
        
        last_parent_name = None
        last_parent_score = None
        
        for rule in all_rules:
            # 处理Parent_Item_Name继承
            if rule.Parent_Item_Name is None or rule.Parent_Item_Name == "":
                if last_parent_name is not None:
                    rule.Parent_Item_Name = last_parent_name
            else:
                last_parent_name = rule.Parent_Item_Name
                
            # 处理Parent_max_score继承
            if rule.Parent_max_score is None or rule.Parent_max_score == 0:
                if last_parent_score is not None:
                    rule.Parent_max_score = last_parent_score
            else:
                last_parent_score = rule.Parent_max_score
                
        db.flush()

    def _clean_incomplete_rules(self, db, project_id: int):
        """
        清理不完整的规则：Parent_Item_Name不为空但Child_Item_Name为空的规则
        注意：这里只清理那些应该是子项但没有子项名称的规则
        特殊处理价格规则，不清理价格规则
        :param db: 数据库会话
        :param project_id: 项目ID
        """
        from modules.database import ScoringRule
        
        # 查询满足条件的不完整规则：
        # 1. Parent_Item_Name不为空
        # 2. Child_Item_Name为空
        # 3. Child_max_score也为空（表明这应该是子项但缺少子项信息）
        # 4. 不是价格评分规则
        # 5. 属于指定项目
        incomplete_rules = db.query(ScoringRule).filter(
            ScoringRule.project_id == project_id,
            ScoringRule.Parent_Item_Name.isnot(None),
            ScoringRule.Child_Item_Name.is_(None),
            ScoringRule.Child_max_score.is_(None),
            ScoringRule.is_price_criteria.is_(False)  # 不清理价格规则
        ).all()
        
        count = len(incomplete_rules)
        for rule in incomplete_rules:
            db.delete(rule)
            
        if count > 0:
            self.logger.info(f"清理了 {count} 条不完整的评分规则")

    def _process_scoring_rules(self, rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        处理评分规则列表（保留原始处理逻辑以兼容其他功能）
        :param rules: 原始评分规则列表
        :return: 处理后的评分规则列表
        """
        return rules

    def _save_scoring_rules_recursive(self, db, project_id: int, rules: List[Dict[str, Any]], parent_id: int = None):
        """
        递归保存评分规则到数据库
        :param db: 数据库会话
        :param project_id: 项目ID
        :param rules: 评分规则列表
        :param parent_id: 父级规则ID
        """
        from modules.database import ScoringRule
        
        for rule in rules:
            try:
                # 确定父项和子项名称
                criteria_name = rule['criteria_name']
                max_score = rule['max_score']
                description = rule.get('description', '')
                is_price_criteria = rule.get('is_price_criteria', False)
                price_formula = rule.get('price_formula', None)
                
                # 特殊处理价格规则
                if is_price_criteria and not rule.get('children', []):
                    # 价格规则没有子项，将描述保存在description字段中
                    scoring_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=criteria_name[:20],
                        Parent_max_score=int(max_score) if max_score else None,
                        Child_Item_Name=None,
                        Child_max_score=None,
                        description=description[:100] if description else None,
                        is_veto=False,
                        is_price_criteria=True,
                        price_formula=price_formula[:100] if price_formula else None
                    )
                elif parent_id is None:  # 父项（非价格规则）
                    scoring_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=criteria_name[:20],
                        Parent_max_score=int(max_score) if max_score else None,
                        Child_Item_Name=None,
                        Child_max_score=None,
                        description=description[:100] if description else None,
                        is_veto=False,
                        is_price_criteria=False,
                        price_formula=None
                    )
                else:  # 子项
                    scoring_rule = ScoringRule(
                        project_id=project_id,
                        Parent_Item_Name=None,
                        Parent_max_score=None,
                        Child_Item_Name=criteria_name[:20],
                        Child_max_score=int(max_score) if max_score else None,
                        description=description[:100] if description else None,
                        is_veto=False,
                        is_price_criteria=False,
                        price_formula=None
                    )
                
                # 添加到数据库会话
                db.add(scoring_rule)
                db.flush()  # 刷新以获取ID
                
                # 递归处理子项
                if 'children' in rule and rule['children']:
                    self._save_scoring_rules_recursive(db, project_id, rule['children'], scoring_rule.id)
            except Exception as e:
                self.logger.error(f"保存评分规则 '{rule.get('criteria_name', 'Unknown')}' 时出错: {e}")
                continue

    def save_scoring_rules_from_table_data(self, project_id: int, structured_tables: List[Dict]) -> bool:
        """
        从结构化表格数据中提取评分规则并保存到数据库
        
        Args:
            project_id: 项目ID
            structured_tables: 结构化表格数据列表
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 使用统一的评分规则解析器解析评分规则
            from .rule_parser import ScoringRuleParser
            parser = ScoringRuleParser()
            scoring_rules = parser.parse_scoring_rules_from_table_data(structured_tables)
            
            # 保存到数据库
            return self.save_scoring_rules_to_db(project_id, scoring_rules)
        except Exception as e:
            self.logger.error(f"从表格数据保存评分规则到数据库时出错: {e}")
            return False

    def _parse_scoring_rules_from_table_data(self, structured_tables: List[Dict]) -> List[Dict[str, Any]]:
        """
        从结构化表格数据中解析评分规则
        
        Args:
            structured_tables: 结构化表格数据列表
            
        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        # 直接使用核心模块中的解析逻辑，避免重复实现
        return self._parse_scoring_rules_from_table_data_impl(structured_tables)

    def _parse_scoring_rules_from_table_data_impl(self, structured_tables: List[Dict]) -> List[Dict[str, Any]]:
        """
        从结构化表格数据中解析评分规则的实际实现
        
        Args:
            structured_tables: 结构化表格数据列表
            
        Returns:
            List[Dict[str, Any]]: 评分规则列表
        """
        from .rule_parser import ScoringRuleParser
        parser = ScoringRuleParser()
        return parser.parse_scoring_rules_from_table_data(structured_tables)