#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试投标方名称提取模块的修复效果
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.bidder_name_extractor import (
    _is_valid_company_name,
    _looks_garbled_or_incomplete,
    _filter_bidder_name
)

def test_bidder_name_validation():
    """
    测试投标方名称验证功能
    """
    print("测试投标方名称验证功能...")
    print("=" * 60)
    
    # 测试有效的公司名称
    valid_names = [
        "山东创杰智慧装备科技有限公司",
        "江苏鑫桥环保科技有限公司",
        "扬州琼花涂装工程技术有限公司"
    ]
    
    # 测试无效的公司名称
    invalid_names = [
        "昆｀＂卫贸有限;？",  # 乱码名称
        "中车眉山车辆有限公司",  # 招标方名称
        "投标文件",  # 无效关键词
        "法定代表人",  # 无效关键词
        "XXX公司（盖章）",  # 包含干扰字符
        "A" * 100,  # 过长名称
        "",  # 空名称
        "公司",  # 过短名称
    ]
    
    print("测试有效的公司名称:")
    for name in valid_names:
        is_valid = _is_valid_company_name(name)
        looks_garbled = _looks_garbled_or_incomplete(name)
        filtered_name = _filter_bidder_name(name)
        print(f"  {name}")
        print(f"    - 有效公司名称: {is_valid}")
        print(f"    - 是否乱码: {looks_garbled}")
        print(f"    - 过滤后名称: {filtered_name}")
        print()
    
    print("测试无效的公司名称:")
    for name in invalid_names:
        is_valid = _is_valid_company_name(name)
        looks_garbled = _looks_garbled_or_incomplete(name)
        filtered_name = _filter_bidder_name(name)
        print(f"  {repr(name)}")
        print(f"    - 有效公司名称: {is_valid}")
        print(f"    - 是否乱码: {looks_garbled}")
        print(f"    - 过滤后名称: {filtered_name}")
        print()

if __name__ == "__main__":
    test_bidder_name_validation()