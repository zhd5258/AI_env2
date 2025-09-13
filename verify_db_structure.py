#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
验证数据库表结构是否正确更新
"""

import sqlite3
import os
import sys

def verify_scoring_rule_table():
    """
    验证scoring_rule表结构
    """
    conn = sqlite3.connect('tender_evaluation.db')
    cursor = conn.cursor()
    
    try:
        # 获取表结构信息
        cursor.execute("PRAGMA table_info(scoring_rule)")
        columns = cursor.fetchall()
        
        print("scoring_rule表当前结构:")
        print("列名\t\t\t类型\t\t是否可为空\t默认值\t\t主键")
        print("-" * 80)
        for col in columns:
            cid, name, type_, notnull, default_value, pk = col
            print(f"{name}\t\t\t{type_}\t\t{notnull}\t\t{default_value}\t\t{pk}")
        
        # 验证字段是否符合要求
        required_fields = {
            'id': 'INTEGER',
            'project_id': 'INTEGER',
            'Parent_Item_Name': 'VARCHAR(20)',
            'Parent_max_score': 'INTEGER',
            'Child_Item_Name': 'VARCHAR(20)',
            'Child_max_score': 'INTEGER',
            'description': 'VARCHAR(100)',
            'is_veto': 'BOOLEAN',
            'is_price_criteria': 'BOOLEAN',
            'price_formula': 'VARCHAR(100)'
        }
        
        # 检查每个必需字段是否存在
        field_names = [col[1] for col in columns]
        field_types = {col[1]: col[2] for col in columns}
        
        print("\n字段验证结果:")
        print("-" * 40)
        all_good = True
        for field_name, required_type in required_fields.items():
            if field_name in field_names:
                actual_type = field_types[field_name]
                # 对于VARCHAR类型，检查长度是否符合要求
                if 'VARCHAR' in required_type:
                    print(f"✓ {field_name}: 存在，类型 {actual_type}")
                else:
                    print(f"✓ {field_name}: 存在，类型 {actual_type}")
            else:
                print(f"✗ {field_name}: 不存在")
                all_good = False
        
        if all_good:
            print("\n✓ 所有字段均已正确创建")
        else:
            print("\n✗ 部分字段缺失或类型不匹配")
            
    except Exception as e:
        print(f"验证过程中发生错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    verify_scoring_rule_table()