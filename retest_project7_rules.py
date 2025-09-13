#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
清理并重新测试项目7的评分规则提取和保存
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, ScoringRule
from modules.scoring_extractor import IntelligentScoringExtractor

def retest_project7_rules():
    """
    清理并重新测试项目7的评分规则提取和保存
    """
    print("清理并重新测试项目7的评分规则提取和保存")
    print("=" * 60)
    
    try:
        db_session = SessionLocal()
        
        # 检查项目7是否存在
        project = db_session.query(TenderProject).filter(TenderProject.id == 7).first()
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
            
        # 清理现有评分规则
        existing_rules = db_session.query(ScoringRule).filter(ScoringRule.project_id == 7).count()
        if existing_rules > 0:
            print(f"清理现有评分规则: {existing_rules} 条")
            db_session.query(ScoringRule).filter(ScoringRule.project_id == 7).delete()
            db_session.commit()
        
        # 重新提取评分规则
        print(f"\n重新提取评分规则...")
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(project.tender_file_path)
        
        print(f"提取到 {len(scoring_rules)} 条评分规则")
        
        if not scoring_rules:
            print("未能提取到评分规则")
            return
            
        # 使用修复后的逻辑保存评分规则
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
                db_rule.price_formula = None
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
            
            db_session.add(db_rule)
            db_session.flush()  # 获取生成的ID
            
            # 递归保存子项
            if 'children' in rule_data and rule_data['children']:
                for child_rule in rule_data['children']:
                    save_rule_recursive(child_rule, project_id, parent_id=db_rule.id)
        
        # 保存所有评分规则
        for rule_data in scoring_rules:
            save_rule_recursive(rule_data, project_id=7)
            
        db_session.commit()
        print("评分规则保存完成!")
        
        # 验证保存结果
        saved_rules = db_session.query(ScoringRule).filter(ScoringRule.project_id == 7).all()
        print(f"数据库中现在有 {len(saved_rules)} 条评分规则:")
        
        price_rule_count = 0
        for i, rule in enumerate(saved_rules):
            print(f"  规则 {i+1}: {rule.Parent_Item_Name} ({rule.Parent_max_score}分)")
            if rule.is_price_criteria:
                print(f"    - 价格规则")
                price_rule_count += 1
            else:
                print(f"    - 子项: {rule.Child_Item_Name} ({rule.Child_max_score}分)")
        
        print(f"\n总共找到 {price_rule_count} 条价格规则")
        
        db_session.close()
        
        # 测试智能投标分析器能否正确加载这些规则
        print("\n测试智能投标分析器能否正确加载评分规则...")
        from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
        
        test_session = SessionLocal()
        # 模拟智能投标分析器加载评分规则的过程
        rules_from_db = test_session.query(ScoringRule).filter(ScoringRule.project_id == 7).all()
        print(f"智能投标分析器能从数据库加载到 {len(rules_from_db)} 条评分规则")
        
        if rules_from_db:
            child_rules = [rule for rule in rules_from_db 
                          if not rule.is_price_criteria and rule.Child_Item_Name is not None]
            price_rules = [rule for rule in rules_from_db if rule.is_price_criteria]
            
            print(f"  其中子项规则: {len(child_rules)} 条")
            print(f"  价格规则: {len(price_rules)} 条")
            
            if price_rules:
                print("  价格规则详情:")
                for rule in price_rules:
                    print(f"    - {rule.Parent_Item_Name} ({rule.Parent_max_score}分)")
                    print(f"      描述: {rule.description}")
        
        test_session.close()
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    retest_project7_rules()