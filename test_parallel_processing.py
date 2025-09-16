#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试并行处理优化效果
"""

import sys
import os
import time
import multiprocessing

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 将函数定义移到全局作用域以便pickle
def cpu_intensive_task(n):
    # 计算斐波那契数列
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a

def test_cpu_cores():
    """
    测试CPU核心数
    """
    print("测试CPU核心数...")
    print("=" * 60)
    
    # 获取CPU核心数
    cpu_count = os.cpu_count()
    print(f"逻辑CPU核心数: {cpu_count}")
    
    # 获取物理CPU核心数（在Linux系统上）
    try:
        with open('/proc/cpuinfo') as f:
            info = f.read()
            physical_ids = set()
            core_ids = set()
            for line in info.split('\n'):
                if line.startswith('physical id'):
                    physical_ids.add(line.split(':')[1].strip())
                elif line.startswith('core id'):
                    core_ids.add(line.split(':')[1].strip())
            
            print(f"物理CPU数量: {len(physical_ids)}")
            print(f"物理核心数: {len(core_ids)}")
    except:
        print("无法获取物理CPU信息")
    
    print()

def test_concurrent_processing():
    """
    测试并发处理能力
    """
    print("测试并发处理能力...")
    print("=" * 60)
    
    # 串行处理
    start_time = time.time()
    results_serial = []
    for i in range(10):
        result = cpu_intensive_task(10000)
        results_serial.append(result)
    serial_time = time.time() - start_time
    
    # 并行处理
    start_time = time.time()
    with multiprocessing.Pool(processes=os.cpu_count()) as pool:
        results_parallel = pool.map(cpu_intensive_task, [10000] * 10)
    parallel_time = time.time() - start_time
    
    print(f"串行处理时间: {serial_time:.4f} 秒")
    print(f"并行处理时间: {parallel_time:.4f} 秒")
    print(f"性能提升: {serial_time/parallel_time:.2f}x")
    print()

if __name__ == "__main__":
    test_cpu_cores()
    test_concurrent_processing()
    print("测试完成!")