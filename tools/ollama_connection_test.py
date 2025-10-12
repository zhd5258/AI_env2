#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama服务连接测试工具
用于诊断与Ollama服务的连接问题
"""

import requests
import socket
import os
import sys
from urllib.parse import urlparse

def test_port_connectivity(host, port, timeout=5):
    """测试指定主机和端口的连通性"""
    print(f"正在测试 {host}:{port} 的连通性...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✓ 端口连通性测试通过")
            return True
        else:
            print("✗ 端口连通性测试失败")
            return False
    except Exception as e:
        print(f"✗ 端口连通性测试出错: {e}")
        return False

def test_ollama_api(host, port):
    """测试Ollama API服务"""
    url = f"http://{host}:{port}"
    print(f"\n正在测试Ollama API服务 ({url})...")
    
    try:
        # 测试根路径
        response = requests.get(url, timeout=10)
        print(f"✓ 根路径可访问，状态码: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"✗ 根路径不可访问: {e}")
        return False
    
    try:
        # 测试模型列表API
        models_url = f"{url}/api/tags"
        response = requests.get(models_url, timeout=10)
        print(f"✓ 模型API可访问，状态码: {response.status_code}")
        
        if response.status_code == 200:
            models_data = response.json()
            models = models_data.get('models', [])
            print(f"✓ 发现 {len(models)} 个模型")
            for model in models:
                print(f"  - {model['name']}")
            return True
        else:
            print("✗ 模型API返回错误状态码")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ 模型API不可访问: {e}")
        return False
    except Exception as e:
        print(f"✗ 解析模型数据时出错: {e}")
        return False

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
    
    print(f"开始诊断Ollama服务连接问题...")
    print(f"目标地址: http://{host}:{port}")
    
    # 测试端口连通性
    if not test_port_connectivity(host, port):
        print("\n解决方案:")
        print("1. 确认Ollama服务是否在目标机器上运行")
        print("2. 检查防火墙设置，确保端口11434对外开放")
        print("3. 检查网络连接，确认可以访问目标主机")
        print("4. 确认目标主机IP地址是否正确")
        return
    
    # 测试Ollama API
    if not test_ollama_api(host, port):
        print("\n解决方案:")
        print("1. 确认Ollama服务是否正确启动")
        print("2. 检查Ollama服务是否绑定到正确的网络接口")
        print("3. 查看Ollama服务日志，确认是否有错误信息")
        print("4. 确认所需的大模型是否已下载")
        return
    
    print("\n✓ 所有测试通过，Ollama服务连接正常!")

if __name__ == "__main__":
    main()