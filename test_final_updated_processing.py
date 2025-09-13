#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
最终测试修改后的评分规则处理逻辑
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.scoring_extractor.db_handler import DBHandlerMixin
from modules.database import SessionLocal, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def close_existing_connections():
    """关闭可能存在的数据库连接"""
    try:
        # 等待一段时间确保其他连接释放
        time.sleep(1)
    except:
        pass

def test_pdf_rule_processing():
    """
    测试从PDF文件提取评分规则并处理的完整流程
    """
    pdf_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"✗ PDF文件不存在: {pdf_path}")
        return False
    
    try:
        # 提取评分规则
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(pdf_path)
        
        if not scoring_rules:
            print("✗ 未能从PDF中提取到评分规则")
            return False
        
        print(f"✓ 成功从PDF中提取到 {len(scoring_rules)} 条评分规则")
        
        # 显示提取的规则
        print("\n提取的评分规则:")
        for i, rule in enumerate(scoring_rules):
            print(f"  {i+1}. {rule.get('criteria_name', '未知')} (分值: {rule.get('max_score', 0)})")
            if 'children' in rule and rule['children']:
                for j, child in enumerate(rule['children']):
                    print(f"     - {child.get('criteria_name', '未知')} (分值: {child.get('max_score', 0)})")
        
        # 测试处理逻辑
        handler = TestDBHandler()
        
        # 处理规则
        processed_rules = handler._process_scoring_rules(scoring_rules)
        print(f"\n✓ 规则处理完成，处理后共有 {len(processed_rules)} 条规则")
        
        # 保存到数据库
        project_id = 6  # 使用新的项目ID
        
        # 关闭可能存在的数据库连接
        close_existing_connections()
        
        success = handler.save_scoring_rules_to_db(project_id, scoring_rules)
        
        if success:
            print("✓ 评分规则成功保存到数据库")
            
            # 验证保存的数据
            session = SessionLocal()
            try:
                rules = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
                print(f"✓ 共保存了 {len(rules)} 条评分规则")
                
                # 分析保存的规则
                parent_rules = [r for r in rules if r.Parent_Item_Name is not None]
                child_rules = [r for r in rules if r.Child_Item_Name is not None]
                
                print(f"  - 父项规则: {len(parent_rules)} 条")
                print(f"  - 子项规则: {len(child_rules)} 条")
                
                print("\n数据库中的评分规则:")
                for rule in rules:
                    print(f"  - ID: {rule.id}")
                    print(f"    Parent_Item_Name: {rule.Parent_Item_Name}")
                    print(f"    Parent_max_score: {rule.Parent_max_score}")
                    print(f"    Child_Item_Name: {rule.Child_Item_Name}")
                    print(f"    Child_max_score: {rule.Child_max_score}")
                    print(f"    Description: {rule.description[:50]}..." if rule.description and len(rule.description) > 50 else f"    Description: {rule.description}")
                    print(f"    Is_veto: {rule.is_veto}")
                    print(f"    Is_price_criteria: {rule.is_price_criteria}")
                    print(f"    Price_formula: {rule.price_formula}")
                    print()
            finally:
                session.close()
        else:
            print("✗ 评分规则保存到数据库失败")
            
        return True
    except Exception as e:
        print(f"✗ 处理PDF评分规则时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rule_inheritance():
    """
    测试规则继承逻辑
    """
    print("测试规则继承逻辑...")
    
    # 创建测试数据
    test_rules = [
        {
            "criteria_name": "技术部分",
            "max_score": 40,
            "description": "技术评分标准",
            "children": [
                {"criteria_name": "技术方案", "max_score": 20, "description": "技术方案评价"},
                {"criteria_name": "技术团队", "max_score": 20, "description": "技术团队评价"}
            ]
        },
        {
            "criteria_name": "",  # 空的父项名称
            "max_score": 0,       # 空的父项分数
            "description": "商务评分标准",
            "children": [
                {"criteria_name": "企业资质", "max_score": 10, "description": "企业资质评价"}
            ]
        }
    ]
    
    handler = TestDBHandler()
    
    print("处理前:")
    for i, rule in enumerate(test_rules):
        print(f"  规则{i+1}: {rule['criteria_name']} ({rule['max_score']}分)")
        if 'children' in rule and rule['children']:
            for j, child in enumerate(rule['children']):
                print(f"    子项{j+1}: {child['criteria_name']} ({child['max_score']}分)")
    
    # 处理规则
    processed_rules = handler._process_scoring_rules(test_rules)
    
    print("\n处理后:")
    for i, rule in enumerate(processed_rules):
        print(f"  规则{i+1}: {rule['criteria_name']} ({rule['max_score']}分)")
        if 'children' in rule and rule['children']:
            for j, child in enumerate(rule['children']):
                print(f"    子项{j+1}: {child['criteria_name']} ({child['max_score']}分)")

if __name__ == "__main__":
    test_rule_inheritance()
    print("\n" + "="*50 + "\n")
    test_pdf_rule_processing()