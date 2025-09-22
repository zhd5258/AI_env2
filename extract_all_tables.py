#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 20:40:25
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 20:46:14
# 文件相对于项目的路径   : \AI_env2\extract_all_tables.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
提取并展示PDF中所有表格的脚本
用于提取指定PDF文件中的所有表格并保存结果
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from modules.table_analyzer import TableAnalyzer


def save_all_tables():
    """提取并保存所有表格"""
    # 指定要分析的PDF文件路径
    pdf_path = project_root / 'temp_uploads' / 'tender_招标文件正文.pdf'

    # 检查文件是否存在
    if not pdf_path.exists():
        print(f'错误: 找不到文件 {pdf_path}')
        return

    print(f'正在分析文件: {pdf_path}')

    # 创建表格分析器实例
    analyzer = TableAnalyzer(str(pdf_path))

    # 提取所有表格（不经过过滤）
    print('正在提取表格...')
    all_tables = analyzer._extract_all_tables()

    if not all_tables:
        print('未找到任何表格')
        return

    print(f'总共找到 {len(all_tables)} 个原始表格')

    # 尝试合并表格
    print('正在合并跨页表格...')
    merged_tables = analyzer._merge_cross_page_tables(all_tables)
    print(f'合并后得到 {len(merged_tables)} 个表格')

    # 转换为结构化格式（所有合并后的表格）
    print('正在转换为结构化格式...')
    structured_tables = analyzer.convert_to_structured_format(merged_tables)

    # 保存结果到文件
    output_path = project_root / 'all_extracted_tables.json'
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structured_tables, f, ensure_ascii=False, indent=2)
        print(f'所有表格已保存到: {output_path}')
    except Exception as e:
        print(f'保存结果时出错: {e}')

    # 同时保存原始表格信息
    raw_output_path = project_root / 'raw_extracted_tables.json'
    try:
        with open(raw_output_path, 'w', encoding='utf-8') as f:
            json.dump(merged_tables, f, ensure_ascii=False, indent=2)
        print(f'原始表格信息已保存到: {raw_output_path}')
    except Exception as e:
        print(f'保存原始表格信息时出错: {e}')

    # 显示一些示例表格
    print('\n示例表格:')
    print('=' * 50)

    for i, table in enumerate(structured_tables[:3]):  # 显示前3个表格
        print(f'表格 {i + 1}:')
        print(f'  列数: {len(table["headers"])}')
        print(f'  行数: {len(table["rows"])}')
        print('  表头:', table['headers'][:5])  # 只显示前5个表头
        print('  数据示例:')

        # 显示前2行数据作为示例
        for j, row in enumerate(table['rows'][:2]):
            # 只显示前3个字段的值
            keys = list(row.keys())[:3]
            sample_row = {k: row[k] for k in keys}
            print(f'    行 {j + 1}: {sample_row}')

        if len(table['rows']) > 2:
            print(f'    ... 还有 {len(table["rows"]) - 2} 行数据')

        print('-' * 30)


if __name__ == '__main__':
    save_all_tables()
