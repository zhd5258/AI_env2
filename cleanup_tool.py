#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理工具快捷启动脚本
Cleanup Tool Launcher
"""

import sys
import os

# 确保在正确的目录中运行
if not os.path.exists('unified_cleanup_tool.py'):
    print('错误: 找不到统一清理工具，请确保在项目根目录中运行')
    print(
        'Error: Cannot find unified cleanup tool, please run from project root directory'
    )
    input('按回车键退出... Press Enter to exit...')
    sys.exit(1)

# 导入并运行统一清理工具
try:
    from unified_cleanup_tool import main

    main()
except ImportError as e:
    print(f'导入错误: {e}')
    print(f'Import error: {e}')
    print('请确保所有必要的模块都已安装')
    print('Please ensure all required modules are installed')
    input('按回车键退出... Press Enter to exit...')
except Exception as e:
    print(f'运行错误: {e}')
    print(f'Runtime error: {e}')
    input('按回车键退出... Press Enter to exit...')
