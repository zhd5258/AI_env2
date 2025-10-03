#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试加密PDF处理功能
"""

import os
import sys
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor

# 设置日志级别
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_encrypted_pdf():
    """测试加密PDF处理功能"""
    # 这里需要一个加密的PDF文件进行测试
    # 由于我们没有实际的加密PDF文件，我们只测试类的导入和方法是否存在
    try:
        # 创建一个PDFProcessor实例（使用一个不存在的文件路径）
        processor = PDFProcessor("test_encrypted.pdf")
        
        # 检查新增的方法是否存在
        if hasattr(processor, '_try_decrypt_pdf'):
            print("✓ _try_decrypt_pdf 方法存在")
        else:
            print("✗ _try_decrypt_pdf 方法不存在")
            
        if hasattr(processor, '_open_pdf_with_decryption'):
            print("✓ _open_pdf_with_decryption 方法存在")
        else:
            print("✗ _open_pdf_with_decryption 方法不存在")
            
        print("加密PDF处理功能测试完成")
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")

if __name__ == "__main__":
    test_encrypted_pdf()
