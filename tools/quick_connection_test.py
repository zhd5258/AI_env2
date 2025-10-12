#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速连接测试脚本
用于快速测试与Ollama服务的连接
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.local_ai_analyzer import LocalAIAnalyzer

def main():
    print("Ollama服务快速连接测试")
    print("=" * 30)
    
    # 创建LocalAIAnalyzer实例
    analyzer = LocalAIAnalyzer()
    
    # 显示当前配置
    service_info = analyzer.get_service_info()
    print(f"测试地址: {service_info['api_url']}")
    print(f"使用模型: {service_info['model']}")
    print()
    
    # 测试连接
    print("正在测试连接...")
    if analyzer.test_connection():
        print("✓ 连接成功!")
        # 检查模型可用性
        print("正在检查模型可用性...")
        if analyzer.check_model_availability():
            print("✓ 模型可用!")
        else:
            print("✗ 模型不可用，请确认模型已下载")
    else:
        print("✗ 连接失败!")
        print("\n可能的原因:")
        print("1. 网络连接问题 - 无法访问目标服务器")
        print("2. Ollama服务未启动")
        print("3. 防火墙阻止了连接")
        print("4. IP地址或端口配置错误")
        print("\n解决方案:")
        print("- 检查网络连接")
        print("- 确认Ollama服务在目标机器上运行")
        print("- 检查防火墙设置")
        print("- 通过环境变量 OLLAMA_HOST 设置正确的地址")
        print("  例如: set OLLAMA_HOST=http://正确的IP:11434 (Windows)")
        print("       export OLLAMA_HOST=http://正确的IP:11434 (Linux/Mac)")

if __name__ == "__main__":
    main()