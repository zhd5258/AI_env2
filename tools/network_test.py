#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:49:35
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:49:38
# 文件相对于项目的路径   : \AI_ENV2\tools\network_test.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
网络连接测试脚本
用于测试服务器在网络环境中的可访问性
"""

import socket
import requests
import subprocess
import sys
import os


def test_local_access():
    """测试本地访问"""
    print('测试本地访问...')
    try:
        response = requests.get('http://localhost:8000', timeout=5)
        print(f'✓ 本地访问成功，状态码: {response.status_code}')
        return True
    except Exception as e:
        print(f'✗ 本地访问失败: {e}')
        return False


def test_network_access():
    """测试网络访问"""
    print('\n测试网络访问...')
    try:
        # 获取本机IP地址
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f'本机主机名: {hostname}')
        print(f'本机IP地址: {local_ip}')

        # 测试本机IP访问
        response = requests.get(f'http://{local_ip}:8000', timeout=5)
        print(f'✓ 本机IP访问成功，状态码: {response.status_code}')
        return True
    except Exception as e:
        print(f'✗ 本机IP访问失败: {e}')
        return False


def check_port_binding():
    """检查端口绑定情况"""
    print('\n检查端口绑定情况...')
    try:
        # Windows系统检查端口
        if sys.platform.startswith('win'):
            result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if ':8000' in line and 'LISTENING' in line:
                    print(f'✓ 端口8000正在监听: {line.strip()}')
                    return True
        else:
            # Unix/Linux系统检查端口
            result = subprocess.run(
                ['netstat', '-tuln'], capture_output=True, text=True
            )
            lines = result.stdout.split('\n')
            for line in lines:
                if ':8000' in line and 'LISTEN' in line:
                    print(f'✓ 端口8000正在监听: {line.strip()}')
                    return True
        print('⚠ 未找到端口8000的监听信息')
        return False
    except Exception as e:
        print(f'✗ 检查端口绑定失败: {e}')
        return False


def check_firewall():
    """检查防火墙设置（仅Windows）"""
    print('\n检查防火墙设置...')
    if sys.platform.startswith('win'):
        try:
            # 检查防火墙状态
            result = subprocess.run(
                ['netsh', 'advfirewall', 'show', 'allprofiles'],
                capture_output=True,
                text=True,
            )
            if 'State' in result.stdout:
                print('✓ 防火墙状态检查完成')
                # 简单检查是否开启了防火墙
                if 'ON' in result.stdout.upper():
                    print('⚠ 防火墙可能已开启，需要确保端口8000已放行')
                else:
                    print('✓ 防火墙已关闭')
                return True
        except Exception as e:
            print(f'✗ 检查防火墙设置失败: {e}')
            return False
    else:
        print('非Windows系统，跳过防火墙检查')
        return True


def main():
    """主函数"""
    print('=' * 50)
    print('网络连接测试')
    print('=' * 50)

    # 测试本地访问
    local_ok = test_local_access()

    # 测试网络访问
    network_ok = test_network_access()

    # 检查端口绑定
    port_ok = check_port_binding()

    # 检查防火墙
    firewall_ok = check_firewall()

    print('\n' + '=' * 50)
    print('测试结果汇总:')
    print('=' * 50)
    print(f'本地访问: {"✓ 通过" if local_ok else "✗ 失败"}')
    print(f'网络访问: {"✓ 通过" if network_ok else "✗ 失败"}')
    print(f'端口绑定: {"✓ 通过" if port_ok else "✗ 失败"}')
    print(f'防火墙检查: {"✓ 通过" if firewall_ok else "✗ 失败"}')

    if local_ok and network_ok and port_ok:
        print('\n✓ 所有测试通过！服务器应该可以正常访问。')
    else:
        print('\n⚠ 部分测试失败，请检查上述问题。')
        print('\n常见解决方案:')
        print('1. 确保服务器正在运行')
        print('2. 检查防火墙设置，确保端口8000已放行')
        print('3. 检查路由器设置，确保端口转发正确')
        print('4. 确保没有其他程序占用端口8000')

    print('=' * 50)


if __name__ == '__main__':
    main()
