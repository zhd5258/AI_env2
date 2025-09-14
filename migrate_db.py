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
        else:
            # 添加dynamic_scores字段
            cursor.execute("ALTER TABLE analysis_result ADD COLUMN dynamic_scores JSON")
            conn.commit()
            print("成功添加dynamic_scores字段到analysis_result表")
        
        # 检查bid_document表是否已经存在新字段
        cursor.execute("PRAGMA table_info(bid_document)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]
        
        # 添加新字段到bid_document表
        new_columns = [
            ('price_extraction_attempts', 'INTEGER'),
            ('price_extraction_error', 'TEXT'),
            ('price_extracted', 'BOOLEAN')
        ]
        
        for column_name, column_type in new_columns:
            if column_name in column_names:
                print(f"{column_name}字段已存在，无需添加")
            else:
                cursor.execute(f"ALTER TABLE bid_document ADD COLUMN {column_name} {column_type}")
                conn.commit()
                print(f"成功添加{column_name}字段到bid_document表")
        
        return True
        
    except sqlite3.Error as e:
        print(f"数据库迁移失败: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate_database()