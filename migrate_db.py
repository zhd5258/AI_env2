import sqlite3

def migrate_database():
    """向analysis_result表添加dynamic_scores字段"""
    try:
        # 连接到数据库
        conn = sqlite3.connect('./tender_evaluation.db')
        cursor = conn.cursor()
        
        # 检查是否已经存在dynamic_scores字段
        cursor.execute("PRAGMA table_info(analysis_result)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        if 'dynamic_scores' in column_names:
            print("dynamic_scores字段已存在，无需添加")
            return True
            
        # 添加dynamic_scores字段
        cursor.execute("ALTER TABLE analysis_result ADD COLUMN dynamic_scores JSON")
        conn.commit()
        print("成功添加dynamic_scores字段到analysis_result表")
        return True
        
    except sqlite3.Error as e:
        print(f"数据库迁移失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()