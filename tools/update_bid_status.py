#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-08 11:07:43
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-08 11:48:38
#文件相对于项目的路径   : \AI_ENV2\tools\update_bid_status.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
更新投标文件状态的脚本
将处理状态为processing的投标文件更新为completed
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.database import SessionLocal, TenderProject, BidDocument


def update_bid_document_status():
    """更新投标文件状态"""
    db = SessionLocal()
    try:
        # 获取所有状态为analyzing的项目
        projects = (
            db.query(TenderProject).filter(TenderProject.status == 'analyzing').all()
        )
        print(f'检查 {len(projects)} 个正在分析的项目...')

        updated_count = 0

        for project in projects:
            print(f'\n检查项目 {project.id}: {project.name}')

            # 获取该项目的所有投标文件
            bid_docs = (
                db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
            )

            # 检查是否有状态为processing的投标文件
            processing_docs = [
                d for d in bid_docs if d.processing_status == 'processing'
            ]

            if processing_docs:
                print(
                    f'  发现 {len(processing_docs)} 个状态为processing的投标文件，正在更新...'
                )

                # 将状态为processing的投标文件更新为completed
                for doc in processing_docs:
                    print(f'    更新 {doc.bidder_name} 的状态: processing -> completed')
                    doc.processing_status = 'completed'
                    updated_count += 1

                db.commit()
                print(f'  项目 {project.id} 的投标文件状态已更新')
            else:
                print(f'  项目 {project.id} 无需要更新的投标文件')

        print(f'\n总共更新了 {updated_count} 个投标文件')

    except Exception as e:
        print(f'更新过程中出错: {e}')
        import traceback

        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == '__main__':
    update_bid_document_status()
