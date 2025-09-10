import sqlite3

conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()

# 检查项目66的分析结果
cursor.execute('SELECT COUNT(*) FROM analysis_result WHERE project_id = 66')
count = cursor.fetchone()[0]
print(f'项目66的分析结果数量: {count}')

# 检查项目66的投标文件状态
cursor.execute('SELECT id, bidder_name, processing_status FROM bid_document WHERE project_id = 66')
bids = cursor.fetchall()
print('项目66的投标文件状态:')
for b in bids:
    print(f'  投标文件ID: {b[0]}, 投标人: {b[1]}, 状态: {b[2]}')

# 检查项目66的状态
cursor.execute('SELECT id, name, status FROM tender_project WHERE id = 66')
project = cursor.fetchone()
if project:
    print(f'项目66状态: ID={project[0]}, 名称={project[1]}, 状态={project[2]}')
else:
    print('项目66不存在')

conn.close()