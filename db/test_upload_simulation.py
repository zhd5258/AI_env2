#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-25 17:38:22
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-25 17:38:25
# 文件相对于项目的路径   : \AI_ENV2\db\test_upload_simulation.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-

"""
模拟文件上传测试脚本
"""

import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# 导入数据库模型
from models.database import DATABASE_URL, Base, BidDocument, get_local_time

# 创建引擎和会话
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def test_upload_simulation():
    """模拟文件上传测试"""
    print('开始模拟文件上传测试...')

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 创建一个测试BidDocument记录
        test_document = BidDocument(
            project_id=1,
            bidder_name='测试公司',
            file_path='uploads/test_file.pdf',
            original_filename='测试文件.pdf',
            file_size=1024,
            upload_time=get_local_time(),
            processing_status='pending',
            updated_at=get_local_time(),  # 这个字段之前缺失导致错误
            progress_total_rules=0,
            progress_completed_rules=0,
            processing_phase='uploaded',
        )

        # 添加到数据库
        db.add(test_document)
        db.commit()
        db.refresh(test_document)

        print(f'✅ 测试记录创建成功，ID: {test_document.id}')

        # 验证记录
        retrieved_document = (
            db.query(BidDocument).filter(BidDocument.id == test_document.id).first()
        )
        if retrieved_document:
            print(f'✅ 记录验证成功，updated_at: {retrieved_document.updated_at}')
        else:
            print('❌ 记录验证失败')

        # 清理测试数据
        db.delete(test_document)
        db.commit()
        print('✅ 测试数据已清理')

        return True

    except Exception as e:
        print(f'❌ 测试失败: {e}')
        db.rollback()
        return False
    finally:
        db.close()


if __name__ == '__main__':
    success = test_upload_simulation()
    if success:
        print('\n🎉 文件上传模拟测试成功!')
    else:
        print('\n💥 文件上传模拟测试失败!')
