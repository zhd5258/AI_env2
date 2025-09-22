#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:21:43
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:21:45
# 文件相对于项目的路径   : \AI_env2\check_file_paths.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:08:55
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:08:58
# 文件相对于项目的路径   : \AI_env2\check_file_paths.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查数据库中的文件路径
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)


def check_file_paths():
    """
    检查数据库中的文件路径
    """
    print('检查数据库中的文件路径')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查所有项目
        projects = session.query(TenderProject).all()
        print(f'项目总数: {len(projects)}')

        for project in projects:
            print(f'\n项目ID: {project.id}')
            print(f'  名称: {project.name}')
            print(f'  状态: {project.status}')
            print(f'  招标文件路径: {project.tender_file_path}')
            if project.tender_file_path:
                exists = os.path.exists(project.tender_file_path)
                print(f'  招标文件存在: {exists}')

            # 检查投标文档
            bid_docs = (
                session.query(BidDocument)
                .filter(BidDocument.project_id == project.id)
                .all()
            )
            print(f'  投标文档数量: {len(bid_docs)}')

            for doc in bid_docs:
                print(f'    文档ID: {doc.id}')
                print(f'      投标方: {doc.bidder_name}')
                print(f'      文件路径: {doc.file_path}')
                if doc.file_path:
                    exists = os.path.exists(doc.file_path)
                    print(f'      文件存在: {exists}')

        session.close()

    except Exception as e:
        print(f'检查过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    check_file_paths()
