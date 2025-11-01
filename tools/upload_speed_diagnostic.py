#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:53:29
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:53:32
# 文件相对于项目的路径   : \AI_ENV2\tools\upload_speed_diagnostic.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
上传速度诊断工具
用于诊断和解决文件上传速度慢的问题
"""

import requests
import time
import os
from pathlib import Path


def test_upload_speed(file_size_mb=1):
    """测试上传速度"""
    print(f'测试上传速度 (文件大小: {file_size_mb}MB)...')

    # 创建测试文件
    test_file_path = 'test_upload_file.bin'
    try:
        # 创建指定大小的测试文件
        with open(test_file_path, 'wb') as f:
            f.write(os.urandom(file_size_mb * 1024 * 1024))

        print(f'创建测试文件: {test_file_path} ({file_size_mb}MB)')

        # 测试上传速度
        files = {'test_file': open(test_file_path, 'rb')}
        start_time = time.time()

        try:
            response = requests.post(
                'http://localhost:8000/api/init-upload',
                files=files,
                timeout=300,  # 5分钟超时
            )
            end_time = time.time()

            upload_time = end_time - start_time
            upload_speed = (file_size_mb * 8) / upload_time  # Mbps

            print(f'上传完成时间: {upload_time:.2f} 秒')
            print(f'上传速度: {upload_speed:.2f} Mbps')
            print(f'服务器响应: {response.status_code}')

            return upload_time, upload_speed
        except Exception as e:
            end_time = time.time()
            upload_time = end_time - start_time
            print(f'上传失败: {e}')
            print(f'上传时间: {upload_time:.2f} 秒')
            return upload_time, 0
        finally:
            files['test_file'].close()
    except Exception as e:
        print(f'创建测试文件失败: {e}')
        return 0, 0
    finally:
        # 清理测试文件
        if os.path.exists(test_file_path):
            os.remove(test_file_path)


def check_server_config():
    """检查服务器配置"""
    print('\n检查服务器配置...')

    try:
        # 检查Flask配置
        response = requests.get('http://localhost:8000/api/runtime-config', timeout=10)
        if response.status_code == 200:
            config = response.json()
            max_content_length = config.get('max_content_length', 0)
            single_file_max_size = config.get('single_file_max_size', 0)

            print(f'最大内容长度: {max_content_length / (1024 * 1024):.0f} MB')
            print(f'单文件最大大小: {single_file_max_size / (1024 * 1024):.0f} MB')

            return max_content_length, single_file_max_size
        else:
            print(f'无法获取服务器配置: {response.status_code}')
            return 0, 0
    except Exception as e:
        print(f'检查服务器配置失败: {e}')
        return 0, 0


def check_network_bandwidth():
    """检查网络带宽"""
    print('\n检查网络带宽...')

    try:
        # 测试下载速度作为参考
        start_time = time.time()
        response = requests.get('https://httpbin.org/bytes/1048576', timeout=30)  # 1MB
        end_time = time.time()

        download_time = end_time - start_time
        download_speed = (8) / download_time  # Mbps

        print(f'下载速度测试: {download_speed:.2f} Mbps')
        return download_speed
    except Exception as e:
        print(f'网络带宽测试失败: {e}')
        return 0


def check_disk_io():
    """检查磁盘IO性能"""
    print('\n检查磁盘IO性能...')

    try:
        # 创建临时文件测试写入速度
        test_file = 'disk_io_test.tmp'
        test_data = os.urandom(10 * 1024 * 1024)  # 10MB

        start_time = time.time()
        with open(test_file, 'wb') as f:
            f.write(test_data)
        end_time = time.time()

        write_time = end_time - start_time
        write_speed = (10 * 8) / write_time  # Mbps

        print(f'磁盘写入速度: {write_speed:.2f} Mbps')

        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)

        return write_speed
    except Exception as e:
        print(f'磁盘IO测试失败: {e}')
        return 0


def main():
    """主函数"""
    print('=' * 50)
    print('AI评标系统上传速度诊断工具')
    print('=' * 50)

    # 测试不同大小文件的上传速度
    file_sizes = [1, 5, 10]  # MB
    results = []

    for size in file_sizes:
        print(f'\n--- 测试 {size}MB 文件上传 ---')
        upload_time, upload_speed = test_upload_speed(size)
        results.append((size, upload_time, upload_speed))

    # 检查服务器配置
    max_content_length, single_file_max_size = check_server_config()

    # 检查网络带宽
    download_speed = check_network_bandwidth()

    # 检查磁盘IO
    disk_write_speed = check_disk_io()

    print('\n' + '=' * 50)
    print('诊断结果:')
    print('=' * 50)

    print('上传速度测试结果:')
    for size, upload_time, upload_speed in results:
        if upload_speed > 0:
            print(f'  {size}MB文件: {upload_speed:.2f} Mbps ({upload_time:.2f}秒)')
        else:
            print(f'  {size}MB文件: 上传失败 ({upload_time:.2f}秒)')

    print('\n服务器配置:')
    print(f'  最大内容长度: {max_content_length / (1024 * 1024):.0f} MB')
    print(f'  单文件最大大小: {single_file_max_size / (1024 * 1024):.0f} MB')

    print('\n网络性能:')
    if download_speed > 0:
        print(f'  下载速度: {download_speed:.2f} Mbps')

    print('\n磁盘性能:')
    if disk_write_speed > 0:
        print(f'  写入速度: {disk_write_speed:.2f} Mbps')

    # 分析可能的问题
    print('\n' + '=' * 50)
    print('问题分析与建议:')
    print('=' * 50)

    # 检查上传速度是否过慢
    if results and results[0][2] > 0:  # 如果有测试结果
        speed_mbps = results[0][2]
        if speed_mbps < 1:  # 小于1Mbps认为过慢
            print('⚠ 上传速度过慢，可能的原因:')
            print('  1. 网络带宽限制')
            print('  2. 服务器性能不足')
            print('  3. 磁盘IO性能差')
            print('  4. Flask默认上传处理较慢')
            print('\n优化建议:')
            print('  1. 考虑使用Nginx作为反向代理')
            print('  2. 增加服务器硬件资源')
            print('  3. 优化磁盘性能')
            print('  4. 调整Flask上传配置')
        else:
            print('✓ 上传速度正常')

    print('=' * 50)


if __name__ == '__main__':
    main()
