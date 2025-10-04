#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 页面路由
# 处理静态页面和模板渲染
#

from flask import Blueprint, render_template, send_file, make_response
import os
from pathlib import Path

# 创建蓝图
router = Blueprint('pages', __name__)

@router.route('/', methods=['GET'])
def read_root():
    """主页面"""
    try:
        return render_template('index.html')
    except Exception as e:
        return f'<h1>错误</h1><p>模板加载失败: {str(e)}</p>', 500

@router.route('/favicon.ico')
def favicon():
    """返回站点图标，避免浏览器404请求。"""
    try:
        # 尝试多个可能的图标路径
        favicon_paths = [
            'public/favicon/favicon.ico',
            'templates/favicon.ico',
            'favicon.ico',
        ]

        for path in favicon_paths:
            if os.path.exists(path):
                response = make_response(send_file(
                    path,
                    mimetype='image/x-icon'
                ))
                response.headers['Cache-Control'] = 'public, max-age=86400'
                return response

        # 如果没有找到图标文件，返回空响应
        return '', 204

    except Exception:
        return '', 404

@router.route('/history', methods=['GET'])
def history_page():
    """历史记录页面"""
    try:
        return render_template('history.html')
    except Exception as e:
        return f'<h1>错误</h1><p>历史页面模板加载失败: {str(e)}</p>', 500

@router.route('/settings', methods=['GET'])
def settings_page():
    """系统设置页面"""
    try:
        return render_template('settings.html')
    except Exception as e:
        return f'<h1>错误</h1><p>系统设置页面加载失败: {str(e)}</p>', 500
