import sqlite3

conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()

# 检查项目66的投标文件错误信息
cursor.execute('SELECT id, bidder_name, error_message FROM bid_document WHERE project_id = 66')
bids = cursor.fetchall()
print('项目66的投标文件错误信息:')
for b in bids:
    print(f'  投标文件ID: {b[0]}, 投标人: {b[1]}')
    print(f'    错误信息: {b[2]}')

conn.close()