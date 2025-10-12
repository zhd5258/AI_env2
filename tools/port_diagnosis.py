#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端口诊断工具
专门用于检查Ollama服务端口的可访问性
"""

import socket
import sys
import platform
import subprocess
import time

def check_port_with_socket(host, port, timeout=10):
    """使用socket检查端口"""
    print(f"1. 使用socket检查 {host}:{port}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("   ✓ 端口可通过socket连接")
            return True
        else:
            print(f"   ✗ 端口无法通过socket连接 (错误代码: {result})")
            return False
    except Exception as e:
        print(f"   ✗ Socket检查出错: {e}")
        return False

def check_port_with_telnet(host, port, timeout=10):
    """使用telnet检查端口"""
    print(f"\n2. 使用telnet检查 {host}:{port}...")
    try:
        # 在Windows上使用telnet命令
        if platform.system().lower() == "windows":
            # 使用PowerShell的Test-NetConnection命令
            cmd = [
                "powershell", 
                "-Command", 
                f"Test-NetConnection -ComputerName {host} -Port {port}"
            ]
        else:
            # 在Linux/Mac上使用nc命令
            cmd = ["nc", "-zv", host, str(port)]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        
        if platform.system().lower() == "windows":
            if "TcpTestSucceeded : True" in result.stdout:
                print("   ✓ 端口可通过Test-NetConnection连接")
                return True
            else:
                print("   ✗ 端口无法通过Test-NetConnection连接")
                print(f"      输出: {result.stdout}")
                return False
        else:
            if result.returncode == 0:
                print("   ✓ 端口可通过nc连接")
                return True
            else:
                print("   ✗ 端口无法通过nc连接")
                print(f"      错误: {result.stderr}")
                return False
                
    except FileNotFoundError:
        print("   ℹ️  系统未安装telnet或nc工具")
        return None
    except subprocess.TimeoutExpired:
        print("   ✗ 端口检查超时")
        return False
    except Exception as e:
        print(f"   ✗ Telnet/nc检查出错: {e}")
        return False

def check_port_with_http_request(host, port, timeout=10):
    """使用HTTP请求检查端口"""
    print(f"\n3. 使用HTTP请求检查 {host}:{port}...")
    try:
        import requests
        
        url = f"http://{host}:{port}"
        response = requests.get(url, timeout=timeout)
        print(f"   ✓ 端口可通过HTTP访问，状态码: {response.status_code}")
        return True
    except Exception as e:
        print(f"   ✗ 端口无法通过HTTP访问: {e}")
        return False

def check_ollama_api_endpoints(host, port, timeout=10):
    """检查Ollama特定的API端点"""
    print(f"\n4. 检查Ollama API端点...")
    try:
        import requests
        
        # 检查根路径
        root_url = f"http://{host}:{port}"
        response = requests.get(root_url, timeout=timeout)
        print(f"   ✓ 根路径可访问，状态码: {response.status_code}")
        
        # 检查API路径
        api_url = f"http://{host}:{port}/api/tags"
        response = requests.get(api_url, timeout=timeout)
        print(f"   ✓ API路径可访问，状态码: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                models = data.get('models', [])
                print(f"   ✓ 找到 {len(models)} 个模型")
                for model in models:
                    print(f"     - {model.get('name', 'unknown')}")
            except Exception as e:
                print(f"   ℹ️  无法解析API响应: {e}")
        
        return True
    except Exception as e:
        print(f"   ✗ Ollama API端点不可访问: {e}")
        return False

def suggest_solutions():
    """提供解决方案建议"""
    print("\n" + "="*50)
    print("问题诊断和解决方案建议")
    print("="*50)
    print("根据诊断结果，可能的问题和解决方案如下:")
    print("\n1. Ollama服务未正确启动:")
    print("   - 在目标服务器上运行: ollama serve")
    print("   - 确保服务在后台持续运行")
    print("\n2. Ollama服务绑定地址问题:")
    print("   - 默认情况下，Ollama可能只绑定到127.0.0.1(localhost)")
    print("   - 需要绑定到所有接口: OLLAMA_HOST=0.0.0.0 ollama serve")
    print("\n3. 防火墙阻止连接:")
    print("   - 在目标服务器上开放11434端口")
    print("   - Windows示例:")
    print("     netsh advfirewall firewall add rule name=\"Ollama\" dir=in action=allow protocol=TCP localport=11434")
    print("   - Linux示例:")
    print("     sudo ufw allow 11434")
    print("     sudo firewall-cmd --permanent --add-port=11434/tcp && sudo firewall-cmd --reload")
    print("\n4. 网络策略或安全组限制:")
    print("   - 如果在云服务器上，检查安全组规则")
    print("   - 确保入站规则允许11434端口的TCP连接")
    print("\n5. 端口被其他进程占用:")
    print("   - 检查11434端口是否被其他程序占用")
    print("   - Windows示例: netstat -ano | findstr :11434")
    print("   - Linux示例: netstat -tulpn | grep :11434")

def main():
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
    
    print("="*60)
    print("Ollama服务端口诊断工具")
    print("="*60)
    print(f"目标地址: {host}:{port}")
    print()
    
    # 执行各项检查
    checks = [
        lambda: check_port_with_socket(host, port),
        lambda: check_port_with_telnet(host, port),
        lambda: check_port_with_http_request(host, port),
        lambda: check_ollama_api_endpoints(host, port)
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"检查过程中出现异常: {e}")
            results.append(False)
        time.sleep(1)  # 避免检查之间间隔太短
    
    # 提供解决方案建议
    suggest_solutions()

if __name__ == "__main__":
    main()