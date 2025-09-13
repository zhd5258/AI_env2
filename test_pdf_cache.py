#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试PDF文本缓存功能
"""

import sys
import os
import shutil

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_pdf_cache():
    """
    测试PDF文本缓存功能
    """
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\广东创智智能装备有限公司投标文件.pdf"
    
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("开始测试PDF文本缓存功能")
    print("=" * 80)
    
    try:
        # 1. 第一次处理PDF文件（无缓存）
        print("1. 第一次处理PDF文件（无缓存）...")
        processor1 = PDFProcessor(bid_file_path)
        
        # 清理可能存在的缓存
        processor1.clear_cache()
        
        print("   提取PDF文本...")
        pages1 = processor1.process_pdf_per_page()
        
        if not pages1 or not any(pages1):
            print("   ✗ 未能提取到PDF文本")
            return
        else:
            print(f"   ✓ 成功提取到 {len(pages1)} 页文本")
            non_empty_pages = sum(1 for page in pages1 if page.strip())
            print(f"   其中非空页面数: {non_empty_pages}")
        
        # 2. 第二次处理相同PDF文件（使用缓存）
        print("\n2. 第二次处理相同PDF文件（使用缓存）...")
        processor2 = PDFProcessor(bid_file_path)
        
        print("   提取PDF文本...")
        pages2 = processor2.process_pdf_per_page()
        
        if not pages2 or not any(pages2):
            print("   ✗ 未能提取到PDF文本")
            return
        else:
            print(f"   ✓ 成功提取到 {len(pages2)} 页文本")
            non_empty_pages = sum(1 for page in pages2 if page.strip())
            print(f"   其中非空页面数: {non_empty_pages}")
        
        # 3. 验证两次提取结果一致性
        print("\n3. 验证两次提取结果一致性...")
        if len(pages1) == len(pages2):
            print("   ✓ 两次提取的页面数一致")
            
            # 比较前几页内容
            pages_to_check = min(3, len(pages1))
            is_consistent = True
            for i in range(pages_to_check):
                if pages1[i] != pages2[i]:
                    print(f"   ✗ 第{i+1}页内容不一致")
                    is_consistent = False
                    break
            
            if is_consistent:
                print(f"   ✓ 前{pages_to_check}页内容一致")
        else:
            print("   ✗ 两次提取的页面数不一致")
        
        # 4. 测试缓存清理功能
        print("\n4. 测试缓存清理功能...")
        processor3 = PDFProcessor(bid_file_path)
        processor3.clear_cache()
        print("   ✓ 缓存清理完成")
        
        # 5. 验证缓存目录
        print("\n5. 验证缓存目录...")
        cache_dir = "temp_pdf_cache"
        if os.path.exists(cache_dir):
            cache_files = os.listdir(cache_dir)
            print(f"   缓存目录存在，包含 {len(cache_files)} 个文件")
        else:
            print("   缓存目录不存在")
            
        print("\n" + "=" * 80)
        print("PDF文本缓存功能测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()

def test_cache_clear_all():
    """
    测试清理所有缓存功能
    """
    print("\n测试清理所有缓存功能...")
    
    try:
        processor = PDFProcessor("")  # 传入空路径仅用于测试缓存功能
        processor.clear_all_cache()
        print("   ✓ 所有缓存清理完成")
    except Exception as e:
        print(f"清理缓存时出错: {e}")

if __name__ == "__main__":
    test_pdf_cache()
    test_cache_clear_all()