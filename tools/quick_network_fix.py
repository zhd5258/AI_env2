#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:51:57
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:52:00
# 文件相对于项目的路径   : \AI_ENV2\tools\quick_network_fix.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
快速网络问题修复工具
用于快速诊断和解决文件上传无响应的问题
"""

import requests
import socket
import subprocess
import sys
import time


def check_server_running():
    """检查服务器是否正在运行"""
    print('检查服务器是否正在运行...')
    try:
        response = requests.get('http://localhost:8000', timeout=5)
        if response.status_code == 200:
            print('✓ 服务器正在运行')
            return True
        else:
            print(f'✗ 服务器返回状态码: {response.status_code}')
            return False
    except requests.exceptions.ConnectionError:
        print('✗ 无法连接到服务器，请确保服务器正在运行')
        return False
    except Exception as e:
        print(f'✗ 检查服务器状态时出错: {e}')
        return False


def check_network_interfaces():
    """检查网络接口"""
    print('\n检查网络接口...')
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        print(f'本机IP地址: {ip_address}')
        return ip_address
    except Exception as e:
        print(f'✗ 获取IP地址失败: {e}')
        return None


def test_local_upload():
    """测试本地上传功能"""
    print('\n测试本地上传功能...')
    try:
        # 发送一个简单的POST请求到上传接口
        response = requests.post(
            'http://localhost:8000/api/init-upload', data={'test': 'data'}, timeout=10
        )
        # 我们期望得到400错误（缺少文件），这表明服务器可以响应
        if response.status_code in [400, 413]:
            print('✓ 上传接口可访问（返回预期错误码）')
            return True
        elif response.status_code == 200:
            print('✓ 上传接口可访问')
            return True
        else:
            print(f'⚠ 上传接口返回意外状态码: {response.status_code}')
            return True  # 仍然认为接口可访问
    except requests.exceptions.ConnectionError:
        print('✗ 无法连接到上传接口')
        return False
    except Exception as e:
        print(f'✗ 测试上传功能时出错: {e}')
        return False


def add_firewall_exception():
    """添加防火墙例外"""
    print('\n添加防火墙例外...')
    try:
        # 添加防火墙规则允许端口8000
        result = subprocess.run(
            [
                'netsh',
                'advfirewall',
                'firewall',
                'add',
                'rule',
                'name=AI评标系统端口8000',
                'dir=in',
                'action=allow',
                'protocol=TCP',
                'localport=8000',
            ],
            capture_output=True,
            text=True,
            encoding='gbk',
        )

        if '确定' in result.stdout:
            print('✓ 防火墙例外添加成功')
            return True
        else:
            print('⚠ 防火墙例外可能已存在或添加失败')
            return False
    except Exception as e:
        print(f'✗ 添加防火墙例外时出错: {e}')
        return False


def restart_server():
    """重启服务器的建议"""
    print('\n如果问题仍然存在，请尝试以下步骤:')
    print('1. 停止当前运行的服务器 (Ctrl+C)')
    print('2. 运行以下命令启动服务器:')
    print('   cd d:\\user\\PythonProject\\AI_ENV2')
    print('   python app.py')
    print("3. 等待服务器启动完成（看到'应用启动中...'消息）")
    print('4. 在其他设备上访问: http://本机IP:8000')


def main():
    """主函数"""
    print('=' * 50)
    print('AI评标系统快速网络问题修复工具')
    print('=' * 50)

    # 检查服务器状态
    server_ok = check_server_running()

    if not server_ok:
        print('\n服务器未运行，请先启动服务器:')
        print('cd d:\\user\\PythonProject\\AI_ENV2')
        print('python app.py')
        return

    # 检查网络接口
    ip_address = check_network_interfaces()

    # 测试本地上传功能
    upload_ok = test_local_upload()

    # 添加防火墙例外
    firewall_added = add_firewall_exception()

    print('\n' + '=' * 50)
    print('修复结果:')
    print('=' * 50)
    print(f'服务器状态: {"✓ 正常" if server_ok else "✗ 异常"}')
    print(f'上传功能: {"✓ 可访问" if upload_ok else "✗ 无法访问"}')
    print(f'防火墙例外: {"✓ 已添加" if firewall_added else "⚠ 未添加"}')

    if server_ok and upload_ok:
        print('\n✓ 服务器功能正常，应该可以接收文件上传请求')
        if ip_address:
            print(f'\n请在其他设备上访问: http://{ip_address}:8000')
    else:
        print('\n✗ 服务器存在问题，请按以下步骤操作:')
        restart_server()

    print('=' * 50)


if __name__ == '__main__':
    main()
