import logging
from typing import List, Dict, Any


class DBHandlerMixin:
    """数据库处理混入类，提供评分规则保存到数据库的功能"""
    
    def save_scoring_rules_to_db(self, project_id: int, rules: List[Dict[str, Any]]) -> bool:
        """
        将评分规则保存到数据库
        :param project_id: 项目ID
        :param rules: 评分规则列表
        :return: 是否保存成功
        """
        try:
            from .database import SessionLocal, ScoringRule
            
            db = SessionLocal()
            try:
                # 先删除该项目已有的评分规则
                db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
                
                # 递归保存评分规则（包括大项和子项）
                self._save_scoring_rules_recursive(db, project_id, rules, None)
                
                db.commit()
                self.logger.info(f"成功将评分规则保存到数据库，项目ID: {project_id}")
                return True
            except Exception as e:
                db.rollback()
                self.logger.error(f"保存评分规则到数据库时出错: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            self.logger.error(f"连接数据库时出错: {e}")
            return False

    def _save_scoring_rules_recursive(self, db, project_id: int, rules: List[Dict[str, Any]], parent_id: int = None):
        """
        递归保存评分规则到数据库
        :param db: 数据库会话
        :param project_id: 项目ID
        :param rules: 评分规则列表
        :param parent_id: 父级规则ID
        """
        from .database import ScoringRule
        
        for rule in rules:
            # 创建评分规则对象
            scoring_rule = ScoringRule(
                project_id=project_id,
                category=rule.get('category', '评标办法'),
                criteria_name=rule['criteria_name'],
                max_score=rule['max_score'],
                weight=rule.get('weight', 1.0),
                description=rule.get('description', ''),
                is_veto=rule.get('is_veto', False),
                parent_id=parent_id,
                numbering='.'.join(rule['numbering']) if isinstance(rule['numbering'], tuple) else str(rule['numbering']),
                is_price_criteria=rule.get('is_price_criteria', False),
                price_formula=rule.get('price_formula', None)  # 保存价格计算公式
            )
            
            # 添加到数据库会话
            db.add(scoring_rule)
            db.flush()  # 刷新以获取ID
            
            # 递归处理子项
            if 'children' in rule and rule['children']:
                self._save_scoring_rules_recursive(db, project_id, rule['children'], scoring_rule.id)