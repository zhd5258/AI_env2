#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:17:25
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:19:15
# 文件相对于项目的路径   : \AI_env2\verify_project_fix.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
验证项目元数据修复是否成功
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject


def verify_project_fix():
    """
    验证项目元数据修复是否成功
    """
    print('验证项目元数据修复是否成功')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 查找所有项目
        projects = session.query(TenderProject).all()
        print(f'项目总数: {len(projects)}')

        for project in projects:
            print(f'  项目 ID: {project.id}')
            print(f'    名称: {project.name}')
            print(f'    项目代码: {project.project_code}')
            print(f'    描述: {project.description}')
            print(f'    状态: {project.status}')
            print(f'    创建时间: {project.created_at}')
            print()

        session.close()

    except Exception as e:
        print(f'验证过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    verify_project_fix()
