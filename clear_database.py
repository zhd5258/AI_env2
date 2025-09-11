#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空数据库脚本
清空所有表中的数据，但保持表结构
"""

import sqlite3
import os

def clear_database():
    """清空数据库中的所有数据"""
    db_path = './tender_evaluation.db'
    
    if not os.path.exists(db_path):
        print("数据库文件不存在")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 禁用外键约束
        cursor.execute("PRAGMA foreign_keys = OFF")
        conn.commit()
        
        # 获取所有表名
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("开始清空数据库...")
        
        # 清空每个表的数据
        for table in tables:
            table_name = table[0]
            # 跳过sqlite内部表
            if not table_name.startswith('sqlite_'):
                cursor.execute(f"DELETE FROM {table_name}")
                print(f"已清空表: {table_name}")
                
                # 重置自增ID（如果表使用自增ID）
                try:
                    cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")
                    if cursor.rowcount > 0:
                        print(f"已重置表 {table_name} 的自增ID")
                except sqlite3.OperationalError:
                    # 某些表可能没有使用sqlite_sequence
                    pass
        
        # 启用外键约束
        cursor.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        
        conn.close()
        print("数据库清空完成")
        return True
        
    except Exception as e:
        print(f"清空数据库时出错: {e}")
        return False

if __name__ == "__main__":
    confirm = input("确定要清空数据库中的所有数据吗？(此操作不可恢复) (y/N): ")
    if confirm.lower() == 'y':
        if clear_database():
            print("✓ 数据库清空成功")
        else:
            print("✗ 数据库清空失败")
    else:
        print("取消清空操作")