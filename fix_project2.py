#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:10:18
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:10:22
# 文件相对于项目的路径   : \AI_env2\fix_project2.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复项目2的状态
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, AnalysisResult


def fix_project2():
    """
    修复项目2的状态
    """
    print('修复项目2的状态')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查项目2
        project = session.query(TenderProject).filter(TenderProject.id == 2).first()
        if not project:
            print('错误：项目2不存在')
            return

        print('项目信息:')
        print(f'  ID: {project.id}')
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 更新项目状态为pending，以便重新上传文件
        project.status = 'pending'
        session.commit()
        print('  已将项目状态更新为pending')

        # 删除投标文档记录
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 2).all()
        for doc in bid_docs:
            print(f'  删除投标文档: {doc.bidder_name}')
            session.delete(doc)

        session.commit()
        print('  已删除所有投标文档记录')

        # 删除分析结果记录
        analysis_results = (
            session.query(AnalysisResult).filter(AnalysisResult.project_id == 2).all()
        )
        for result in analysis_results:
            print(f'  删除分析结果: {result.id}')
            session.delete(result)

        session.commit()
        print('  已删除所有分析结果记录')

        session.close()
        print('\n项目2已重置，现在可以重新上传文件并进行分析。')

    except Exception as e:
        print(f'修复过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    fix_project2()
