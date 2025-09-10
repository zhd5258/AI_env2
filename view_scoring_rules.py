#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:40:52
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-09-10 21:42:12
#文件相对于项目的路径   : \AI_env2\view_scoring_rules.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看评分规则文件内容的程序
"""

import json
import sys
import os


def view_scoring_rules(file_path):
    """查看评分规则文件内容"""
    if not os.path.exists(file_path):
        print(f'文件不存在: {file_path}')
        return

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)

        print(f'评分规则文件: {file_path}')
        print('=' * 60)
        print(f'共找到 {len(rules)} 条评分规则:\n')

        for i, rule in enumerate(rules, 1):
            print(f'{i}. 评分项: {rule.get("criteria_name", "未知")}')
            print(f'   分数: {rule.get("max_score", 0)}分')
            print(
                f'   是否价格规则: {"是" if rule.get("is_price_criteria", False) else "否"}'
            )
            if rule.get('description'):
                desc = rule['description']
                if len(desc) > 200:
                    desc = desc[:200] + '...'
                print(f'   描述: {desc}')
            print()

    except Exception as e:
        print(f'读取文件时出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    # 指定JSON文件路径
    json_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文_final_scoring_rules.json'

    # 如果通过命令行参数指定了文件路径，则使用该路径
    if len(sys.argv) > 1:
        json_file_path = sys.argv[1]

    view_scoring_rules(json_file_path)
