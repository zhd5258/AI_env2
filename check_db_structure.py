import sqlite3
import os

def check_db_structure():
    # 连接到数据库
    db_path = './tender_evaluation.db'
    if not os.path.exists(db_path):
        print("数据库文件不存在")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查scoring_rule表结构
    try:
        cursor.execute("PRAGMA table_info(scoring_rule)")
        columns = cursor.fetchall()
        print("scoring_rule 表结构:")
        for col in columns:
            print(f"  {col[1]} ({col[2]}) {'PRIMARY KEY' if col[5] else ''} {'NOT NULL' if col[3] else ''}")
    except Exception as e:
        print(f"查询表结构时出错: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_db_structure()