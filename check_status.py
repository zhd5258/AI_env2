import sqlite3

conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()

# 查看最近5个项目状态
cursor.execute('SELECT id, name, status FROM tender_project ORDER BY id DESC LIMIT 5')
projects = cursor.fetchall()
print('最近5个项目状态:')
for p in projects:
    print(f'  项目ID: {p[0]}, 名称: {p[1]}, 状态: {p[2]}')

# 查看最近项目的投标文件状态
if projects:
    latest_project_id = projects[0][0]
    print(f'\n项目ID {latest_project_id} 的投标文件状态:')
    cursor.execute('SELECT id, bidder_name, processing_status, error_message FROM bid_document WHERE project_id = ? ORDER BY id', (latest_project_id,))
    bid_docs = cursor.fetchall()
    for doc in bid_docs:
        print(f'  投标文件ID: {doc[0]}, 投标人: {doc[1]}, 状态: {doc[2]}')
        if doc[3]:
            print(f'    错误信息: {doc[3]}')

conn.close()