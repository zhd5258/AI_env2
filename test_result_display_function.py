#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试项目1的结果展示功能
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.result_display import ResultDisplay

def test_result_display():
    """
    测试项目1的结果展示功能
    """
    print("测试项目1的结果展示功能")
    print("=" * 50)
    
    try:
        # 创建结果展示对象
        display = ResultDisplay(project_id=1)
        table_data = display.generate_multi_level_table()
        
        print("表头信息:")
        headers = table_data['headers']
        for i, header_row in enumerate(headers):
            print(f"  第{i+1}行: {header_row}")
            
        print("\n数据信息:")
        data = table_data['data']
        bidders = table_data['bidders']
        print(f"  投标方数量: {len(bidders)}")
        print(f"  数据行数: {len(data)}")
        
        for i, row in enumerate(data):
            print(f"  数据行 {i+1}: {row}")
            
        print("\n详细分析:")
        # 检查表头结构
        if len(headers) >= 2:
            print(f"  表头行数: {len(headers)}")
            print(f"  第一行表头列数: {len(headers[0])}")
            print(f"  第二行表头列数: {len(headers[1])}")
            
        # 检查数据结构
        if data:
            print(f"  数据行的列数: {[len(row) for row in data]}")
            
        # 检查是否列数匹配
        if len(headers) >= 2 and data:
            header_cols = len(headers[1])  # 以第二行表头为准
            data_cols = [len(row) for row in data]
            print(f"  表头列数: {header_cols}")
            print(f"  数据列数: {data_cols}")
            if all(col_count == header_cols for col_count in data_cols):
                print("  ✓ 表头和数据列数匹配")
            else:
                print("  ✗ 表头和数据列数不匹配")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_result_display()