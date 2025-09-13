import sqlite3

# 连接到数据库
conn = sqlite3.connect('./tender_evaluation.db')
cursor = conn.cursor()

# 查询所有分析结果
print("所有分析结果:")
cursor.execute("SELECT bidder_name, total_score, price_score, extracted_price FROM analysis_result;")
results = cursor.fetchall()
for r in results:
    print(r)

# 查询盐城大德相关数据
print("\n盐城大德相关数据:")
cursor.execute("SELECT bidder_name, total_score, price_score, extracted_price FROM analysis_result WHERE bidder_name LIKE '%盐城大德%';")
yancheng_results = cursor.fetchall()
for r in yancheng_results:
    print(r)

# 查询武汉新国铁博达科技有限公司相关数据
print("\n武汉新国铁博达科技有限公司相关数据:")
cursor.execute("SELECT bidder_name, total_score, price_score, extracted_price FROM analysis_result WHERE bidder_name LIKE '%武汉新国铁博达科技有限公司%';")
wuhan_results = cursor.fetchall()
for r in wuhan_results:
    print(r)

# 关闭连接
conn.close()