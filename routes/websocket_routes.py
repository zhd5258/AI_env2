#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
WebSocket路由
处理WebSocket连接和事件
"""

from flask import request
from flask_socketio import join_room, leave_room, emit
from modules.websocket_manager import get_socketio
import logging

logger = logging.getLogger(__name__)
socketio = get_socketio()


@socketio.on('connect')
def handle_connect():
    """处理客户端连接"""
    logger.info('WebSocket客户端已连接')
    emit('connected', {'status': 'connected'})


@socketio.on('disconnect')
def handle_disconnect():
    """处理客户端断开连接"""
    logger.info('WebSocket客户端已断开连接')


@socketio.on('join_project')
def handle_join_project(data):
    """
    加入项目房间，接收该项目的进度更新
    
    Args:
        data: 包含project_id的字典
    """
    project_id = data.get('project_id')
    if project_id:
        room = f'project_{project_id}'
        join_room(room)
        logger.info(f'客户端加入项目房间: {room}')
        emit('joined', {'room': room, 'project_id': project_id})


@socketio.on('leave_project')
def handle_leave_project(data):
    """
    离开项目房间
    
    Args:
        data: 包含project_id的字典
    """
    project_id = data.get('project_id')
    if project_id:
        room = f'project_{project_id}'
        leave_room(room)
        logger.info(f'客户端离开项目房间: {room}')
        emit('left', {'room': room, 'project_id': project_id})

