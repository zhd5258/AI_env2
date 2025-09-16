#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试PDF处理并行优化效果
"""

import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def simulate_pdf_page_processing(page_count):
    """
    模拟PDF页面处理任务
    """
    print(f"开始处理包含 {page_count} 页的PDF文件...")
    
    # 模拟串行处理
    start_time = time.time()
    for i in range(page_count):
        # 模拟每页处理需要的时间
        time.sleep(0.1)  # 模拟OCR处理耗时
    serial_time = time.time() - start_time
    
    # 模拟并行处理
    start_time = time.time()
    max_workers = min(page_count, os.cpu_count() or 1)
    
    def process_page(page_num):
        time.sleep(0.1)  # 模拟每页处理需要的时间
        return f"Page {page_num} processed"
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_page, i) for i in range(page_count)]
        results = [future.result() for future in futures]
    
    parallel_time = time.time() - start_time
    
    print(f"  串行处理时间: {serial_time:.2f} 秒")
    print(f"  并行处理时间: {parallel_time:.2f} 秒")
    print(f"  性能提升: {serial_time/parallel_time:.2f}x")
    print()
    
    return serial_time, parallel_time

def test_multiple_pdfs():
    """
    测试多个PDF文件的并行处理
    """
    print("测试多个PDF文件的并行处理...")
    print("=" * 60)
    
    pdf_sizes = [5, 10, 15, 20]  # 每个PDF文件的页数
    
    # 串行处理多个PDF
    start_time = time.time()
    for size in pdf_sizes:
        # 模拟串行处理每个PDF
        for i in range(size):
            time.sleep(0.05)  # 模拟每页处理时间
    serial_time = time.time() - start_time
    
    # 并行处理多个PDF
    start_time = time.time()
    max_workers = min(len(pdf_sizes), os.cpu_count() or 1)
    
    def process_pdf(pdf_size):
        for i in range(pdf_size):
            time.sleep(0.05)  # 模拟每页处理时间
        return f"PDF with {pdf_size} pages processed"
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(process_pdf, size) for size in pdf_sizes]
        results = [future.result() for future in futures]
    
    parallel_time = time.time() - start_time
    
    print(f"串行处理 {len(pdf_sizes)} 个PDF文件时间: {serial_time:.2f} 秒")
    print(f"并行处理 {len(pdf_sizes)} 个PDF文件时间: {parallel_time:.2f} 秒")
    print(f"性能提升: {serial_time/parallel_time:.2f}x")
    print()

if __name__ == "__main__":
    print("测试PDF处理并行优化效果")
    print("=" * 60)
    
    # 测试不同页数的PDF处理
    for page_count in [10, 20, 30]:
        simulate_pdf_page_processing(page_count)
    
    test_multiple_pdfs()
    
    print("测试完成!")