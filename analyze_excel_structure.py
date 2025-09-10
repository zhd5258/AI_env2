#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-07 12:29:28
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-07 12:29:30
# 文件相对于项目的路径   : \AI_env2\analyze_excel_structure.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import pandas as pd

# 读取Excel文件，查看其结构
df = pd.read_excel('评价.xlsx')

# 显示完整的数据结构
print('Excel文件完整数据:')
print(df.to_string())

# 分析投标方和评分项的结构
print('\n=== 投标方信息 ===')
bidders = df[df['投标方'].notna()]['投标方'].tolist()
for i, bidder in enumerate(bidders):
    print(f'{i + 1}. {bidder}')

print('\n=== 评分项结构 ===')
# 找出评分项（没有投标方但有评价项目的行）
scoring_items = df[(df['投标方'].isna()) & (df['评价项目'].notna())]
for idx, row in scoring_items.iterrows():
    print(f'评分项: {row["评价项目"]}, 满分: {row["满分分值"]}')

print('\n=== 评标办法表格结构分析 ===')
# 分析如何构建正确的评标办法表格
current_bidder = None
for idx, row in df.iterrows():
    if pd.notna(row['投标方']) and row['投标方'] != '':
        current_bidder = row['投标方']
        print(f'\n投标方: {current_bidder}')
    elif pd.notna(row['评价项目']) and current_bidder:
        print(
            f'  评分项: {row["评价项目"]}, 满分: {row["满分分值"]}, 得分: {row["得分"]}'
        )
