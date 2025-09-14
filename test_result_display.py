#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试结果展示模块是否能正确显示更新后的价格分和总分
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.result_display import ResultDisplay
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_result_display():
    """
    测试结果展示模块
    """
    print("开始测试结果展示模块...")
    
    # 测试项目ID为4
    project_id = 4
    
    # 创建结果展示对象
    result_display = ResultDisplay(project_id)
    
    try:
        # 获取汇总数据
        print("获取汇总数据...")
        summary_data = result_display.get_summary_data()
        
        print("=" * 80)
        print("汇总数据:")
        print("=" * 80)
        print(f'{"排名":>4} | {"投标人":>30} | {"价格分":>6} | {"总分":>6}')
        print("-" * 80)
        for item in summary_data:
            rank = item['rank']
            bidder_name = item['bidder_name']
            price_score = item['price_score']
            total_score = item['total_score']
            print(f'{rank:>4} | {bidder_name:>30} | {price_score:>6.2f} | {total_score:>6.2f}')
        print("=" * 80)
        
        # 获取详细表格数据
        print("\n获取详细表格数据...")
        table_data = result_display.generate_multi_level_table()
        
        print("\n表头:")
        for i, header_row in enumerate(table_data['headers']):
            print(f"  第{i+1}行: {header_row}")
            
        print("\n数据行:")
        for i, data_row in enumerate(table_data['data']):
            print(f"  第{i+1}行: {data_row}")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        result_display.session.close()

if __name__ == "__main__":
    test_result_display()