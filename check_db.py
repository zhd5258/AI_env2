import sqlite3

conn = sqlite3.connect('tender_evaluation.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(analysis_result)')
columns = cursor.fetchall()
print('analysis_result表结构:')
for col in columns:
    print('  {0} ({1})'.format(col[1], col[2]))
conn.close()