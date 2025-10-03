#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 17:57:17
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 17:57:20
#文件相对于项目的路径   : \AI_env2\test\test_extraction.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
import os
import sys
from pathlib import Path

# 将项目根目录添加到sys.path，以便导入模块
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.bidder_name_extractor import extract_bidder_name_from_file_after_analysis
from modules.md_price_extractor import MDPriceExtractor

def test_extraction():
    """
    测试投标人名称和投标价格提取功能。
    """
    # 定义测试文件路径
    md_file_path = r'd:\user\PythonProject\AI_env2\temp_md\江苏中车云汇科技有限公司投标文件.md'
    
    # 验证文件是否存在
    if not os.path.exists(md_file_path):
        print(f"错误: 测试文件不存在: {md_file_path}")
        return
    
    print(f"开始测试文件: {md_file_path}\n")
    
    # 1. 测试投标人名称提取
    print("1. 正在测试投标人名称提取...")
    bidder_name = extract_bidder_name_from_file_after_analysis(md_file_path)
    if bidder_name:
        print(f"✓ 提取成功: {bidder_name}")
    else:
        print("✗ 提取失败: 未能找到有效的投标人名称")
    
    # 2. 测试投标价格提取
    print("\n2. 正在测试投标价格提取...")
    price_extractor = MDPriceExtractor()
    price = price_extractor.extract_price_from_md_file(md_file_path)
    if price is not None:
        print(f"✓ 提取成功: {price:.2f} 元")
    else:
        print("✗ 提取失败: 未能找到有效的投标总价")
    
    # 3. 测试增强的表格处理功能
    print("\n3. 正在测试增强的表格处理功能...")
    try:
        # 读取文件内容
        with open(md_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 查找包含投标一览表的区域
        target_sections = price_extractor._locate_bid_summary_sections(content)
        if target_sections:
            print(f"✓ 找到 {len(target_sections)} 个投标一览表区域")
            
            # 测试表格解析功能
            for i, section in enumerate(target_sections):
                print(f"  正在分析第 {i+1} 个区域的表格...")
                table_data = price_extractor._parse_markdown_table(section)
                if table_data:
                    print(f"  ✓ 成功解析表格，包含 {len(table_data)} 行数据")
                    
                    # 显示表头
                    if table_data:
                        headers = list(table_data[0].keys())
                        print(f"    表头: {', '.join(headers)}")
                        
                        # 尝试从结构化表格中提取价格
                        table_price = price_extractor._extract_price_from_structured_table(table_data)
                        if table_price:
                            print(f"    ✓ 从结构化表格中提取到价格: {table_price:.2f} 元")
                        else:
                            print(f"    ✗ 未能从结构化表格中提取到价格")
                else:
                    print(f"  ✗ 未能解析第 {i+1} 个区域的表格")
        else:
            print("✗ 未能找到投标一览表区域")
    except Exception as e:
        print(f"✗ 测试增强表格处理功能时出错: {e}")
    
    print("\n测试完成。")

if __name__ == '__main__':
    test_extraction()
