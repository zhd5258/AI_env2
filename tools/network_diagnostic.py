#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:51:15
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:51:17
# 文件相对于项目的路径   : \AI_ENV2\tools\network_diagnostic.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
网络诊断工具
用于诊断和解决服务器在网络环境中的访问问题
"""

import socket
import requests
import subprocess
import sys
import os
import json
from urllib.parse import urlparse


def check_server_status():
    """检查服务器状态"""
    print('检查服务器状态...')
    try:
        response = requests.get('http://localhost:8000', timeout=5)
        print(f'✓ 服务器正在运行，状态码: {response.status_code}')
        return True
    except Exception as e:
        print(f'✗ 服务器未运行或无法访问: {e}')
        return False


def get_network_interfaces():
    """获取网络接口信息"""
    print('\n获取网络接口信息...')
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print(f'主机名: {hostname}')
        print(f'本地IP: {local_ip}')

        # 获取所有网络接口
        interfaces = socket.getaddrinfo(hostname, None)
        print('网络接口:')
        for interface in interfaces:
            ip = interface[4][0]
            if ':' not in str(ip):  # 过滤IPv6地址
                print(f'  - {ip}')
        return local_ip
    except Exception as e:
        print(f'✗ 获取网络接口信息失败: {e}')
        return None


def check_port_listening():
    """检查端口监听状态"""
    print('\n检查端口监听状态...')
    try:
        if sys.platform.startswith('win'):
            result = subprocess.run(
                ['netstat', '-an'], capture_output=True, text=True, encoding='utf-8'
            )
        else:
            result = subprocess.run(
                ['netstat', '-tuln'], capture_output=True, text=True
            )

        lines = result.stdout.split('\n')
        listening_ports = []
        for line in lines:
            if ':8000' in line and ('LISTEN' in line or 'LISTENING' in line):
                listening_ports.append(line.strip())

        if listening_ports:
            for port_info in listening_ports:
                print(f'✓ 端口8000正在监听: {port_info}')
            return True
        else:
            print('⚠ 端口8000未在监听')
            return False
    except Exception as e:
        print(f'✗ 检查端口监听状态失败: {e}')
        return False


def check_firewall_rules():
    """检查防火墙规则"""
    print('\n检查防火墙规则...')
    try:
        if sys.platform.startswith('win'):
            # 检查是否有针对端口8000的防火墙规则
            result = subprocess.run(
                ['netsh', 'advfirewall', 'firewall', 'show', 'rule', 'name=all'],
                capture_output=True,
                text=True,
                encoding='utf-8',
            )

            rules = result.stdout.split('\n规则名称:')
            port_8000_rules = []
            for rule in rules:
                if '8000' in rule:
                    port_8000_rules.append(rule)

            if port_8000_rules:
                print('✓ 找到针对端口8000的防火墙规则:')
                for rule in port_8000_rules:
                    lines = rule.split('\n')
                    for line in lines:
                        if line.strip():
                            print(f'  {line.strip()}')
                return True
            else:
                print('⚠ 未找到针对端口8000的防火墙规则')
                return False
        else:
            print('非Windows系统，跳过防火墙检查')
            return True
    except Exception as e:
        print(f'✗ 检查防火墙规则失败: {e}')
        return False


def add_firewall_rule():
    """添加防火墙规则"""
    print('\n添加防火墙规则...')
    try:
        if sys.platform.startswith('win'):
            result = subprocess.run(
                [
                    'netsh',
                    'advfirewall',
                    'firewall',
                    'add',
                    'rule',
                    'name=AI评标系统',
                    'dir=in',
                    'action=allow',
                    'protocol=TCP',
                    'localport=8000',
                ],
                capture_output=True,
                text=True,
                encoding='utf-8',
            )

            if '确定' in result.stdout:
                print('✓ 防火墙规则添加成功')
                return True
            else:
                print(f'✗ 防火墙规则添加失败: {result.stdout}')
                return False
        else:
            print('非Windows系统，跳过防火墙规则添加')
            return True
    except Exception as e:
        print(f'✗ 添加防火墙规则失败: {e}')
        return False


def test_network_access(ip_address):
    """测试网络访问"""
    print(f'\n测试网络访问 ({ip_address})...')
    try:
        response = requests.get(f'http://{ip_address}:8000', timeout=10)
        print(f'✓ 网络访问成功，状态码: {response.status_code}')
        return True
    except Exception as e:
        print(f'✗ 网络访问失败: {e}')
        return False


def check_cors_configuration():
    """检查CORS配置"""
    print('\n检查CORS配置...')
    try:
        # 检查是否允许跨域请求
        response = requests.options('http://localhost:8000/api/init-upload', timeout=5)
        if 'Access-Control-Allow-Origin' in response.headers:
            print('✓ CORS配置正确')
            return True
        else:
            print('⚠ CORS配置可能存在问题')
            return False
    except Exception as e:
        print(f'✗ 检查CORS配置失败: {e}')
        return False


def main():
    """主函数"""
    print('=' * 60)
    print('AI评标系统网络诊断工具')
    print('=' * 60)

    # 检查服务器状态
    server_ok = check_server_status()

    # 获取网络接口信息
    local_ip = get_network_interfaces()

    # 检查端口监听状态
    port_ok = check_port_listening()

    # 检查防火墙规则
    firewall_ok = check_firewall_rules()

    # 如果没有防火墙规则，添加一个
    if not firewall_ok:
        print('\n未找到针对端口8000的防火墙规则，正在添加...')
        add_firewall_rule()
        # 重新检查防火墙规则
        firewall_ok = check_firewall_rules()

    # 测试网络访问
    network_ok = False
    if local_ip:
        network_ok = test_network_access(local_ip)

    # 检查CORS配置
    cors_ok = check_cors_configuration()

    print('\n' + '=' * 60)
    print('诊断结果汇总:')
    print('=' * 60)
    print(f'服务器状态: {"✓ 正常" if server_ok else "✗ 异常"}')
    print(f'端口监听: {"✓ 正常" if port_ok else "✗ 异常"}')
    print(f'防火墙规则: {"✓ 正常" if firewall_ok else "✗ 异常"}')
    print(f'网络访问: {"✓ 正常" if network_ok else "✗ 异常"}')
    print(f'CORS配置: {"✓ 正常" if cors_ok else "✗ 异常"}')

    if server_ok and port_ok and firewall_ok and network_ok and cors_ok:
        print('\n✓ 所有检查通过！服务器应该可以正常访问。')
        print(f'\n请在其他设备上访问: http://{local_ip}:8000')
    else:
        print('\n⚠ 部分检查失败，请根据上述结果进行相应处理。')
        print('\n常见解决方案:')
        print('1. 确保服务器正在运行 (python app.py)')
        print('2. 检查端口8000是否被其他程序占用')
        print('3. 确保防火墙允许端口8000的入站连接')
        print('4. 检查路由器设置，确保端口转发正确')
        print('5. 确保网络连接正常')

    print('=' * 60)


if __name__ == '__main__':
    main()
