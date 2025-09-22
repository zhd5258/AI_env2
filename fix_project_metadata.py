#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:16:20
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:16:23
# 文件相对于项目的路径   : \AI_env2\fix_project_metadata.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复项目元数据问题
为没有名称和描述的项目添加默认值
"""

import sys
import os
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject


def fix_project_metadata():
    """
    修复项目元数据问题
    """
    print('修复项目元数据问题')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 查找所有项目
        projects = session.query(TenderProject).all()
        print(f'项目总数: {len(projects)}')

        fixed_count = 0
        for project in projects:
            updated = False

            # 如果项目名称为空，设置默认名称
            if not project.name:
                project.name = f'项目-{project.id}'
                updated = True
                print(f"  项目 {project.id}: 设置默认名称为 '{project.name}'")

            # 如果项目代码为空，设置默认代码
            if not project.project_code:
                project.project_code = f'PROJ-{project.id:03d}'
                updated = True
                print(f"  项目 {project.id}: 设置默认代码为 '{project.project_code}'")

            # 如果描述为空，设置默认描述
            if not project.description:
                project.description = f'自动创建于 {project.created_at.strftime("%Y-%m-%d %H:%M:%S") if project.created_at else "未知时间"}'
                updated = True
                print(f"  项目 {project.id}: 设置默认描述为 '{project.description}'")

            if updated:
                fixed_count += 1

        if fixed_count > 0:
            session.commit()
            print(f'\n成功修复 {fixed_count} 个项目的元数据。')
        else:
            print('\n所有项目的元数据都已正确设置。')

        session.close()

    except Exception as e:
        print(f'修复过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    fix_project_metadata()
