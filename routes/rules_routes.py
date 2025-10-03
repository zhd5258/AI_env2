#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
系统规则相关路由
包括系统规则的获取、更新等操作
"""

from flask import Blueprint, jsonify, request
# 不再在模块级别导入系统规则管理器的全局实例
# from modules.system_rules_manager import system_rules_manager

# 创建蓝图
router = Blueprint('rules', __name__, url_prefix='/api/rules')

# 在需要时创建系统规则管理器实例
def get_system_rules_manager():
    from modules.system_rules_manager import SystemRulesManager
    return SystemRulesManager()

@router.route('/system', methods=['GET'])
def get_system_rules():
    """获取所有系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        # 加载规则
        system_rules_manager.load_rules()
        rules = system_rules_manager.get_all_rules()
        # 确保返回的JSON正确编码
        response_data = {
            'success': True,
            'data': rules,
            'count': len(rules)
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取系统规则失败: {str(e)}'
        }), 500

@router.route('/system/enabled', methods=['GET'])
def get_enabled_system_rules():
    """获取启用的系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        # 加载规则
        system_rules_manager.load_rules()
        rules = system_rules_manager.get_enabled_rules()
        # 确保返回的JSON正确编码
        response_data = {
            'success': True,
            'data': rules,
            'count': len(rules)
        }
        return jsonify(response_data)
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'获取启用的系统规则失败: {str(e)}'
        }), 500

@router.route('/system', methods=['POST'])
def add_system_rule():
    """添加系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        # 加载规则
        system_rules_manager.load_rules()
        data = request.get_json()
        content = data.get('content', '')
        result = system_rules_manager.add_rule(content)
        if result:
            # 保存规则到文件
            system_rules_manager.save_rules()
            return jsonify({
                'success': True,
                'message': '规则添加成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '规则添加失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'添加系统规则失败: {str(e)}'
        }), 500

@router.route('/system/<int:rule_id>', methods=['PUT'])
def update_system_rule(rule_id):
    """更新系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        # 加载规则
        system_rules_manager.load_rules()
        data = request.get_json()
        content = data.get('content')
        enabled = data.get('enabled')
        result = system_rules_manager.update_rule(
            rule_id, 
            content=content, 
            enabled=enabled
        )
        if result:
            # 保存规则到文件
            system_rules_manager.save_rules()
            return jsonify({
                'success': True,
                'message': '规则更新成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '规则不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'更新系统规则失败: {str(e)}'
        }), 500

@router.route('/system/<int:rule_id>', methods=['DELETE'])
def delete_system_rule(rule_id):
    """删除系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        # 加载规则
        system_rules_manager.load_rules()
        result = system_rules_manager.delete_rule(rule_id)
        if result:
            # 保存规则到文件
            system_rules_manager.save_rules()
            return jsonify({
                'success': True,
                'message': '规则删除成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '规则不存在'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'删除系统规则失败: {str(e)}'
        }), 500

@router.route('/system/reload', methods=['POST'])
def reload_system_rules():
    """重新加载系统规则"""
    try:
        # 创建系统规则管理器实例
        system_rules_manager = get_system_rules_manager()
        result = system_rules_manager.load_rules()
        if result:
            return jsonify({
                'success': True,
                'message': '系统规则重新加载成功'
            })
        else:
            return jsonify({
                'success': False,
                'error': '系统规则重新加载失败'
            }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'重新加载系统规则失败: {str(e)}'
        }), 500
