#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:54:59
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:54:59
# 文件相对于项目的路径   : \AI_ENV2\tools\network_bandwidth_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
网络带宽测试工具
用于测试客户端到服务器的上传带宽
"""

import requests
import time
import os
import threading
from pathlib import Path


class BandwidthTester:
    def __init__(self, server_url='http://localhost:8000'):
        self.server_url = server_url
        self.test_results = []

    def create_test_file(self, size_mb):
        """创建指定大小的测试文件"""
        filename = f'test_file_{size_mb}mb.bin'
        with open(filename, 'wb') as f:
            f.write(os.urandom(size_mb * 1024 * 1024))
        return filename

    def test_upload_speed(self, file_size_mb=10):
        """测试上传速度"""
        print(f'测试 {file_size_mb}MB 文件上传速度...')

        # 创建测试文件
        test_file = self.create_test_file(file_size_mb)
        dummy_file = None

        try:
            # 准备上传
            with open(test_file, 'rb') as f:
                files = {'tender_file': (test_file, f, 'application/octet-stream')}
                # 添加一个虚拟的投标文件
                dummy_file = self.create_test_file(1)
                with open(dummy_file, 'rb') as df:
                    files['bid_files'] = (dummy_file, df, 'application/octet-stream')

                    start_time = time.time()
                    try:
                        response = requests.post(
                            f'{self.server_url}/api/init-upload',
                            files=files,
                            timeout=300,  # 5分钟超时
                        )
                        end_time = time.time()

                        upload_time = end_time - start_time
                        file_size_bits = file_size_mb * 8 * 1024 * 1024
                        upload_speed_mbps = file_size_bits / upload_time / 1024 / 1024

                        print(f'  上传时间: {upload_time:.2f} 秒')
                        print(f'  上传速度: {upload_speed_mbps:.2f} Mbps')
                        print(f'  服务器响应: {response.status_code}')

                        self.test_results.append(
                            {
                                'file_size_mb': file_size_mb,
                                'upload_time': upload_time,
                                'upload_speed_mbps': upload_speed_mbps,
                                'status_code': response.status_code,
                            }
                        )

                        return upload_speed_mbps
                    except Exception as e:
                        end_time = time.time()
                        upload_time = end_time - start_time
                        print(f'  上传失败: {e}')
                        print(f'  上传时间: {upload_time:.2f} 秒')
                        return 0
        finally:
            # 清理测试文件
            if os.path.exists(test_file):
                os.remove(test_file)
            if dummy_file and os.path.exists(dummy_file):
                os.remove(dummy_file)

    def test_multiple_sizes(self, sizes_mb=[1, 5, 10, 20]):
        """测试多种文件大小的上传速度"""
        print('测试多种文件大小上传速度...')

        for size in sizes_mb:
            print(f'\n--- 测试 {size}MB 文件 ---')
            self.test_upload_speed(size)

    def analyze_results(self):
        """分析测试结果"""
        print('\n' + '=' * 50)
        print('上传速度测试结果分析:')
        print('=' * 50)

        if not self.test_results:
            print('没有测试结果')
            return

        # 显示每个测试的结果
        print('详细结果:')
        for result in self.test_results:
            print(
                f'  {result["file_size_mb"]}MB文件: '
                f'{result["upload_speed_mbps"]:.2f} Mbps '
                f'({result["upload_time"]:.2f}秒)'
            )

        # 计算平均速度
        valid_speeds = [
            r['upload_speed_mbps']
            for r in self.test_results
            if r['upload_speed_mbps'] > 0
        ]
        if valid_speeds:
            avg_speed = sum(valid_speeds) / len(valid_speeds)
            print(f'\n平均上传速度: {avg_speed:.2f} Mbps')

        # 识别性能问题
        print('\n性能分析:')
        if valid_speeds and min(valid_speeds) < 1:
            print('⚠ 上传速度较慢，可能的原因:')
            print('  1. 网络带宽限制')
            print('  2. 网络延迟高')
            print('  3. 服务器处理能力不足')
            print('  4. Flask默认上传机制效率低')
        elif valid_speeds and min(valid_speeds) < 10:
            print('⚠ 上传速度一般，可考虑优化:')
            print('  1. 使用Nginx作为反向代理')
            print('  2. 增加服务器资源')
            print('  3. 优化网络配置')
        else:
            print('✓ 上传速度良好')

    def suggest_optimizations(self):
        """提供优化建议"""
        print('\n' + '=' * 50)
        print('优化建议:')
        print('=' * 50)

        print('服务器端优化:')
        print('  1. 使用Nginx作为反向代理处理文件上传')
        print('  2. 调整Flask配置:')
        print('     - 增加MAX_CONTENT_LENGTH')
        print('     - 调整缓冲区大小')
        print('  3. 使用异步文件处理')
        print('  4. 考虑使用专门的文件上传服务')

        print('\n网络优化:')
        print('  1. 确保网络带宽充足')
        print('  2. 减少网络延迟')
        print('  3. 使用CDN加速')
        print('  4. 优化路由配置')

        print('\n客户端优化:')
        print('  1. 使用压缩文件')
        print('  2. 分批上传大文件')
        print('  3. 显示上传进度')
        print('  4. 支持断点续传')


def main():
    """主函数"""
    print('=' * 50)
    print('网络带宽测试工具')
    print('=' * 50)

    tester = BandwidthTester()

    # 测试多种文件大小
    tester.test_multiple_sizes([1, 5, 10])

    # 分析结果
    tester.analyze_results()

    # 提供优化建议
    tester.suggest_optimizations()

    print('\n' + '=' * 50)


if __name__ == '__main__':
    main()
