#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:59:58
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 12:00:01
# 文件相对于项目的路径   : \AI_ENV2\tools\lan_upload_diagnostic.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
局域网上传诊断工具
专门针对局域网环境的上传性能问题诊断
"""

import requests
import time
import os
import psutil
import threading
from pathlib import Path


def check_server_resources():
    """检查服务器资源使用情况"""
    print('检查服务器资源使用情况...')

    # CPU使用率
    cpu_percent = psutil.cpu_percent(interval=1)
    print(f'  CPU使用率: {cpu_percent}%')

    # 内存使用情况
    memory = psutil.virtual_memory()
    memory_percent = memory.percent
    memory_available_gb = memory.available / (1024**3)
    print(f'  内存使用率: {memory_percent}%')
    print(f'  可用内存: {memory_available_gb:.2f} GB')

    # 磁盘使用情况
    disk = psutil.disk_usage('/')
    disk_percent = (disk.used / disk.total) * 100
    disk_free_gb = disk.free / (1024**3)
    print(f'  磁盘使用率: {disk_percent:.1f}%')
    print(f'  磁盘剩余空间: {disk_free_gb:.2f} GB')

    return cpu_percent, memory_percent, disk_percent


class MonitorController:
    def __init__(self):
        self.stop = False


def monitor_server_during_upload(test_file_path):
    """在上传过程中监控服务器资源"""
    controller = MonitorController()

    def monitor():
        while not controller.stop:
            cpu = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory().percent
            print(f'    实时监控 - CPU: {cpu}%, 内存: {memory}%')
            time.sleep(1)

    monitor_thread = threading.Thread(target=monitor)
    monitor_thread.start()

    # 执行上传
    try:
        with open(test_file_path, 'rb') as f:
            files = {'tender_file': f}
            response = requests.post(
                'http://localhost:8000/api/init-upload', files=files, timeout=300
            )
        return response
    finally:
        controller.stop = True
        monitor_thread.join()


def test_upload_with_monitoring(file_size_mb=10):
    """测试上传并监控服务器状态"""
    print(f'\n测试 {file_size_mb}MB 文件上传并监控服务器状态...')

    # 创建测试文件
    test_file = f'lan_test_file_{file_size_mb}mb.bin'
    with open(test_file, 'wb') as f:
        f.write(os.urandom(file_size_mb * 1024 * 1024))

    try:
        print('  上传前服务器状态:')
        check_server_resources()

        print('  开始上传并监控...')
        start_time = time.time()
        response = monitor_server_during_upload(test_file)
        end_time = time.time()

        upload_time = end_time - start_time
        upload_speed = (file_size_mb * 8) / upload_time

        print('  上传完成:')
        print(f'    时间: {upload_time:.2f} 秒')
        print(f'    速度: {upload_speed:.2f} Mbps')
        print(f'    状态码: {response.status_code}')

        print('  上传后服务器状态:')
        check_server_resources()

        return upload_time, upload_speed, response.status_code
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)


def check_flask_configuration():
    """检查Flask配置"""
    print('\n检查Flask配置...')

    try:
        # 检查运行时配置
        response = requests.get('http://localhost:8000/api/runtime-config', timeout=10)
        if response.status_code == 200:
            config = response.json()
            print('  服务器运行时配置:')
            for key, value in config.items():
                print(f'    {key}: {value}')
        else:
            print(f'  无法获取服务器配置: {response.status_code}')
    except Exception as e:
        print(f'  检查服务器配置失败: {e}')


def check_upload_directory_status():
    """检查上传目录状态"""
    print('\n检查上传目录状态...')

    upload_dir = Path('uploads')
    if upload_dir.exists():
        # 统计文件数量和大小
        file_count = 0
        total_size = 0
        for file_path in upload_dir.rglob('*'):
            if file_path.is_file():
                file_count += 1
                total_size += file_path.stat().st_size

        print(f'  上传目录文件数: {file_count}')
        print(f'  上传目录总大小: {total_size / (1024 * 1024):.2f} MB')

        # 检查目录权限
        try:
            test_file = upload_dir / 'permission_test.tmp'
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print('  上传目录写入权限: 正常')
        except Exception as e:
            print(f'  上传目录写入权限: 异常 ({e})')
    else:
        print('  上传目录不存在')


def analyze_request_processing():
    """分析请求处理流程"""
    print('\n分析请求处理流程...')

    # 测试简单的API调用时间
    start_time = time.time()
    try:
        response = requests.get('http://localhost:8000/api/runtime-config', timeout=10)
        end_time = time.time()

        api_time = end_time - start_time
        print(f'  API响应时间: {api_time:.3f} 秒')
        print(f'  API状态码: {response.status_code}')
    except Exception as e:
        end_time = time.time()
        api_time = end_time - start_time
        print(f'  API调用失败: {e}')
        print(f'  调用时间: {api_time:.3f} 秒')


def check_background_processes():
    """检查后台处理进程"""
    print('\n检查后台处理进程...')

    try:
        # 检查是否有正在进行的分析任务
        response = requests.get('http://localhost:8000/api/projects', timeout=10)
        if response.status_code == 200:
            projects = response.json()
            active_projects = [
                p for p in projects if p.get('status') in ['analyzing', 'processing']
            ]
            print(f'  活动项目数: {len(active_projects)}')
            if active_projects:
                for project in active_projects:
                    print(f'    项目 {project["id"]}: {project["status"]}')
        else:
            print(f'  无法获取项目信息: {response.status_code}')
    except Exception as e:
        print(f'  检查后台进程失败: {e}')


def main():
    """主函数"""
    print('=' * 50)
    print('局域网上传性能诊断工具')
    print('=' * 50)

    # 检查服务器资源
    check_server_resources()

    # 检查Flask配置
    check_flask_configuration()

    # 检查上传目录状态
    check_upload_directory_status()

    # 分析请求处理流程
    analyze_request_processing()

    # 检查后台进程
    check_background_processes()

    # 测试上传性能
    print('\n' + '=' * 50)
    print('上传性能测试:')
    print('=' * 50)

    test_sizes = [1, 5, 10]
    results = []

    for size in test_sizes:
        try:
            upload_time, upload_speed, status_code = test_upload_with_monitoring(size)
            results.append((size, upload_time, upload_speed, status_code))
        except Exception as e:
            print(f'  {size}MB文件测试失败: {e}')
            results.append((size, 0, 0, 0))

    # 输出结果
    print('\n' + '=' * 50)
    print('测试结果汇总:')
    print('=' * 50)

    for size, upload_time, upload_speed, status_code in results:
        if upload_time > 0:
            print(
                f'  {size}MB文件: {upload_speed:.2f} Mbps ({upload_time:.2f}秒, 状态码:{status_code})'
            )
        else:
            print(f'  {size}MB文件: 测试失败')

    # 分析可能的问题
    print('\n' + '=' * 50)
    print('问题分析:')
    print('=' * 50)

    if results:
        # 检查速度是否合理
        speeds = [r[2] for r in results if r[2] > 0]
        if speeds and sum(speeds) / len(speeds) < 10:  # 平均速度低于10Mbps
            print('⚠ 上传速度偏慢，可能的原因:')
            print('  1. Flask默认文件处理机制效率低')
            print('  2. 服务器资源不足')
            print('  3. 后台任务占用过多资源')
            print('  4. 文件保存逻辑需要优化')
        else:
            print('✓ 上传速度正常')

    print('\n优化建议:')
    print('  1. 如果上传速度慢，考虑使用Nginx处理文件上传')
    print('  2. 监控服务器资源使用情况')
    print('  3. 优化后台任务调度')
    print('  4. 考虑实施分块上传')
    print('=' * 50)


if __name__ == '__main__':
    main()
