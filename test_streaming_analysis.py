#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:22:04
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:27:41
# 文件相对于项目的路径   : \AI_env2\test_streaming_analysis.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:07:27
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:07:30
# 文件相对于项目的路径   : \AI_env2\test_streaming_analysis.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试流式分析功能
"""

import sys
import os
import json
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.pdf_processor import PDFProcessor


def test_streaming_analysis():
    """
    测试流式分析功能
    """
    print('测试流式分析功能')
    print('=' * 60)

    # 创建一个简单的测试PDF文件
    test_pdf_path = 'test_sample.pdf'

    # 检查是否存在测试PDF文件
    if not os.path.exists(test_pdf_path):
        print(f'测试PDF文件不存在: {test_pdf_path}')
        print('请提供一个测试PDF文件来继续测试')
        return

    print(f'使用测试PDF文件: {test_pdf_path}')

    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    try:
        print('\n开始测试流式PDF处理...')

        # 测试PDF处理器的流式处理
        processor = PDFProcessor(test_pdf_path, file_type='bid')

        # 设置流式处理回调
        def stream_callback(processed_pages: int, pages_text: list):
            print(f'  流式处理回调：已处理 {processed_pages} 页')
            if pages_text:
                print(
                    f'    最后一页文本长度: {len(pages_text[-1]) if pages_text else 0}'
                )

        processor.set_stream_callback(stream_callback)

        # 执行流式处理
        pages_text = processor.stream_process_pdf(chunk_size=3)
        print(f'\n流式处理完成，共处理 {len(pages_text)} 页')

        # 显示前几页的内容
        for i, page_text in enumerate(pages_text[:3]):
            print(f'  第{i + 1}页文本长度: {len(page_text)}')
            if page_text:
                print(f'    前100字符: {page_text[:100]}')

        print('\n流式分析测试完成')

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    test_streaming_analysis()
