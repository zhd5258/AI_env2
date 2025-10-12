#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全面诊断工具
用于诊断与Ollama服务的各种连接问题
"""

import requests
import socket
import os
import sys
import subprocess
from urllib.parse import urlparse

def check_network_connectivity(host, port=11434):
    """检查网络连通性"""
    print(f"1. 检查网络连通性到 {host}:{port}")
    
    # 使用socket测试端口连通性
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("   ✓ 端口可达")
            return True
        else:
            print("   ✗ 端口不可达")
            return False
    except Exception as e:
        print(f"   ✗ 网络测试出错: {e}")
        return False

def check_ollama_service(host, port=11434):
    """检查Ollama服务状态"""
    print(f"\n2. 检查Ollama服务状态")
    url = f"http://{host}:{port}"
    
    try:
        # 测试根路径
        response = requests.get(url, timeout=10)
        print(f"   ✓ Ollama服务响应，状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"   ✗ 无法访问Ollama服务: {e}")
        return False
    
    try:
        # 测试API路径
        api_url = f"{url}/api/tags"
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            print("   ✓ Ollama API可访问")
            models = response.json().get('models', [])
            print(f"   ✓ 可用模型数量: {len(models)}")
            for model in models:
                print(f"     - {model.get('name', 'unknown')}")
            return True
        else:
            print(f"   ✗ API返回错误状态码: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"   ✗ API不可访问: {e}")
        return False

def check_firewall():
    """检查本地防火墙设置（Windows）"""
    print("\n3. 检查本地防火墙设置")
    try:
        # 这里我们只是提示用户检查防火墙，而不是实际修改它
        print("   ℹ️  请确保Windows防火墙允许Ollama服务通过")
        print("   ℹ️  如果是远程连接，请确保防火墙允许出站连接到目标端口")
        return True
    except Exception as e:
        print(f"   ✗ 检查防火墙时出错: {e}")
        return False

def check_environment_variables():
    """检查相关环境变量"""
    print("\n4. 检查环境变量")
    ollama_host = os.environ.get('OLLAMA_HOST')
    if ollama_host:
        print(f"   ✓ OLLAMA_HOST = {ollama_host}")
    else:
        print("   ℹ️  OLLAMA_HOST 未设置，将使用默认值")
    
    return True

def diagnose_common_issues():
    """诊断常见问题"""
    print("\n5. 常见问题诊断")
    print("   可能的问题和解决方案:")
    print("   1. IP地址或端口号错误")
    print("      - 确保使用正确的IP地址和端口号（默认11434）")
    print("   2. Ollama服务未启动")
    print("      - 在运行Ollama的机器上执行 'ollama serve'")
    print("   3. Ollama未绑定到正确的网络接口")
    print("      - 启动时设置环境变量 OLLAMA_HOST=0.0.0.0")
    print("   4. 防火墙阻止连接")
    print("      - 在防火墙中开放端口11434")
    print("   5. 网络路由问题")
    print("      - 确保客户端可以访问目标网络")
    return True

def main():
    # 默认主机和端口
    host = "10.0.3.169"
    port = 11434
    
    # 如果提供了命令行参数，则使用参数中的地址
    if len(sys.argv) > 1:
        addr = sys.argv[1]
        if ':' in addr:
            parts = addr.split(':')
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                print("警告: 端口号无效，使用默认端口11434")
                port = 11434
        else:
            host = addr
    
    print("=" * 50)
    print("Ollama服务连接问题诊断工具")
    print("=" * 50)
    print(f"目标地址: http://{host}:{port}")
    print()
    
    # 执行各项检查
    checks = [
        lambda: check_network_connectivity(host, port),
        lambda: check_ollama_service(host, port),
        check_firewall,
        check_environment_variables,
        diagnose_common_issues
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"检查过程中出现异常: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("诊断总结")
    print("=" * 50)
    
    if all(results[:2]):  # 如果网络连接和服务状态都正常
        print("✓ 连接正常，Ollama服务可访问")
    elif results[0]:  # 网络连接正常但服务不可访问
        print("⚠️  网络可达但Ollama服务不可访问")
        print("   请检查Ollama服务是否在目标机器上正确运行")
    else:  # 网络连接失败
        print("✗ 网络连接失败")
        print("   请检查IP地址、端口号以及网络连接")
    
    print("\n详细诊断信息请查看以上输出")

if __name__ == "__main__":
    main()