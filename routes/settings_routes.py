#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-04 10:41:40
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-04 10:44:26
#文件相对于项目的路径   : \AI_env2\routes\settings_routes.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 系统设置路由
# 处理系统参数设置相关功能
#

from flask import Blueprint, render_template, jsonify
from modules.system_maintenance import clear_database, cleanup_uploads_directory, cleanup_all_temp_directories

# 创建蓝图
router = Blueprint('settings', __name__, url_prefix='/api')

@router.route('/settings', methods=['GET'])
def settings_page():
    """系统设置页面"""
    try:
        return render_template('settings.html')
    except Exception as e:
        return f'<h1>错误</h1><p>系统设置页面加载失败: {str(e)}</p>', 500

@router.route('/settings/maintenance/clear-database', methods=['POST'])
def clear_database_endpoint():
    """清空数据库端点"""
    try:
        success = clear_database()
        if success:
            return jsonify({'success': True, 'message': '数据库已清空'})
        else:
            return jsonify({'success': False, 'message': '清空数据库失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'清空数据库时出错: {str(e)}'}), 500

@router.route('/settings/maintenance/cleanup-uploads', methods=['POST'])
def cleanup_uploads_endpoint():
    """清理上传目录端点"""
    try:
        success = cleanup_uploads_directory()
        if success:
            return jsonify({'success': True, 'message': '上传目录已清理'})
        else:
            return jsonify({'success': False, 'message': '清理上传目录失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'清理上传目录时出错: {str(e)}'}), 500

@router.route('/settings/maintenance/cleanup-temp', methods=['POST'])
def cleanup_temp_endpoint():
    """清理临时目录端点"""
    try:
        success = cleanup_all_temp_directories()
        if success:
            return jsonify({'success': True, 'message': '临时目录已清理'})
        else:
            return jsonify({'success': False, 'message': '清理临时目录失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'message': f'清理临时目录时出错: {str(e)}'}), 500
