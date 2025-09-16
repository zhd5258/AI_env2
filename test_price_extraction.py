#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试价格提取模块的修复效果
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.enhanced_price_extractor import EnhancedPriceExtractor
from modules.price_manager import PriceManager

def test_price_extraction():
    """
    测试价格提取功能
    """
    print("测试价格提取模块...")
    print("=" * 60)
    
    # 模拟"投标一览表"页面内容
    test_pages = [
        "投标函\n投标项目：XXX项目\n投标报价：￥1,729,800.00\n大写：壹佰柒拾贰万玖仟捌佰元整",
        "投标一览表\n项目名称：XXX项目\n投标单位：山东创杰智慧装备科技有限公司\n小写金额：￥2,270,000.00\n大写金额：贰佰贰拾柒万元整",
        "其他页面内容\n分项报价：￥50,000.00\n其他内容..."
    ]
    
    # 创建价格提取器
    extractor = EnhancedPriceExtractor()
    prices = extractor.extract_enhanced_prices(test_pages)
    
    print("提取到的所有价格:")
    for price in prices:
        print(f"  - 价格: {price['value']}, 页面: {price['page']}, 置信度: {price['confidence']}, 原因: {price['reason']}")
    
    # 创建价格管理器
    price_manager = PriceManager()
    best_price = price_manager.select_best_price(prices, test_pages)
    
    print(f"\n选择的最佳价格: {best_price}")
    
    # 验证结果
    expected_price = 2270000.0  # 应该是投标一览表中的价格
    if best_price == expected_price:
        print("✓ 价格提取正确!")
        return True
    else:
        print("✗ 价格提取错误!")
        return False

if __name__ == "__main__":
    success = test_price_extraction()
    if success:
        print("\n测试通过!")
    else:
        print("\n测试失败!")