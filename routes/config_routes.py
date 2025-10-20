#!/usr/bin/env python
# -*- coding:utf-8 -*-


from flask import Blueprint, request, jsonify
import logging
import os
import json

from modules.runtime_config import (
    load_config,
    save_config,
    load_config_for_project,
    save_config_for_project,
    get_bool,
)

# 创建蓝图
router = Blueprint('config', __name__, url_prefix='/api')

# 全局变量 (从配置文件加载初始值)
RUNTIME_CONFIG = load_config()

# OCR配置相关变量
OCR_CONFIG_FILE = 'ocr_config.json'
DEFAULT_OCR_CONFIG = {
    'ocr_engine': 'mineru_online',
    'dpi': 300,
    'max_side': 1024,
    'lang': 'ch',
    'use_gpu': True,
    'det_model_dir': None,
    'rec_model_dir': None,
    'cls_model_dir': None,
    'mineru_api_token': 'eyJ0eXBlIjoiSldUIiwiYWxnIjoiSFM1MTIifQ.eyJqdGkiOiI2MzIwMDAzMyIsInJvbCI6IlJPTEVfUkVHSVNURVIiLCJpc3MiOiJPcGVuWExhYiIsImlhdCI6MTc2MDg0MDM2OSwiY2xpZW50SWQiOiJsa3pkeDU3bnZ5MjJqa3BxOXgydyIsInBob25lIjoiIiwib3BlbklkIjpudWxsLCJ1dWlkIjoiMzJjZjlkMWQtMjIzMi00NzAwLWI1YzItOTAwYTU0ZDViNjk1IiwiZW1haWwiOiJ6aGQ1MjU4QDE2My5jb20iLCJleHAiOjE3NjIwNDk5Njl9.sdAaT6nt2oyEIaqGaM-Vuj7rBkJrwOX-YbpXtETopxx8uY86mC49s4MTM4kc7y3jgUuN08pcc6OUBxjNBQe5lg',
    'mineru_api_url': 'https://mineru.net/api/v4',
    'fallback_to_local': True,
}


def load_ocr_config():
    """加载OCR配置"""
    if os.path.exists(OCR_CONFIG_FILE):
        try:
            with open(OCR_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f'加载OCR配置失败: {e}')
    return DEFAULT_OCR_CONFIG.copy()


