#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
完整测试价格提取模块的修复效果
模拟真实的投标文件内容
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.enhanced_price_extractor import EnhancedPriceExtractor
from modules.price_manager import PriceManager

def test_real_scenario():
    """
    测试真实场景下的价格提取
    """
    print("测试真实场景下的价格提取...")
    print("=" * 60)
    
    # 模拟真实的投标文件页面内容（包含多个投标人）
    test_pages = [
        # 第一页：投标函
        """投标函
致：招标人
根据贵方为 项目名称 的招标文件，遵照《中华人民共和国招标投标法》等有关规定，我方经踏勘现场和研究上述招标文件的投标须知、合同条款、技术规范、图纸和其他有关文件后，我方愿以人民币（大写）壹佰柒拾贰万玖仟捌佰元整（￥1,729,800.00）的投标报价并按上述图纸、合同条款、技术规范和其他有关文件要求承包上述工程的施工、竣工和保修。
      
投标人：江苏鑫桥环保科技有限公司
法定代表人或其委托代理人：（签字或盖章）
日期：2023年5月20日""",
        
        # 第二页：投标一览表（这是应该优先提取的价格）
        """投标一览表
项目名称：XXX项目
标段号：第一标段
投标单位：山东创杰智慧装备科技有限公司
投标报价：
小写金额：￥2,270,000.00
大写金额：贰佰贰拾柒万元整
工期：120日历天
质量标准：合格
项目经理：张三
执业证书名称及编号：注册建造师、XXXXXX
      
投标人：山东创杰智慧装备科技有限公司（盖章）
法定代表人或其委托代理人：（签字或盖章）
日期：2023年5月20日""",
        
        # 第三页：分项报价表（这些不应该被提取为总价）
        """分项报价表
序号 项目名称        数量  单位  单价（元）  合价（元）
1    设备采购        1     批    1,500,000   1,500,000
2    安装调试        1     批    500,000     500,000
3    运输费          1     批    50,000      50,000
4    税费            1     批    120,000     120,000
合计金额（小写）：￥2,170,000.00
合计金额（大写）：贰佰壹拾柒万元整
      
投标人：山东创杰智慧装备科技有限公司（盖章）""",
        
        # 第四页：其他内容
        """其他内容
这里可能包含一些干扰信息，如：
项目预算：￥5,000,000.00
预付款：￥1,000,000.00
保证金：￥100,000.00"""
    ]
    
    # 创建价格提取器
    extractor = EnhancedPriceExtractor()
    prices = extractor.extract_enhanced_prices(test_pages)
    
    print("提取到的所有价格:")
    for i, price in enumerate(prices):
        print(f"  {i+1}. 价格: {price['value']:,}, 页面: {price['page']}, 置信度: {price['confidence']}, 原因: {price['reason']}")
    
    # 创建价格管理器
    price_manager = PriceManager()
    best_price = price_manager.select_best_price(prices, test_pages)
    
    print(f"\n选择的最佳价格: {best_price:,}")
    
    # 验证结果
    expected_price = 2270000.0  # 应该是投标一览表中的价格
    if best_price == expected_price:
        print("✓ 价格提取正确!")
        return True
    else:
        print("✗ 价格提取错误!")
        return False

if __name__ == "__main__":
    success = test_real_scenario()
    if success:
        print("\n真实场景测试通过!")
    else:
        print("\n真实场景测试失败!")