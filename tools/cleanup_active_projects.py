#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-26 12:02:13
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-26 12:02:16
# 文件相对于项目的路径   : \AI_ENV2\tools\cleanup_active_projects.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
清理活动项目工具
用于清理系统中的活动分析项目，释放服务器资源
"""

import requests
import json


def list_active_projects():
    """列出所有活动项目"""
    print('获取活动项目列表...')
    try:
        response = requests.get('http://localhost:8000/api/projects', timeout=10)
        if response.status_code == 200:
            projects = response.json()
            active_projects = [
                p
                for p in projects
                if p.get('status') in ['analyzing', 'processing', 'pending']
            ]

            print(f'找到 {len(active_projects)} 个活动项目:')
            for project in active_projects:
                print(
                    f'  项目ID: {project["id"]}, 名称: {project["name"]}, 状态: {project["status"]}'
                )

            return active_projects
        else:
            print(f'获取项目列表失败: {response.status_code}')
            return []
    except Exception as e:
        print(f'获取项目列表出错: {e}')
        return []


def cancel_project(project_id):
    """取消指定项目"""
    print(f'取消项目 {project_id}...')
    try:
        # 这里我们发送一个请求来更新项目状态为取消
        # 实际实现可能需要根据API的具体设计来调整
        response = requests.post(
            f'http://localhost:8000/api/projects/{project_id}/cancel', timeout=30
        )

        if response.status_code in [200, 204]:
            print(f'  项目 {project_id} 已取消')
            return True
        else:
            print(f'  取消项目 {project_id} 失败: {response.status_code}')
            return False
    except Exception as e:
        print(f'  取消项目 {project_id} 出错: {e}')
        return False


def force_cleanup_projects():
    """强制清理项目"""
    print('强制清理项目...')
    try:
        response = requests.post(
            'http://localhost:8000/api/projects/force-cleanup', timeout=60
        )

        if response.status_code == 200:
            result = response.json()
            print(f'  清理完成: {result}')
            return True
        else:
            print(f'  清理失败: {response.status_code}')
            return False
    except Exception as e:
        print(f'  清理出错: {e}')
        return False


def check_system_status():
    """检查系统状态"""
    print('\n检查系统状态...')

    # 检查API响应
    try:
        response = requests.get('http://localhost:8000/api/runtime-config', timeout=10)
        print(
            f'  API状态: {"正常" if response.status_code == 200 else f"异常 ({response.status_code})"}'
        )
    except Exception as e:
        print(f'  API状态: 异常 ({e})')

    # 检查上传目录
    import os
    from pathlib import Path

    upload_dir = Path('uploads')
    if upload_dir.exists():
        file_count = len(list(upload_dir.iterdir()))
        print(f'  上传目录文件数: {file_count}')
    else:
        print('  上传目录不存在')


def optimize_flask_config():
    """优化Flask配置"""
    print('\n优化Flask配置...')

    # 这里我们可以建议一些配置优化
    optimizations = [
        '增加MAX_BUFFER_SIZE到128KB',
        '调整线程池大小',
        '优化文件处理流程',
        '启用GZIP压缩',
    ]

    for opt in optimizations:
        print(f'  建议: {opt}')


def main():
    """主函数"""
    print('=' * 50)
    print('活动项目清理工具')
    print('=' * 50)

    # 检查系统状态
    check_system_status()

    # 列出活动项目
    active_projects = list_active_projects()

    if not active_projects:
        print('\n没有活动项目需要清理')
        return

    print(f'\n发现 {len(active_projects)} 个活动项目')

    # 询问用户是否要清理
    choice = input('\n是否要清理这些活动项目? (y/N): ').strip().lower()

    if choice in ['y', 'yes']:
        print('\n开始清理活动项目...')

        # 尝试取消项目
        success_count = 0
        for project in active_projects:
            if cancel_project(project['id']):
                success_count += 1

        print(f'\n成功取消 {success_count}/{len(active_projects)} 个项目')

        # 如果还有项目未清理，尝试强制清理
        if success_count < len(active_projects):
            print('\n尝试强制清理...')
            force_cleanup_projects()
    else:
        print('\n取消清理操作')

    # 优化建议
    optimize_flask_config()

    print('\n' + '=' * 50)
    print('清理完成')
    print('建议重启服务器以获得最佳性能')
    print('=' * 50)


if __name__ == '__main__':
    main()
