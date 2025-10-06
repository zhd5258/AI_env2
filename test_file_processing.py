#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-06 14:07:37
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-06 14:07:40
#文件相对于项目的路径   : \AI_env2\test_file_processing.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from controllers.file_controller import init_upload_logic
from werkzeug.datastructures import FileStorage
import tempfile

def test_file_processing():
    """测试文件处理功能"""
    # 创建一个简单的PDF文件用于测试
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tender_file:
        tender_file.write(b'%PDF-1.4\n%Test tender file content')
        tender_file_path = tender_file.name
        
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as bid_file:
        bid_file.write(b'%PDF-1.4\n%Test bid file content')
        bid_file_path = bid_file.name
    
    try:
        # 创建模拟的文件对象
        tender_file_storage = FileStorage(
            stream=open(tender_file_path, 'rb'),
            filename='test_tender.pdf',
            content_type='application/pdf'
        )
        
        bid_file_storage = FileStorage(
            stream=open(bid_file_path, 'rb'),
            filename='test_bid.pdf',
            content_type='application/pdf'
        )
        
        # 调用上传逻辑
        result = init_upload_logic(tender_file_storage, [bid_file_storage])
        print(f"Upload result: {result}")
        
    except Exception as e:
        print(f"Error during file processing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # 清理临时文件
        try:
            os.unlink(tender_file_path)
            os.unlink(bid_file_path)
            tender_file_storage.close()
            bid_file_storage.close()
        except:
            pass

if __name__ == "__main__":
    test_file_processing()
