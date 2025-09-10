#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-07 10:48:50
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-07 10:48:53
# 文件相对于项目的路径   : \AI_env2\process_excel.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import pandas as pd
import json


def process_excel_data():
    # 读取Excel文件
    df = pd.read_excel('评价.xlsx')

    # 获取所有投标方
    bidders = df['投标方'].dropna().tolist()

    # 计算每个投标方的总分
    bidder_scores = {}
    current_bidder = None
    current_total = 0

    for i, row in df.iterrows():
        # 如果这一行有投标方名称，说明是新的投标方
        if pd.notna(row['投标方']) and row['投标方'] != '':
            # 保存上一个投标方的总分
            if current_bidder is not None:
                bidder_scores[current_bidder] = current_total

            # 开始计算新投标方的总分
            current_bidder = row['投标方']
            current_total = 0

        # 如果这一行有得分，累加到当前投标方的总分
        if pd.notna(row['得分']):
            try:
                # 处理"废标"情况
                if row['得分'] == '废标':
                    current_total = '废标'
                    break
                else:
                    current_total += float(row['得分'])
            except:
                pass

    # 保存最后一个投标方的总分
    if current_bidder is not None and current_bidder not in bidder_scores:
        bidder_scores[current_bidder] = current_total

    # 按总分排序
    sorted_bidders = sorted(
        bidder_scores.items(),
        key=lambda x: x[1] if x[1] != '废标' else -1,
        reverse=True,
    )

    # 添加排名
    results = []
    for i, (bidder, score) in enumerate(sorted_bidders):
        results.append(
            {
                'rank': i + 1,
                'bidder_name': bidder,
                'total_score': score,
                'detailed_scores': [],  # 这里可以添加详细的评分项
            }
        )

    return results


if __name__ == '__main__':
    results = process_excel_data()
    print(json.dumps(results, ensure_ascii=False, indent=2))
