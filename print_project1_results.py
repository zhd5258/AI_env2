#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
打印项目1的完整结果表格
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.result_display import print_multi_level_table

def print_project1_results():
    """
    打印项目1的完整结果表格
    """
    print("打印项目1的完整结果表格")
    print("=" * 50)
    
    try:
        print_multi_level_table(project_id=1)
    except Exception as e:
        print(f"打印过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print_project1_results()