import sqlite3

# 连接到数据库
conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()

# 清空所有表的数据
tables = [
    'score_modification_history',
    'project_audit_log',
    'analysis_result',
    'scoring_rule',
    'bid_document',
    'tender_project',
]

for table in tables:
    try:
        cursor.execute(f'DELETE FROM {table}')
        print(f'已清空表 {table}')
    except sqlite3.Error as e:
        print(f'清空表 {table} 时出错: {e}')

# 重置自增ID
for table in tables:
    try:
        cursor.execute(f'DELETE FROM sqlite_sequence WHERE name="{table}"')
        print(f'已重置表 {table} 的自增ID')
    except sqlite3.Error as e:
        print(f'重置表 {table} 的自增ID时出错: {e}')

# 提交更改并关闭连接
conn.commit()
conn.close()

print('数据库清空完成')
