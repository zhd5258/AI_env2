#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:54:16
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:54:20
# 文件相对于项目的路径   : \AI_ENV2\tools\upload_performance_analyzer.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
上传性能分析工具
用于分析和优化文件上传性能
"""

import time
import os
import shutil
import tempfile
from pathlib import Path


def analyze_file_save_performance():
    """分析文件保存性能"""
    print('分析文件保存性能...')

    # 创建测试文件
    test_data = os.urandom(10 * 1024 * 1024)  # 10MB

    # 测试不同的文件保存方法
    methods = {
        '直接写入': test_direct_write,
        '分块写入(8KB)': lambda data: test_chunked_write(data, 8192),
        '分块写入(64KB)': lambda data: test_chunked_write(data, 65536),
        '分块写入(1MB)': lambda data: test_chunked_write(data, 1024 * 1024),
        'shutil.copyfileobj': test_copyfileobj,
    }

    results = {}
    for method_name, method_func in methods.items():
        print(f'  测试 {method_name}...')
        start_time = time.time()
        try:
            method_func(test_data)
            end_time = time.time()
            elapsed = end_time - start_time
            results[method_name] = elapsed
            print(f'    完成时间: {elapsed:.4f} 秒')
        except Exception as e:
            print(f'    失败: {e}')
            results[method_name] = float('inf')

    return results


def test_direct_write(data):
    """直接写入方法"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name
    os.unlink(tmp_path)


def test_chunked_write(data, chunk_size):
    """分块写入方法"""
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        for i in range(0, len(data), chunk_size):
            chunk = data[i : i + chunk_size]
            tmp.write(chunk)
        tmp_path = tmp.name
    os.unlink(tmp_path)


def test_copyfileobj(data):
    """shutil.copyfileobj方法"""
    with tempfile.NamedTemporaryFile(delete=False) as src:
        src.write(data)
        src_path = src.name

    with open(src_path, 'rb') as src, tempfile.NamedTemporaryFile(delete=False) as dst:
        shutil.copyfileobj(src, dst)
        dst_path = dst.name

    os.unlink(src_path)
    os.unlink(dst_path)


def check_disk_performance():
    """检查磁盘性能"""
    print('\n检查磁盘性能...')

    # 测试磁盘写入速度
    test_data = os.urandom(100 * 1024 * 1024)  # 100MB

    start_time = time.time()
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(test_data)
        tmp_path = tmp.name
    end_time = time.time()

    write_time = end_time - start_time
    write_speed = (100 * 8) / write_time  # Mbps

    # 测试磁盘读取速度
    start_time = time.time()
    with open(tmp_path, 'rb') as f:
        f.read()
    end_time = time.time()

    read_time = end_time - start_time
    read_speed = (100 * 8) / read_time  # Mbps

    # 清理
    os.unlink(tmp_path)

    print(f'  磁盘写入速度: {write_speed:.2f} Mbps')
    print(f'  磁盘读取速度: {read_speed:.2f} Mbps')

    return write_speed, read_speed


def check_memory_usage():
    """检查内存使用情况"""
    print('\n检查内存使用情况...')

    try:
        import psutil

        process = psutil.Process()
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
        print(f'  当前内存使用: {memory_mb:.2f} MB')
        return memory_mb
    except ImportError:
        print('  无法检查内存使用情况 (需要安装psutil)')
        return 0


def analyze_upload_directory():
    """分析上传目录"""
    print('\n分析上传目录...')

    upload_dir = Path('uploads')
    if not upload_dir.exists():
        print('  上传目录不存在')
        return

    # 统计文件数量和大小
    file_count = 0
    total_size = 0

    for file_path in upload_dir.rglob('*'):
        if file_path.is_file():
            file_count += 1
            total_size += file_path.stat().st_size

    print(f'  文件数量: {file_count}')
    print(f'  总大小: {total_size / (1024 * 1024):.2f} MB')

    # 检查磁盘剩余空间
    disk_usage = shutil.disk_usage('.')
    free_space_gb = disk_usage.free / (1024**3)
    print(f'  磁盘剩余空间: {free_space_gb:.2f} GB')


def main():
    """主函数"""
    print('=' * 50)
    print('AI评标系统上传性能分析工具')
    print('=' * 50)

    # 分析文件保存性能
    performance_results = analyze_file_save_performance()

    # 检查磁盘性能
    write_speed, read_speed = check_disk_performance()

    # 检查内存使用
    memory_usage = check_memory_usage()

    # 分析上传目录
    analyze_upload_directory()

    print('\n' + '=' * 50)
    print('性能分析结果:')
    print('=' * 50)

    print('文件保存方法性能对比:')
    # 按时间排序
    sorted_results = sorted(performance_results.items(), key=lambda x: x[1])
    for method_name, elapsed in sorted_results:
        if elapsed != float('inf'):
            print(f'  {method_name}: {elapsed:.4f} 秒')
        else:
            print(f'  {method_name}: 失败')

    print('\n磁盘性能:')
    print(f'  写入速度: {write_speed:.2f} Mbps')
    print(f'  读取速度: {read_speed:.2f} Mbps')

    if memory_usage > 0:
        print(f'\n内存使用: {memory_usage:.2f} MB')

    print('\n' + '=' * 50)
    print('优化建议:')
    print('=' * 50)

    # 根据测试结果给出建议
    best_method = sorted_results[0][0] if sorted_results else '未知'
    print(f'推荐的文件保存方法: {best_method}')

    if write_speed < 100:  # 如果磁盘写入速度低于100Mbps
        print('⚠ 磁盘性能可能影响上传速度，建议:')
        print('  1. 使用SSD硬盘')
        print('  2. 清理磁盘空间')
        print('  3. 检查磁盘健康状态')

    if memory_usage > 500:  # 如果内存使用超过500MB
        print('⚠ 内存使用较高，建议:')
        print('  1. 优化文件处理流程')
        print('  2. 增加系统内存')
        print('  3. 调整Flask配置')

    print('=' * 50)


if __name__ == '__main__':
    main()
