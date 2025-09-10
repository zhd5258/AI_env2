#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-10 21:42:20
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-10 21:42:22
# 文件相对于项目的路径   : \AI_env2\view_pdf_pages.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查看PDF指定页码内容的程序
"""

import sys
import os

# 添加项目根目录到 Python 路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor


def view_specific_pages(pdf_file_path, start_page, end_page):
    """查看PDF指定页码的内容"""
    if not os.path.exists(pdf_file_path):
        print(f'文件不存在: {pdf_file_path}')
        return

    try:
        # 使用PDF处理器提取文本
        print(f'正在处理PDF文件: {pdf_file_path}')
        processor = PDFProcessor(pdf_file_path)
        pages_text = processor.process_pdf_per_page()

        print(f'PDF文件共 {len(pages_text)} 页')

        # 显示指定页码的内容
        for i in range(start_page - 1, min(end_page, len(pages_text))):
            print(f'\n{"=" * 60}')
            print(f'第 {i + 1} 页内容 (字符数: {len(pages_text[i])}):')
            print(f'{"=" * 60}')
            if len(pages_text[i].strip()) > 0:
                print(pages_text[i])
            else:
                print('[该页无文本内容]')

    except Exception as e:
        print(f'处理PDF文件时出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    # 指定PDF文件路径
    pdf_file_path = r'D:\user\PythonProject\AI_env2\uploads\24_tender_招标文件正文.pdf'

    # 默认查看第14-16页
    start_page = 14
    end_page = 16

    # 如果通过命令行参数指定了页码范围，则使用该范围
    if len(sys.argv) > 2:
        start_page = int(sys.argv[1])
        end_page = int(sys.argv[2])
    elif len(sys.argv) > 1:
        page_num = int(sys.argv[1])
        start_page = page_num
        end_page = page_num

    view_specific_pages(pdf_file_path, start_page, end_page)
