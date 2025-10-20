#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-20 21:33:43
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-20 21:33:46
# 文件相对于项目的路径   : \AI_ENV2\tools\extract_prices_from_output.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
从output目录下的MD文件中提取投标价格的脚本
"""

import os
import sys
import glob
import logging
from typing import Dict, List

# 添加项目根目录到Python路径
# 由于脚本现在在tools目录下，需要向上两级到达项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from modules.md_price_extractor import MDPriceExtractor

# 配置日志
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def extract_prices_from_md_files(output_dir: str) -> Dict[str, float]:
    """
    从output目录下的所有MD文件中提取价格

    Args:
        output_dir: output目录路径

    Returns:
        Dict[str, float]: 文件名到提取价格的映射
    """
    # 查找所有MD文件
    md_pattern = os.path.join(output_dir, '*.md')
    md_files = glob.glob(md_pattern)

    if not md_files:
        logger.info(f'在目录 {output_dir} 中未找到MD文件')
        return {}

    logger.info(f'找到 {len(md_files)} 个MD文件')

    # 创建价格提取器
    price_extractor = MDPriceExtractor()

    # 存储提取结果
    extracted_prices = {}

    # 遍历所有MD文件
    for md_file in md_files:
        try:
            logger.info(f'处理文件: {md_file}')

            # 提取价格
            price = price_extractor.extract_price_from_md_file(md_file)

            # 获取文件名（不含路径）
            filename = os.path.basename(md_file)

            if price is not None:
                extracted_prices[filename] = price
                logger.info(f'从 {filename} 提取到价格: {price}')
            else:
                logger.warning(f'未能从 {filename} 提取到价格')
                extracted_prices[filename] = 0.0

        except Exception as e:
            logger.error(f'处理文件 {md_file} 时出错: {e}')
            filename = os.path.basename(md_file)
            extracted_prices[filename] = 0.0

    return extracted_prices


def print_extracted_prices(prices: Dict[str, float]):
    """
    打印提取的价格结果

    Args:
        prices: 文件名到价格的映射
    """
    print('\n' + '=' * 50)
    print('投标价格提取结果')
    print('=' * 50)

    if not prices:
        print('未提取到任何价格信息')
        return

    # 按文件名排序
    sorted_prices = sorted(prices.items())

    for filename, price in sorted_prices:
        print(f'{filename:50} : {price:>15,.2f}')

    print('=' * 50)
    print(f'总计: {len(prices)} 个文件')

    # 计算总金额
    total_amount = sum(prices.values())
    print(f'总金额: {total_amount:>13,.2f}')
    print('=' * 50)


def main():
    """主函数"""
    output_dir = os.path.join(project_root, 'output')

    if not os.path.exists(output_dir):
        logger.error(f'目录 {output_dir} 不存在')
        return

    print('开始从output目录下的MD文件中提取投标价格...')

    # 提取价格
    prices = extract_prices_from_md_files(output_dir)

    # 打印结果
    print_extracted_prices(prices)

    print('\n价格提取完成!')


if __name__ == '__main__':
    main()
