#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-25 07:41:59
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-25 07:42:02
# 文件相对于项目的路径   : \AI_ENV2\tools\test_display.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
测试工具脚本显示逻辑的简单脚本
"""

import json
import tkinter as tk
from tkinter import ttk

# 模拟从数据库获取的detailed_scores数据
test_data_str = """[{"Child_Item_Name": "企业证书，认证体系", "max_score": 5, "score": 5.0, "reason": "测试数据"}, 
{"Child_Item_Name": "标书的完整性", "max_score": 5, "score": 4.0, "reason": "测试数据2"}]"""


def test_display():
    # 创建主窗口
    root = tk.Tk()
    root.title('测试显示')
    root.geometry('800x600')

    # 创建Treeview来显示详细评分
    tree = ttk.Treeview(
        root,
        columns=('规则名称', '满分', '得分', '理由'),
        show='headings',
    )
    tree.heading('规则名称', text='规则名称')
    tree.heading('满分', text='满分')
    tree.heading('得分', text='得分')
    tree.heading('理由', text='理由')

    # 设置列宽
    tree.column('规则名称', width=200)
    tree.column('满分', width=80, anchor=tk.CENTER)
    tree.column('得分', width=80, anchor=tk.CENTER)
    tree.column('理由', width=400)

    # 添加滚动条
    tree_scroll_y = ttk.Scrollbar(root, orient=tk.VERTICAL, command=tree.yview)
    tree_scroll_x = ttk.Scrollbar(root, orient=tk.HORIZONTAL, command=tree.xview)
    tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

    # 布局
    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
    tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)

    # 解析并显示数据
    try:
        detailed_scores = json.loads(test_data_str)
        if isinstance(detailed_scores, list):
            for score_item in detailed_scores:
                if isinstance(score_item, dict):
                    rule_name = score_item.get('Child_Item_Name', '未知规则')
                    max_score = score_item.get('max_score', 0)
                    score = score_item.get('score', 0)
                    reason = score_item.get('reason', '')

                    # 如果是定性规则，显示结果而不是分数
                    if 'result' in score_item:
                        score = score_item.get('result', '未知')
                        reason = score_item.get('reason', '')

                    tree.insert(
                        '', tk.END, values=(rule_name, max_score, score, reason)
                    )
    except Exception as e:
        print(f'Error: {e}')

    root.mainloop()


if __name__ == '__main__':
    test_display()
