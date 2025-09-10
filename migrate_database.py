import sqlite3
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def migrate_database():
    """
    对数据库进行迁移，以支持新的列和功能。
    """
    db_path = 'tender_evaluation.db'
    try:
        # 连接到SQLite数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        logging.info(f"成功连接到数据库: {db_path}")

        # 1. 检查并向 analysis_result 表添加 extracted_price 列
        cursor.execute("PRAGMA table_info(analysis_result)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'extracted_price' not in columns:
            logging.info("在 analysis_result 表中未找到 'extracted_price' 列，正在添加...")
            cursor.execute("ALTER TABLE analysis_result ADD COLUMN extracted_price FLOAT")
            logging.info("成功添加 'extracted_price' 列。")
        else:
            logging.info("'extracted_price' 列已存在于 analysis_result 表中，无需操作。")

        # 提交事务
        conn.commit()
        logging.info("数据库迁移成功完成。")

    except sqlite3.Error as e:
        logging.error(f"数据库迁移过程中发生错误: {e}")
    finally:
        if conn:
            conn.close()
            logging.info("数据库连接已关闭。")

if __name__ == '__main__':
    migrate_database()
