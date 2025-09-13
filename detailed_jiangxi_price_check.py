#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
详细检查江西中霖环境科技集团有限公司投标文件中的价格信息
"""

import sys
import os
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor

def detailed_jiangxi_price_check():
    """
    详细检查江西中霖环境科技集团有限公司投标文件中的价格信息
    """
    print("详细检查江西中霖环境科技集团有限公司投标文件中的价格信息")
    print("=" * 70)
    
    # 江西中霖环境科技集团有限公司投标文件路径
    file_path = r"uploads\6_bid_江西中霖环境科技集团投标文件.pdf"
    
    if not os.path.exists(file_path):
        print(f"错误：文件不存在 {file_path}")
        return
    
    try:
        # 处理PDF文件
        print("处理PDF文件...")
        processor = PDFProcessor(file_path)
        pages = processor.process_pdf_per_page()
        print(f"提取到 {len(pages)} 页文本")
        
        # 重点检查第39页（投标一览表）
        print("\n详细检查第39页（投标一览表）:")
        page_39 = pages[38]  # 0-based index
        print("第39页内容:")
        print(page_39)
        
        # 查找价格相关模式
        print("\n查找第39页中的价格信息:")
        # 查找"小写"价格
        xiaoxie_match = re.search(r'小写.*?(\d[\d,]*\.?\d*)', page_39, re.IGNORECASE)
        if xiaoxie_match:
            xiaoxie_price = xiaoxie_match.group(1)
            print(f"  小写价格: {xiaoxie_price}")
        
        # 查找"大写"价格
        daxie_match = re.search(r'大写.*?([壹贰叁肆伍陆柒捌玖拾佰仟万亿零一二三四五六七八九十百千万亿]+)', page_39, re.IGNORECASE)
        if daxie_match:
            daxie_price_text = daxie_match.group(1)
            print(f"  大写价格文本: {daxie_price_text}")
        
        # 查找总价模式
        total_matches = re.findall(r'(\d[\d,]*\.?\d*)', page_39)
        print(f"  找到的所有数字: {total_matches}")
        
        # 重点检查第41页（分项报价表末尾的总价）
        print("\n详细检查第41页（分项报价表末尾的总价）:")
        page_41 = pages[40]  # 0-based index
        print("第41页内容:")
        print(page_41)
        
        # 查找总价相关模式
        print("\n查找第41页中的价格信息:")
        # 查找"总报价"或"总价"
        total_price_match = re.search(r'(总报价|总价).*?(\d[\d,]*\.?\d*)', page_41, re.IGNORECASE)
        if total_price_match:
            total_label = total_price_match.group(1)
            total_price = total_price_match.group(2)
            print(f"  {total_label}: {total_price}")
        
        # 查找所有数字
        all_numbers_41 = re.findall(r'(\d[\d,]*\.?\d*)', page_41)
        print(f"  找到的所有数字: {all_numbers_41}")
        
        # 查找最大的数字，很可能是总价
        if all_numbers_41:
            # 转换为浮点数并找到最大值
            numbers_41_float = []
            for num_str in all_numbers_41:
                try:
                    # 移除逗号并转换为浮点数
                    num_float = float(num_str.replace(',', ''))
                    numbers_41_float.append((num_float, num_str))
                except ValueError:
                    pass
            
            if numbers_41_float:
                # 按数值大小排序
                numbers_41_float.sort(key=lambda x: x[0], reverse=True)
                print(f"  按大小排序的数字:")
                for i, (num_val, num_str) in enumerate(numbers_41_float[:10]):  # 显示前10个最大的
                    print(f"    {i+1}. {num_str} ({num_val})")
        
        # 检查价格提取器可能遗漏的模式
        print("\n检查可能被价格提取器遗漏的价格模式:")
        
        # 查找"投标总价"、"总报价"等关键词附近的数字
        price_keywords = ['投标总价', '总报价', '总价', '投标报价', '合计']
        for keyword in price_keywords:
            for i, page_text in enumerate(pages):
                if keyword in page_text:
                    print(f"\n  第 {i+1} 页包含关键词 '{keyword}':")
                    # 查找关键词后100字符内的数字
                    keyword_pos = page_text.find(keyword)
                    if keyword_pos != -1:
                        # 提取关键词后的内容
                        content_after = page_text[keyword_pos:keyword_pos+200]  # 关键词后200字符
                        numbers_after = re.findall(r'(\d[\d,]*\.?\d*)', content_after)
                        print(f"    关键词后的内容: ...{content_after}...")
                        print(f"    找到的数字: {numbers_after}")
                        
                        # 查找最大的数字
                        if numbers_after:
                            max_number = max(numbers_after, key=lambda x: float(x.replace(',', '')))
                            print(f"    最大数字: {max_number}")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    detailed_jiangxi_price_check()