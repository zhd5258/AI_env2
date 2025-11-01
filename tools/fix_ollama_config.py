#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 11:32:45
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 11:32:48
# 文件相对于项目的路径   : \AI_ENV2\tools\fix_ollama_config.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
修复Ollama配置脚本
用于修正环境变量中的OLLAMA_HOST和OLLAMA_MODEL配置
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from modules.runtime_config import runtime_config


def fix_ollama_config():
    """修复Ollama配置"""
    print('修复Ollama配置...')

    # 获取当前配置
    config_summary = runtime_config.get_config_summary()
    print('当前配置:')
    print(f"  OLLAMA_HOST: '{config_summary['ollama_host']}'")
    print(f"  OLLAMA_MODEL: '{config_summary['ollama_model']}'")

    # 修正OLLAMA_HOST
    ollama_host = config_summary['ollama_host']
    # 去除首尾空格
    clean_host = ollama_host.strip()
    # 如果不包含协议前缀，添加http://
    if not clean_host.startswith('http://') and not clean_host.startswith('https://'):
        clean_host = f'http://{clean_host}'
    # 如果主机是0.0.0.0，则改为localhost（在Windows上0.0.0.0无效）
    if '0.0.0.0' in clean_host:
        clean_host = clean_host.replace('0.0.0.0', 'localhost')
        print('  注意: 将0.0.0.0替换为localhost（Windows兼容性修正）')

    # 修正OLLAMA_MODEL
    ollama_model = config_summary['ollama_model']
    # 去除首尾空格
    clean_model = ollama_model.strip()

    # 如果配置有变化，则更新
    if clean_host != ollama_host or clean_model != ollama_model:
        print('\n修正配置:')
        if clean_host != ollama_host:
            print(f"  OLLAMA_HOST: '{ollama_host}' -> '{clean_host}'")
        if clean_model != ollama_model:
            print(f"  OLLAMA_MODEL: '{ollama_model}' -> '{clean_model}'")

        # 更新配置
        runtime_config.update_ollama_config(host=clean_host, model=clean_model)

        # 显示更新后的配置
        new_config_summary = runtime_config.get_config_summary()
        print('\n更新后配置:')
        print(f"  OLLAMA_HOST: '{new_config_summary['ollama_host']}'")
        print(f"  OLLAMA_MODEL: '{new_config_summary['ollama_model']}'")

        print('\n✓ 配置修正完成')
        return True
    else:
        print('\n配置已经是正确的，无需修正')
        return False


def test_ollama_connection():
    """测试Ollama连接"""
    print('\n测试Ollama连接...')

    # 获取修正后的配置
    config_summary = runtime_config.get_config_summary()
    ollama_host = config_summary['ollama_host']
    ollama_model = config_summary['ollama_model']

    print('使用配置:')
    print(f'  主机: {ollama_host}')
    print(f'  模型: {ollama_model}')

    try:
        import requests

        # 测试API根路径
        response = requests.get(ollama_host, timeout=5)
        print(f'✓ API根路径可访问，状态码: {response.status_code}')

        # 测试模型列表
        response = requests.get(f'{ollama_host}/api/tags', timeout=10)
        response.raise_for_status()
        data = response.json()
        models = data.get('models', [])
        print(f'✓ API模型列表可访问，找到 {len(models)} 个模型')

        # 检查目标模型是否存在
        target_model_found = False
        for m in models:
            if m.get('name') == ollama_model:
                target_model_found = True
                size_mb = m.get('size', 0) / (1024 * 1024)
                print(f"✓ 目标模型 '{ollama_model}' 可用，大小: {size_mb:.1f} MB")
                break

        if not target_model_found:
            print(f"⚠ 目标模型 '{ollama_model}' 未找到")
            return False

        # 测试简单生成
        payload = {'model': ollama_model, 'prompt': '你好', 'stream': False}
        response = requests.post(
            f'{ollama_host}/api/generate', json=payload, timeout=30
        )
        response.raise_for_status()
        data = response.json()
        result = data.get('response', '')
        print(f'✓ 简单生成测试成功，响应长度: {len(result)} 字符')

        print('\n✓ Ollama连接测试通过')
        return True

    except Exception as e:
        print(f'✗ Ollama连接测试失败: {e}')
        return False


def main():
    """主函数"""
    print('=' * 50)
    print('Ollama配置修正工具')
    print('=' * 50)

    # 修正配置
    config_fixed = fix_ollama_config()

    # 测试连接
    connection_ok = test_ollama_connection()

    print('\n' + '=' * 50)
    if connection_ok:
        print('所有测试通过！Ollama配置正确且连接正常。')
    else:
        print('测试失败，请检查Ollama服务配置。')
    print('=' * 50)

    return connection_ok


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
