#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 页面路由
# 处理页面渲染相关的路由
#

from flask import Blueprint, render_template, request

# 创建蓝图
router = Blueprint('pages', __name__)


@router.route('/')
def index():
    """首页"""
    return render_template('index.html')


@router.route('/history')
def history():
    """历史项目页面"""
    return render_template('history.html')


@router.route('/settings')
def settings():
    """系统设置页面"""
    return render_template('settings.html')


@router.route('/qualitative-review')
def qualitative_review():
    """符合性审查表页面"""
    return render_template('qualitative_review.html')
