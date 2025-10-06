#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-06 09:29:36
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-06 09:29:39
#文件相对于项目的路径   : \AI_env2\modules\system_maintenance.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
系统维护模块
提供清空数据库、清理上传文件夹、清理临时文件夹等功能
"""

import os
import shutil
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, TenderProject, BidDocument, AnalysisResult, ScoringRule, ScoreModificationHistory, ProjectAuditLog
from controllers.file_controller import get_platform_safe_path, safe_makedirs

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clear_database():
    """
    清空数据库中的所有数据
    """
    try:
        from models.database import engine, SessionLocal
        # 创建会话
        db = SessionLocal()
        
        try:
            # 按正确的依赖顺序删除数据
            db.query(ScoreModificationHistory).delete()
            db.query(ProjectAuditLog).delete()
            db.query(AnalysisResult).delete()
            db.query(ScoringRule).delete()
            db.query(BidDocument).delete()
            db.query(TenderProject).delete()
            
            # 提交更改
            db.commit()
            logger.info("数据库已清空")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"清空数据库时出错: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"连接数据库时出错: {e}")
        return False

def cleanup_directory(directory_path):
    """
    清理指定目录中的所有文件和子目录
    """
    try:
        if os.path.exists(directory_path):
            # 删除目录中的所有文件和子目录
            for filename in os.listdir(directory_path):
                file_path = os.path.join(directory_path, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    logger.error(f'删除文件 {file_path} 时出错: {e}')
            
            logger.info(f'已清空目录: {directory_path}')
            return True
        else:
            logger.info(f'目录不存在: {directory_path}')
            return True
    except Exception as e:
        logger.error(f'清理目录 {directory_path} 时出错: {e}')
        return False

def cleanup_uploads_directory():
    """
    清理上传文件目录
    """
    try:
        UPLOADS_DIR = get_platform_safe_path('uploads')
        return cleanup_directory(UPLOADS_DIR)
    except Exception as e:
        logger.error(f'清理上传目录时出错: {e}')
        return False

def cleanup_temp_directory():
    """
    清理临时文件目录
    """
    try:
        TEMP_DIR = get_platform_safe_path('temp')
        return cleanup_directory(TEMP_DIR)
    except Exception as e:
        logger.error(f'清理临时目录时出错: {e}')
        return False

def cleanup_all_temp_directories():
    """
    清理所有临时目录（包括项目根目录下的临时目录）
    """
    try:
        success = True
        
        # 清理标准temp目录
        if not cleanup_temp_directory():
            success = False
            
        # 清理项目根目录下的其他临时目录
        root_temp_dirs = ['tempX', 'temp_pdf_cache']
        for temp_dir in root_temp_dirs:
            temp_path = get_platform_safe_path(temp_dir)
            if os.path.exists(temp_path):
                if not cleanup_directory(temp_path):
                    success = False
                    
        return success
    except Exception as e:
        logger.error(f'清理所有临时目录时出错: {e}')
        return False

def cleanup_before_upload():
    """
    在上传文件前自动清空上传文件夹
    """
    return cleanup_uploads_directory()

if __name__ == "__main__":
    # 测试函数
    print("系统维护模块测试")
    print("1. 清空数据库:", clear_database())
    print("2. 清理上传目录:", cleanup_uploads_directory())
    print("3. 清理临时目录:", cleanup_temp_directory())
    print("4. 清理所有临时目录:", cleanup_all_temp_directories())
