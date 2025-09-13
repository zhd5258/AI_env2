#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据库结构更新脚本
将scoring_rule表更新为新的结构
"""

import sqlite3
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import engine, ScoringRule, Base
from sqlalchemy import MetaData

def update_scoring_rule_table():
    """
    更新scoring_rule表结构
    """
    # 创建到数据库的连接
    conn = sqlite3.connect('tender_evaluation.db')
    cursor = conn.cursor()
    
    try:
        # 1. 重命名旧表
        cursor.execute("ALTER TABLE scoring_rule RENAME TO scoring_rule_old")
        
        # 2. 创建新表（手动创建避免索引冲突）
        cursor.execute("""
            CREATE TABLE scoring_rule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                Parent_Item_Name VARCHAR(20),
                Parent_max_score INTEGER,
                Child_Item_Name VARCHAR(20),
                Child_max_score INTEGER,
                description VARCHAR(100),
                is_veto BOOLEAN,
                is_price_criteria BOOLEAN,
                price_formula VARCHAR(100)
            )
        """)
        
        # 3. 迁移数据（根据字段映射）
        # 由于字段结构变化较大，这里我们只迁移基本字段
        # 实际项目中可能需要根据具体情况调整
        cursor.execute("""
            INSERT INTO scoring_rule 
            (id, project_id, Parent_Item_Name, Parent_max_score, Child_Item_Name, 
             Child_max_score, description, is_veto, is_price_criteria, price_formula)
            SELECT 
                id, 
                project_id,
                substr(criteria_name, 1, 20) as Parent_Item_Name,  -- 临时处理
                CAST(max_score as INTEGER) as Parent_max_score,   -- 临时处理
                substr(criteria_name, 1, 20) as Child_Item_Name,  -- 临时处理
                CAST(max_score as INTEGER) as Child_max_score,    -- 临时处理
                substr(description, 1, 100) as description,
                COALESCE(is_veto, 0) as is_veto,
                COALESCE(is_price_criteria, 0) as is_price_criteria,
                price_formula
            FROM scoring_rule_old
        """)
        
        # 4. 删除旧表
        cursor.execute("DROP TABLE scoring_rule_old")
        
        # 提交事务
        conn.commit()
        print("scoring_rule表结构更新成功！")
        
    except Exception as e:
        # 回滚事务
        conn.rollback()
        print(f"更新过程中发生错误: {e}")
        print("回滚操作...")
        
        # 如果新表已创建但迁移失败，清理新表
        try:
            cursor.execute("DROP TABLE scoring_rule")
        except:
            pass
            
        # 恢复旧表名
        try:
            cursor.execute("ALTER TABLE scoring_rule_old RENAME TO scoring_rule")
        except:
            pass
            
    finally:
        conn.close()

if __name__ == "__main__":
    print("开始更新scoring_rule表结构...")
    update_scoring_rule_table()