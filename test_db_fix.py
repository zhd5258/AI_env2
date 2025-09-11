#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库修复脚本
验证price_formula字段是否可以正常使用
"""

from modules.database import SessionLocal, ScoringRule

def test_database_fix():
    """测试数据库修复"""
    print("开始测试数据库修复...")
    
    try:
        # 创建数据库会话
        db = SessionLocal()
        
        # 尝试查询scoring_rule表
        count = db.query(ScoringRule).count()
        print(f"成功查询scoring_rule表，共有 {count} 条记录")
        
        # 尝试创建一个新的评分规则，包含price_formula字段
        test_rule = ScoringRule(
            project_id=1,
            category="测试类别",
            criteria_name="测试评分项",
            max_score=10.0,
            weight=1.0,
            description="测试描述",
            is_veto=False,
            numbering="1",
            is_price_criteria=True,
            price_formula="测试价格公式"
        )
        
        db.add(test_rule)
        db.commit()
        print("成功向scoring_rule表添加包含price_formula字段的记录")
        
        # 查询刚刚添加的记录
        rule = db.query(ScoringRule).filter(ScoringRule.criteria_name == "测试评分项").first()
        if rule and rule.price_formula == "测试价格公式":
            print("成功验证price_formula字段的读写功能")
        else:
            print("price_formula字段读写功能验证失败")
        
        # 删除测试记录
        if rule:
            db.delete(rule)
            db.commit()
            print("已删除测试记录")
        
        db.close()
        print("数据库测试完成")
        return True
        
    except Exception as e:
        print(f"数据库测试失败: {e}")
        return False

if __name__ == "__main__":
    success = test_database_fix()
    if success:
        print("✓ 数据库修复验证成功")
    else:
        print("✗ 数据库修复验证失败")