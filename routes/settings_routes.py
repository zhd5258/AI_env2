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

from flask import Blueprint, render_template

# 创建蓝图
router = Blueprint('settings', __name__, url_prefix='/api')

@router.route('/settings', methods=['GET'])
def settings_page():
    """系统设置页面"""
    try:
        return render_template('settings.html')
    except Exception as e:
        return f'<h1>错误</h1><p>系统设置页面加载失败: {str(e)}</p>', 500
