#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查江西中霖环境科技集团有限公司投标文件中的价格提取情况
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager
from modules.enhanced_price_extractor import EnhancedPriceExtractor

def check_jiangxi_price_extraction():
    """
    检查江西中霖环境科技集团有限公司投标文件中的价格提取情况
    """
    print("检查江西中霖环境科技集团有限公司投标文件中的价格提取情况")
    print("=" * 60)
    
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
        
        # 查找包含"价格一览表"或类似关键词的页面
        print("\n查找包含价格相关关键词的页面:")
        price_keywords = ['价格一览表', '投标一览表', '开标一览表', '报价表', '总价']
        for i, page_text in enumerate(pages):
            for keyword in price_keywords:
                if keyword in page_text:
                    print(f"  第 {i+1} 页包含关键词: {keyword}")
                    # 显示该页的部分内容（前500个字符）
                    print(f"    页面内容预览: {page_text[:500]}...")
                    print("-" * 40)
        
        # 使用价格提取器提取价格
        print("\n使用增强价格提取器提取价格:")
        extractor = EnhancedPriceExtractor()
        prices = extractor.extract_enhanced_prices(pages)
        print(f"提取到 {len(prices)} 个价格:")
        
        for i, price_info in enumerate(prices):
            print(f"  价格 {i+1}: {price_info['value']} (置信度: {price_info['confidence']}, 来源页: {price_info['page']+1})")
        
        # 使用智能选择方法选择最佳价格
        print("\n使用智能方法选择最佳价格:")
        best_price = extractor.select_best_total_price(prices)
        print(f"选择的最佳价格: {best_price}")
        
        # 使用价格管理器提取和选择价格
        print("\n使用价格管理器提取和选择价格:")
        price_manager = PriceManager()
        extracted_prices = price_manager.extract_prices_from_content(pages)
        selected_price = price_manager.select_best_price(extracted_prices, pages)
        print(f"价格管理器提取到 {len(extracted_prices)} 个价格")
        print(f"价格管理器选择的最佳价格: {selected_price}")
        
        # 详细分析置信度最高的几个价格
        print("\n详细分析置信度最高的几个价格:")
        sorted_prices = sorted(prices, key=lambda x: x['confidence'], reverse=True)
        for i, price_info in enumerate(sorted_prices[:5]):  # 分析前5个
            page_index = price_info['page']
            page_text = pages[page_index]
            price_value = price_info['value']
            confidence = price_info['confidence']
            
            print(f"\n  价格 {i+1} (置信度: {confidence}):")
            print(f"    数值: {price_value}")
            print(f"    来源页: {page_index + 1}")
            
            # 查找该价格在页面中的上下文
            price_str = str(price_value)
            if price_str in page_text:
                # 找到价格在文本中的位置
                pos = page_text.find(price_str)
                # 提取前后各100个字符作为上下文
                start = max(0, pos - 100)
                end = min(len(page_text), pos + len(price_str) + 100)
                context = page_text[start:end]
                print(f"    上下文: ...{context}...")
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_jiangxi_price_extraction()