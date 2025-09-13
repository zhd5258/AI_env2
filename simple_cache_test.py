#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化版测试脚本，验证PDF缓存功能
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor
import time

def simple_cache_test():
    """
    简化版PDF缓存功能测试
    """
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\广东创智智能装备有限公司投标文件.pdf"
    
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("简化版PDF缓存功能测试")
    print("=" * 50)
    
    # 1. 第一次处理（无缓存）
    print("1. 第一次处理PDF（无缓存）...")
    start_time = time.time()
    
    processor1 = PDFProcessor(bid_file_path)
    processor1.clear_cache()  # 确保没有缓存
    
    pages1 = processor1.process_pdf_per_page()
    time1 = time.time() - start_time
    
    print(f"   处理时间: {time1:.2f}秒")
    print(f"   提取页数: {len(pages1)}页")
    
    # 2. 第二次处理（使用缓存）
    print("\n2. 第二次处理PDF（使用缓存）...")
    start_time = time.time()
    
    processor2 = PDFProcessor(bid_file_path)
    pages2 = processor2.process_pdf_per_page()
    time2 = time.time() - start_time
    
    print(f"   处理时间: {time2:.2f}秒")
    print(f"   提取页数: {len(pages2)}页")
    
    # 3. 性能对比
    print("\n3. 性能对比...")
    if time2 < time1:
        speedup = time1 / time2
        print(f"   缓存加速比: {speedup:.2f}x")
        print("   ✓ 缓存功能正常工作")
    else:
        print("   ! 缓存效果不明显（可能首次已缓存）")
    
    # 4. 清理缓存
    print("\n4. 清理缓存...")
    processor2.clear_cache()
    print("   ✓ 缓存已清理")

if __name__ == "__main__":
    simple_cache_test()