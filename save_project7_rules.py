#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动为项目7保存评分规则
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, ScoringRule
from modules.scoring_extractor import IntelligentScoringExtractor

def save_project7_rules():
    """
    手动为项目7保存评分规则
    """
    print("手动为项目7保存评分规则")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目7是否存在
        project = session.query(TenderProject).filter(TenderProject.id == 7).first()
        if not project:
            print("错误：项目7不存在")
            return
        
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  状态: {project.status}")
        print(f"  描述: {project.description}")
        print(f"  招标文件路径: {project.tender_file_path}")
        
        # 检查招标文件是否存在
        if not os.path.exists(project.tender_file_path):
            print(f"错误：招标文件不存在 {project.tender_file_path}")
            return
            
        # 检查是否已有评分规则
        existing_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 7).count()
        if existing_rules > 0:
            print(f"警告：项目7已存在 {existing_rules} 条评分规则")
            # 删除现有规则
            session.query(ScoringRule).filter(ScoringRule.project_id == 7).delete()
            session.commit()
            print("已删除现有评分规则")
        
        # 提取评分规则
        print(f"\n开始提取评分规则...")
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(project.tender_file_path)
        
        print(f"提取到 {len(scoring_rules)} 条评分规则")
        
        if not scoring_rules:
            print("未能提取到评分规则")
            return
            
        # 保存评分规则到数据库
        print("开始保存评分规则到数据库...")
        
        def save_rule_recursive(rule_data, project_id, parent_id=None):
            """递归保存评分规则"""
            # 创建评分规则对象
            db_rule = ScoringRule(
                project_id=project_id,
                Parent_Item_Name=rule_data.get('criteria_name'),
                Parent_max_score=rule_data.get('max_score'),
                description=rule_data.get('description', ''),
                is_price_criteria='价格' in rule_data.get('criteria_name', '') or 'price' in rule_data.get('criteria_name', '').lower()
            )
            
            # 如果是价格规则，设置价格公式字段
            if db_rule.is_price_criteria:
                db_rule.price_formula = None  # 可以根据需要设置具体公式
                db_rule.Child_Item_Name = None
                db_rule.Child_max_score = None
            else:
                # 对于非价格规则，如果有子项，需要特殊处理
                if 'children' in rule_data and rule_data['children']:
                    # 父项规则，子项信息将在子项规则中保存
                    db_rule.Child_Item_Name = None
                    db_rule.Child_max_score = None
                else:
                    # 叶子节点规则（没有子项）
                    db_rule.Child_Item_Name = rule_data.get('criteria_name')
                    db_rule.Child_max_score = rule_data.get('max_score')
            
            session.add(db_rule)
            session.flush()  # 获取生成的ID
            
            # 递归保存子项
            if 'children' in rule_data and rule_data['children']:
                for child_rule in rule_data['children']:
                    save_rule_recursive(child_rule, project_id, parent_id=db_rule.id)
        
        # 保存所有评分规则
        for rule_data in scoring_rules:
            save_rule_recursive(rule_data, project_id=7)
            
        session.commit()
        print("评分规则保存完成!")
        
        # 验证保存结果
        saved_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 7).all()
        print(f"数据库中现在有 {len(saved_rules)} 条评分规则:")
        
        for i, rule in enumerate(saved_rules):
            print(f"  规则 {i+1}: {rule.Parent_Item_Name} ({rule.Parent_max_score}分)")
            if rule.is_price_criteria:
                print(f"    - 价格规则")
            else:
                print(f"    - 子项: {rule.Child_Item_Name} ({rule.Child_max_score}分)")
        
        session.close()
        
    except Exception as e:
        print(f"保存过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    save_project7_rules()