def save_ocr_config(config):
    """保存OCR配置"""
    try:
        with open(OCR_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logging.error(f'保存OCR配置失败: {e}')
        return False


@router.route('/runtime-config', methods=['GET'])
def get_runtime_config():
    """获取当前运行参数配置（全局默认）。"""
    return jsonify(RUNTIME_CONFIG)


@router.route('/runtime-config', methods=['POST'])
def update_runtime_config():
    """更新全局运行参数默认配置（数值校验+落盘+内存刷新）。"""
    global RUNTIME_CONFIG

    try:
        data = request.get_json()

        # 验证参数范围
        updates = {k: v for k, v in data.items() if v is not None}

        if 'max_concurrent_analysis' in updates:
            if not (1 <= updates['max_concurrent_analysis'] <= 10):
                return jsonify({'error': 'max_concurrent_analysis必须在1-10之间'}), 400

        if 'processing_timeout' in updates:
            if not (30 <= updates['processing_timeout'] <= 1800):
                return jsonify({'error': 'processing_timeout必须在30-1800秒之间'}), 400

        # 验证文件上传大小限制（1MB到1000MB之间）
        if 'max_content_length' in updates:
            max_content_length = updates['max_content_length']
            # 确保是整数且在合理范围内
            try:
                max_content_length = int(max_content_length)
                if not (1 * 1024 * 1024 <= max_content_length <= 1000 * 1024 * 1024):
                    return jsonify(
                        {'error': '文件上传大小限制必须在1MB到1000MB之间'}
                    ), 400
                updates['max_content_length'] = max_content_length
            except (ValueError, TypeError):
                return jsonify({'error': '文件上传大小限制必须是整数'}), 400

        # 验证单个文件大小限制（1MB到500MB之间）
        if 'single_file_max_size' in updates:
            single_file_max_size = updates['single_file_max_size']
            # 确保是整数且在合理范围内
            try:
                single_file_max_size = int(single_file_max_size)
                if not (1 * 1024 * 1024 <= single_file_max_size <= 500 * 1024 * 1024):
                    return jsonify(
                        {'error': '单个文件大小限制必须在1MB到500MB之间'}
                    ), 400
                updates['single_file_max_size'] = single_file_max_size
            except (ValueError, TypeError):
                return jsonify({'error': '单个文件大小限制必须是整数'}), 400

        # 验证自动删除MD文件配置
        if 'auto_delete_md_files' in updates:
            # 确保是布尔值
            try:
                updates['auto_delete_md_files'] = bool(updates['auto_delete_md_files'])
            except (ValueError, TypeError):
                return jsonify({'error': '自动删除MD文件配置必须是布尔值'}), 400

        # 验证质量不达标时重新分析配置
        if 'enable_retry_on_quality_issue' in updates:
            # 确保是布尔值
            try:
                updates['enable_retry_on_quality_issue'] = bool(
                    updates['enable_retry_on_quality_issue']
                )
            except (ValueError, TypeError):
                return jsonify({'error': '质量不达标时重新分析配置必须是布尔值'}), 400

        # 更新配置
        RUNTIME_CONFIG.update(updates)

        # 保存到文件
        save_config(RUNTIME_CONFIG)
        logging.info(f'全局运行配置已更新: {updates}')
        return jsonify({'message': '配置更新成功', 'config': RUNTIME_CONFIG})

    except Exception as e:
        logging.error(f'更新运行配置时出错: {e}')
        return jsonify({'error': f'更新配置失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/runtime-config', methods=['GET'])
def get_project_runtime_config(project_id):
    """获取项目级运行参数配置（不存在则返回并创建默认）。"""
    try:
        config = load_config_for_project(project_id)
        if config is None:
            # 创建默认配置
            config = RUNTIME_CONFIG.copy()
            save_config_for_project(project_id, config)

        return jsonify(config)

    except Exception as e:
        logging.error(f'获取项目 {project_id} 运行配置时出错: {e}')
        return jsonify({'error': f'获取项目配置失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/runtime-config', methods=['POST'])
def update_project_runtime_config(project_id):
    """更新项目级运行参数配置（数值校验+落盘）。"""
    try:
        data = request.get_json()

        # 验证参数范围（同全局配置）
        updates = {k: v for k, v in data.items() if v is not None}

        if 'max_concurrent_analysis' in updates:
            if not (1 <= updates['max_concurrent_analysis'] <= 10):
                return jsonify({'error': 'max_concurrent_analysis必须在1-10之间'}), 400

        if 'processing_timeout' in updates:
            if not (30 <= updates['processing_timeout'] <= 1800):
                return jsonify({'error': 'processing_timeout必须在30-1800秒之间'}), 400

        # 验证文件上传大小限制（1MB到1000MB之间）
        if 'max_content_length' in updates:
            max_content_length = updates['max_content_length']
            # 确保是整数且在合理范围内
            try:
                max_content_length = int(max_content_length)
                if not (1 * 1024 * 1024 <= max_content_length <= 1000 * 1024 * 1024):
                    return jsonify(
                        {'error': '文件上传大小限制必须在1MB到1000MB之间'}
                    ), 400
                updates['max_content_length'] = max_content_length
            except (ValueError, TypeError):
                return jsonify({'error': '文件上传大小限制必须是整数'}), 400

        # 验证单个文件大小限制（1MB到500MB之间）
        if 'single_file_max_size' in updates:
            single_file_max_size = updates['single_file_max_size']
            # 确保是整数且在合理范围内
            try:
                single_file_max_size = int(single_file_max_size)
                if not (1 * 1024 * 1024 <= single_file_max_size <= 500 * 1024 * 1024):
                    return jsonify(
                        {'error': '单个文件大小限制必须在1MB到500MB之间'}
                    ), 400
                updates['single_file_max_size'] = single_file_max_size
            except (ValueError, TypeError):
                return jsonify({'error': '单个文件大小限制必须是整数'}), 400

        # 验证自动删除MD文件配置
        if 'auto_delete_md_files' in updates:
            # 确保是布尔值
            try:
                updates['auto_delete_md_files'] = bool(updates['auto_delete_md_files'])
            except (ValueError, TypeError):
                return jsonify({'error': '自动删除MD文件配置必须是布尔值'}), 400

        # 获取当前项目配置
        current_config = load_config_for_project(project_id) or RUNTIME_CONFIG.copy()

        # 更新配置
        current_config.update(updates)

        # 保存项目配置
        if save_config_for_project(project_id, current_config):
            logging.info(f'项目 {project_id} 运行配置已更新: {updates}')
            return jsonify({'message': '项目配置更新成功', 'config': current_config})
        else:
            return jsonify({'error': '项目配置保存失败'}), 500

    except Exception as e:
        logging.error(f'更新项目 {project_id} 运行配置时出错: {e}')
        return jsonify({'error': f'更新项目配置失败: {str(e)}'}), 500


@router.route('/ocr-config', methods=['GET'])
def get_ocr_config():
    """获取当前OCR配置"""
    return jsonify(
        {
            'success': True,
            'data': load_ocr_config(),
            'available_engines': [
                'smart',
                'rapid',
                'pp_ocrv5',
                'hybrid',
                'optimized',
                'v3_2',
                '3_2_final',
            ],
        }
    )


@router.route('/ocr-config', methods=['POST'])
def update_ocr_config():
    """更新OCR配置"""
    try:
        data = request.get_json()

        # 验证OCR引擎
        valid_engines = [
            'smart',
            'rapid',
            'pp_ocrv5',
            'hybrid',
            'optimized',
            'v3_2',
            '3_2_final',
            'mineru_online',
            'mineru_local',
        ]

        if data.get('ocr_engine') not in valid_engines:
            return jsonify(
                {
                    'success': False,
                    'error': f'无效的OCR引擎: {data.get("ocr_engine")}',
                    'valid_engines': valid_engines,
                }
            ), 400

        # 保存配置
        if save_ocr_config(data):
            logging.info(f'OCR配置已更新: {data}')
            return jsonify(
                {
                    'success': True,
                    'message': 'OCR配置更新成功',
                    'config': data,
                }
            )
        else:
            return jsonify({'success': False, 'error': 'OCR配置保存失败'}), 500

    except Exception as e:
        logging.error(f'更新OCR配置时出错: {e}')
        return jsonify(
            {
                'success': False,
                'error': f'更新OCR配置失败: {str(e)}',
            }
        ), 500
