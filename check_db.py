import sqlite3

# 连接到数据库
conn = sqlite3.connect('./tender_evaluation.db')
cursor = conn.cursor()

# 查询analysis_result表结构
print("Current analysis_result table structure:")
cursor.execute('PRAGMA table_info(analysis_result)')
results = cursor.fetchall()
for r in results:
    print(r)

# 查询scoring_rule表结构
print("\nCurrent scoring_rule table structure:")
cursor.execute('PRAGMA table_info(scoring_rule)')
results = cursor.fetchall()
for r in results:
    print(r)

# 关闭连接
conn.close()