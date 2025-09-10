import sqlite3

# 连接到数据库
conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()

# 将状态为processing的项目更新为error状态
cursor.execute("UPDATE tender_project SET status = 'error' WHERE status = 'processing'")
print(f"更新了 {cursor.rowcount} 个项目的状态")

# 将状态为pending的投标文件更新为error状态
cursor.execute("UPDATE bid_document SET processing_status = 'error' WHERE processing_status = 'pending'")
print(f"更新了 {cursor.rowcount} 个投标文件的状态")

# 提交更改并关闭连接
conn.commit()
conn.close()

print("数据库状态修复完成")