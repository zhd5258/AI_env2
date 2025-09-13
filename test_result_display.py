#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试结果展示功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.result_display import ResultDisplay, print_multi_level_table, print_summary_table

def test_result_display():
    """
    测试结果展示功能
    """
    print("测试结果展示功能")
    print("=" * 50)
    
    try:
        # 使用之前的测试项目ID
        project_id = 5
        
        # 创建结果展示对象
        display = ResultDisplay(project_id)
        
        # 生成多层表头表格数据
        print("1. 生成多层表头表格数据...")
        table_data = display.generate_multi_level_table()
        
        print("   表头:")
        for i, header_row in enumerate(table_data['headers']):
            print(f"     第{i+1}行: {header_row}")
            
        print("   数据行数:", len(table_data['data']))
        if table_data['data']:
            print("   第一行数据:", table_data['data'][0])
            
        # 获取汇总数据
        print("\n2. 获取汇总数据...")
        summary_data = display.get_summary_data()
        print("   汇总数据项数:", len(summary_data))
        if summary_data:
            print("   第一项数据:", summary_data[0])
            
        # 打印多层表头表格
        print("\n3. 打印多层表头表格...")
        print_multi_level_table(project_id)
        
        # 打印汇总表格
        print("\n4. 打印汇总表格...")
        print_summary_table(project_id)
        
        print("\n" + "=" * 50)
        print("结果展示功能测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_result_display()