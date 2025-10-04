#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
文件上传相关路由
"""

import logging
from flask import Blueprint, request, jsonify
from controllers.file_controller import init_upload_logic, list_project_bidders_logic
from werkzeug.exceptions import RequestEntityTooLarge

# 创建路由实例
router = Blueprint('file', __name__, url_prefix='/api')

@router.route('/init-upload', methods=['POST'])
def init_upload():
    """初始化上传：创建项目、保存文件，不提取投标人名称，等待分析完成后再提取。"""
    try:
        # 检查是否有文件
        if 'tender_file' not in request.files:
            return jsonify({"error": "缺少招标文件"}), 400
            
        if 'bid_files' not in request.files:
            return jsonify({"error": "缺少投标文件"}), 400

        tender_file = request.files['tender_file']
        bid_files = request.files.getlist('bid_files')

        if not tender_file or tender_file.filename == '':
            return jsonify({"error": "招标文件不能为空"}), 400

        if not bid_files or all(f.filename == '' for f in bid_files):
            return jsonify({"error": "投标文件不能为空"}), 400

        # 调用业务逻辑控制器
        result = init_upload_logic(tender_file, bid_files)
        return jsonify(result)
    except RequestEntityTooLarge:
        logging.error('文件上传大小超出限制')
        return jsonify({'error': '文件大小超出限制，请上传小于500MB的文件'}), 413
    except Exception as e:
        logging.error(f'初始化上传失败: {e}')
        return jsonify({'error': f'初始化上传失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/bidders', methods=['GET'])
def list_project_bidders(project_id):
    """列出项目下的投标文件与当前名称，供前端展示和编辑。"""
    try:
        # 调用业务逻辑控制器
        result = list_project_bidders_logic(project_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f'获取投标方列表失败: {e}')
        return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500
