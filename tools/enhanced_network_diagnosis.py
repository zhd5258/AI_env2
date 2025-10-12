#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强网络诊断工具
用于详细诊断与Ollama服务的连接问题
"""

import socket
import subprocess
import sys
import os
import platform

def ping_host(host):
    """使用ping命令检查主机连通性"""
    print(f"正在ping主机 {host}...")
    try:
        param = "-n" if platform.system().lower() == "windows" else "-c"
        result = subprocess.run(
            ["ping", param, "4", host], 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        if result.returncode == 0:
            print("✓ 主机可达")
            return True
        else:
            print("✗ 主机不可达")
            print(f"  错误信息: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ ping命令超时")
        return False
    except Exception as e:
        print(f"✗ ping命令执行出错: {e}")
        return False

def check_port_connectivity(host, port):
    """检查特定端口的连通性"""
    print(f"\n正在检查 {host}:{port} 端口连通性...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)  # 10秒超时
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print("✓ 端口可达")
            return True
        else:
            print("✗ 端口不可达")
            print(f"  错误代码: {result}")
            return False
    except Exception as e:
        print(f"✗ 端口检查出错: {e}")
        return False

def check_with_telnet(host, port):
    """尝试使用telnet检查端口（如果可用）"""
    print(f"\n尝试使用telnet连接 {host}:{port}...")
    try:
        result = subprocess.run(
            ["telnet", host, str(port)], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        # 在Windows上，telnet返回码不总是准确的，需要检查输出
        if "Connected" in result.stdout or result.returncode == 0:
            print("✓ Telnet连接成功")
            return True
        else:
            print("✗ Telnet连接失败")
            return False
    except FileNotFoundError:
        print("ℹ️  系统未安装telnet客户端")
        return None
    except subprocess.TimeoutExpired:
        print("✗ Telnet连接超时")
        return False
    except Exception as e:
        print(f"✗ Telnet命令执行出错: {e}")
        return False

def check_firewall_windows():
    """检查Windows防火墙状态"""
    if platform.system().lower() != "windows":
        print("\nℹ️  非Windows系统，跳过Windows防火墙检查")
        return True
    
    print("\n检查Windows防火墙状态...")
    try:
        result = subprocess.run(
            ["netsh", "advfirewall", "show", "allprofiles", "state"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            print("✓ 防火墙状态:")
            print(result.stdout)
            return True
        else:
            print("✗ 无法获取防火墙状态")
            return False
    except Exception as e:
        print(f"✗ 检查防火墙时出错: {e}")
        return False

def check_routes(host):
    """检查路由表"""
    print(f"\n检查到 {host} 的路由...")
    try:
        if platform.system().lower() == "windows":
            result = subprocess.run(
                ["tracert", "-h", "5", host], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
        else:
            result = subprocess.run(
                ["traceroute", "-m", "5", host], 
                capture_output=True, 
                text=True, 
                timeout=30
            )
        
        if result.returncode == 0:
            print("✓ 路由追踪结果:")
            # 只显示前几行，避免输出过多
            lines = result.stdout.split('\n')[:15]
            print('\n'.join(lines))
            return True
        else:
            print("✗ 路由追踪失败")
            print(f"  错误信息: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print("✗ 路由追踪超时")
        return False
    except Exception as e:
        print(f"✗ 路由追踪出错: {e}")
        return False

def check_dns_resolution(host):
    """检查DNS解析"""
    print(f"\n检查 {host} 的DNS解析...")
    try:
        import socket
        ip = socket.gethostbyname(host)
        print(f"✓ {host} 解析为 {ip}")
        return True
    except Exception as e:
        print(f"✗ DNS解析失败: {e}")
        return False

def suggest_solutions():
    """提供解决方案建议"""
    print("\n" + "="*50)
    print("问题诊断和解决方案建议")
    print("="*50)
    print("1. 网络连接问题:")
    print("   - 确认目标服务器IP地址是否正确 (应该是 10.0.3.169)")
    print("   - 检查本地网络连接是否正常")
    print("   - 确认是否在同一个网络中")
    print("\n2. 防火墙问题:")
    print("   - 检查目标服务器防火墙是否开放了11434端口")
    print("   - 检查本地防火墙是否阻止了出站连接")
    print("   - 在目标服务器上使用以下命令开放端口:")
    print("     Windows: netsh advfirewall firewall add rule name=\"Ollama\" dir=in action=allow protocol=TCP localport=11434")
    print("\n3. Ollama服务问题:")
    print("   - 确认Ollama服务在目标服务器上正在运行")
    print("   - 确认Ollama服务绑定到了正确的网络接口 (0.0.0.0 而不是 127.0.0.1)")
    print("   - 可以通过以下命令启动Ollama服务:")
    print("     OLLAMA_HOST=0.0.0.0 ollama serve")
    print("\n4. 环境变量配置:")
    print("   - 可以通过设置环境变量 OLLAMA_HOST 来更改目标地址:")
    print("     Windows: set OLLAMA_HOST=http://<正确IP>:11434")
    print("     Linux/Mac: export OLLAMA_HOST=http://<正确IP>:11434")

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
    print("增强网络诊断工具")
    print("="*60)
    print(f"目标地址: {host}:{port}")
    print()
    
    # 执行各项检查
    checks = [
        lambda: ping_host(host),
        lambda: check_port_connectivity(host, port),
        lambda: check_dns_resolution(host),
        lambda: check_with_telnet(host, port),
        lambda: check_routes(host),
        check_firewall_windows
    ]
    
    results = []
    for check in checks:
        try:
            result = check()
            results.append(result)
        except Exception as e:
            print(f"检查过程中出现异常: {e}")
            results.append(False)
        print()  # 添加空行分隔
    
    # 提供解决方案建议
    suggest_solutions()

if __name__ == "__main__":
    main()