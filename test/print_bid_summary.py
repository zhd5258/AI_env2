#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 19:11:12
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 19:11:14
#文件相对于项目的路径   : \AI_env2\test\print_bid_summary.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-

import os
import sys
from pathlib import Path

# 将项目根目录添加到sys.path，以便导入模块
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

def print_bid_summary_content():
    """
    打印投标一览表的全部内容
    """
    # 定义测试文件路径
    md_file_path = r'd:\user\PythonProject\AI_env2\temp_md\江苏中车云汇科技有限公司投标文件.md'
    
    # 验证文件是否存在
    if not os.path.exists(md_file_path):
        print(f"错误: 测试文件不存在: {md_file_path}")
        return
    
    print(f"开始读取文件: {md_file_path}\n")
    
    # 读取文件内容
    with open(md_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 查找包含"投标一览表"的行
    lines = content.split('\n')
    bid_summary_sections = []
    
    for i, line in enumerate(lines):
        if '投标一览表' in line:
            print(f"在第 {i+1} 行找到包含'投标一览表'的行:")
            print(f"  {line}")
            
            # 提取包含该关键词的段落（向前向后各扩展一定行数）
            start_idx = max(0, i - 20)
            end_idx = min(len(lines), i + 50)
            section = '\n'.join(lines[start_idx:end_idx])
            bid_summary_sections.append(section)
            
            print(f"  提取了从第 {start_idx+1} 行到第 {end_idx} 行的段落:")
            print("=" * 60)
            print(section)
            print("=" * 60)
            print()
    
    if not bid_summary_sections:
        print("未找到包含'投标一览表'的内容")

if __name__ == '__main__':
    print_bid_summary_content()
