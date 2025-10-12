#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 路由模块初始化文件
# 用于导入所有路由模块
#

# 注意：为了避免循环导入，我们不在此处导入具体的路由模块
# 而是在main.py中直接导入各个路由模块

__all__ = [
    'config_router',
    'project_router',
    'analysis_router',
    'export_router',
    'page_router',
    'file_router',
]
