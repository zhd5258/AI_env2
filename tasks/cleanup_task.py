#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-03 14:35:44
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 14:35:46
#文件相对于项目的路径   : \AI_env2\tasks\cleanup_task.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
清理任务
"""

import os
import logging
from pathlib import Path

def cleanup_temp_files():
    """清理临时文件"""
    try:
        # 清理temp目录
        temp_dir = Path('temp')
        if temp_dir.exists():
            for file_path in temp_dir.glob('*'):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                    elif file_path.is_dir():
                        # 递归删除目录
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    logging.warning(f'无法删除文件 {file_path}: {e}')
        
        # 清理temp_uploads目录
        temp_uploads_dir = Path('temp/uploads')
        if temp_uploads_dir.exists():
            for file_path in temp_uploads_dir.glob('*'):
                try:
                    if file_path.is_file():
                        file_path.unlink()
                    elif file_path.is_dir():
                        # 递归删除目录
                        import shutil
                        shutil.rmtree(file_path)
                except Exception as e:
                    logging.warning(f'无法删除文件 {file_path}: {e}')
                    
        logging.info('临时文件清理完成')
    except Exception as e:
        logging.error(f'清理临时文件时出错: {e}')
