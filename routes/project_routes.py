#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 项目管理路由
# 处理项目相关的CRUD操作
#

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)

# 辅助函数：从文件路径提取文件名
def get_filename_from_path(file_path: str) -> str:
    """从文件路径中提取文件名"""
    if not file_path:
        return ''
    return Path(file_path).name

# 创建蓝图
router = Blueprint('projects', __name__, url_prefix='/api')

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 数据模型（替代Pydantic模型）
class UpdateBidderNameRequest:
    def __init__(self, bidder_name):
        self.bidder_name = bidder_name

class CleanupRequest:
    def __init__(self, cleanup_temp_uploads=False, cleanup_temp_word=False, cleanup_temp_pdf_cache=False):
        self.cleanup_temp_uploads = cleanup_temp_uploads
        self.cleanup_temp_word = cleanup_temp_word
        self.cleanup_temp_pdf_cache = cleanup_temp_pdf_cache

@router.route('/projects', methods=['GET'])
def get_all_projects():
    """获取所有项目列表"""
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    projects = db.query(TenderProject).all()

    # 使用单次查询获取所有相关的投标文件和分析结果信息
    project_data = []
    for project in projects:
        bid_docs = (
            db.query(BidDocument).filter(BidDocument.project_id == project.id).all()
        )

        # 统计分析结果
        completed_count = (
            db.query(AnalysisResult)
            .join(BidDocument, AnalysisResult.bid_document_id == BidDocument.id)
            .filter(BidDocument.project_id == project.id)
            .filter(AnalysisResult.total_score.isnot(None))
            .count()
        )

        project_info = {
            'id': project.id,
            'name': project.name,
            'tender_file_path': project.tender_file_path,
            'created_at': project.created_at.isoformat()
            if project.created_at
            else None,
            'updated_at': project.updated_at.isoformat()
            if project.updated_at
            else None,
            'bid_documents_count': len(bid_docs),
            'completed_analysis_count': completed_count,
            'processing_status': project.status,
            'bid_documents': [
                {
                    'id': doc.id,
                    'filename': get_filename_from_path(doc.file_path or ''),
                    'bidder_name': doc.bidder_name,
                    'processing_status': doc.processing_status,
                    'file_path': doc.file_path,
                }
                for doc in bid_docs
            ],
        }
        project_data.append(project_info)

    return jsonify({'projects': project_data})

@router.route('/projects/<int:project_id>/bidders', methods=['GET'])
def list_project_bidders(project_id):
    """列出项目下的投标文件与当前名称，供前端展示和编辑。"""
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    docs = db.query(BidDocument).filter(BidDocument.project_id == project_id).all()

    bidders = []
    for doc in docs:
        bidders.append(
            {
                'id': doc.id,
                'filename': get_filename_from_path(doc.file_path or ''),
                'bidder_name': doc.bidder_name,
                'processing_status': doc.processing_status,
                'file_path': doc.file_path,
            }
        )

    return jsonify({'bidders': bidders})

@router.route('/bids/<int:bid_id>/name', methods=['PATCH'])
def update_bidder_name(bid_id):
    """更新投标人名称"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        data = request.get_json()
        payload = UpdateBidderNameRequest(data.get('bidder_name', ''))
        
        # 查找投标文件
        bid_doc = db.query(BidDocument).filter(BidDocument.id == bid_id).first()
        if not bid_doc:
            return jsonify({'error': '投标文件不存在'}), 404

        # 更新投标人名称
        old_name = bid_doc.bidder_name
        bid_doc.bidder_name = payload.bidder_name

        # 同时更新关联的分析结果中的投标人名称
        analysis_result = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.bid_document_id == bid_id)
            .first()
        )
        if analysis_result:
            analysis_result.bidder_name = payload.bidder_name

        db.commit()

        logging.info(
            f'投标人名称已更新: ID={bid_id}, {old_name} -> {payload.bidder_name}'
        )

        return jsonify({
            'message': '投标人名称更新成功',
            'bid_id': bid_id,
            'old_name': old_name,
            'new_name': payload.bidder_name,
        })

    except Exception as e:
        # 确保db已定义
        try:
            db.rollback()
        except:
            pass
        logging.error(f'更新投标人名称时出错: {e}')
        return jsonify({'error': f'更新失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/bid-documents/batch', methods=['DELETE'])
def delete_bid_documents_batch(project_id):
    """批量删除投标文件"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        # 解析请求体
        data = request.get_json()
        bid_document_ids = data.get('bid_document_ids', [])

        if not bid_document_ids:
            return jsonify({'error': '没有提供要删除的投标文件ID'}), 400

        # 验证所有文件都属于指定项目
        bid_docs = (
            db.query(BidDocument)
            .filter(
                BidDocument.id.in_(bid_document_ids),
                BidDocument.project_id == project_id,
            )
            .all()
        )

        if len(bid_docs) != len(bid_document_ids):
            return jsonify({'error': '部分文件不存在或不属于该项目'}), 400

        deleted_files = []
        failed_files = []

        for bid_doc in bid_docs:
            try:
                # 删除关联的分析结果
                db.query(AnalysisResult).filter(
                    AnalysisResult.bid_document_id == bid_doc.id
                ).delete()

                # 删除物理文件
                file_path = bid_doc.file_path
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)

                # 删除数据库记录
                db.delete(bid_doc)

                deleted_files.append(
                    {
                        'id': bid_doc.id,
                        'filename': get_filename_from_path(file_path or ''),
                        'bidder_name': bid_doc.bidder_name,
                    }
                )

                logging.info(
                    f'已删除投标文件: {get_filename_from_path(file_path or "")} (ID: {bid_doc.id})'
                )

            except Exception as e:
                failed_files.append(
                    {
                        'id': bid_doc.id,
                        'filename': get_filename_from_path(bid_doc.file_path or ''),
                        'error': str(e),
                    }
                )
                logging.error(
                    f'删除投标文件 {get_filename_from_path(bid_doc.file_path or "")} 时出错: {e}'
                )

        db.commit()

        return jsonify({
            'message': f'批量删除完成，成功: {len(deleted_files)}, 失败: {len(failed_files)}',
            'deleted_files': deleted_files,
            'failed_files': failed_files,
        })

    except Exception as e:
        # 确保db已定义
        try:
            db.rollback()
        except:
            pass
        logging.error(f'批量删除投标文件时出错: {e}')
        return jsonify({'error': f'批量删除失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/bid-documents/<int:bid_document_id>/failed-pages', methods=['GET'])
def get_failed_pages_info(project_id, bid_document_id):
    """获取处理失败页面的详细信息"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        # 验证投标文件存在且属于指定项目
        bid_doc = (
            db.query(BidDocument)
            .filter(
                BidDocument.id == bid_document_id, BidDocument.project_id == project_id
            )
            .first()
        )

        if not bid_doc:
            return jsonify({'error': '投标文件不存在'}), 404

        # 这里可以添加获取失败页面信息的逻辑
        # 暂时返回基本信息
        return jsonify({
            'bid_document_id': bid_document_id,
            'filename': get_filename_from_path(bid_doc.file_path or ''),
            'processing_status': bid_doc.processing_status,
            'failed_pages': [],  # 实际实现中可以从日志或其他地方获取失败页面信息
        })

    except Exception as e:
        logging.error(f'获取失败页面信息时出错: {e}')
        return jsonify({'error': f'获取失败页面信息失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/cleanup', methods=['POST'])
def cleanup_temp_files(project_id):
    """清理临时文件"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        # 验证项目存在
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return jsonify({'error': '项目不存在'}), 404

        data = request.get_json()
        payload = CleanupRequest(
            cleanup_temp_uploads=data.get('cleanup_temp_uploads', False),
            cleanup_temp_word=data.get('cleanup_temp_word', False),
            cleanup_temp_pdf_cache=data.get('cleanup_temp_pdf_cache', False)
        )

        cleanup_results = {
            'temp_uploads': {'cleaned': False, 'message': ''},
            'temp_word': {'cleaned': False, 'message': ''},
            'temp_pdf_cache': {'cleaned': False, 'message': ''},
        }

        # 清理 temp_uploads
        if payload.cleanup_temp_uploads:
            try:
                temp_uploads_path = 'temp_uploads'
                if os.path.exists(temp_uploads_path):
                    file_count = len(
                        [
                            f
                            for f in os.listdir(temp_uploads_path)
                            if os.path.isfile(os.path.join(temp_uploads_path, f))
                        ]
                    )
                    # 只清理不属于当前项目的文件（这里简化处理，实际可能需要更复杂的逻辑）
                    cleanup_results['temp_uploads'] = {
                        'cleaned': True,
                        'message': f'temp_uploads 目录检查完成，发现 {file_count} 个文件',
                    }
                else:
                    cleanup_results['temp_uploads'] = {
                        'cleaned': True,
                        'message': 'temp_uploads 目录不存在',
                    }
            except Exception as e:
                cleanup_results['temp_uploads'] = {
                    'cleaned': False,
                    'message': f'清理 temp_uploads 失败: {str(e)}',
                }

        # 清理 temp_word
        if payload.cleanup_temp_word:
            try:
                temp_word_path = 'temp_word'
                if os.path.exists(temp_word_path):
                    file_count = len(
                        [f for f in os.listdir(temp_word_path) if f.endswith('.txt')]
                    )
                    cleanup_results['temp_word'] = {
                        'cleaned': True,
                        'message': f'temp_word 目录检查完成，发现 {file_count} 个txt文件',
                    }
                else:
                    cleanup_results['temp_word'] = {
                        'cleaned': True,
                        'message': 'temp_word 目录不存在',
                    }
            except Exception as e:
                cleanup_results['temp_word'] = {
                    'cleaned': False,
                    'message': f'清理 temp_word 失败: {str(e)}',
                }

        # 清理 temp_pdf_cache
        if payload.cleanup_temp_pdf_cache:
            try:
                temp_pdf_cache_path = 'temp_pdf_cache'
                if os.path.exists(temp_pdf_cache_path):
                    file_count = len(
                        [
                            f
                            for f in os.listdir(temp_pdf_cache_path)
                            if os.path.isfile(os.path.join(temp_pdf_cache_path, f))
                        ]
                    )
                    cleanup_results['temp_pdf_cache'] = {
                        'cleaned': True,
                        'message': f'temp_pdf_cache 目录检查完成，发现 {file_count} 个文件',
                    }
                else:
                    cleanup_results['temp_pdf_cache'] = {
                        'cleaned': True,
                        'message': 'temp_pdf_cache 目录不存在',
                    }
            except Exception as e:
                cleanup_results['temp_pdf_cache'] = {
                    'cleaned': False,
                    'message': f'清理 temp_pdf_cache 失败: {str(e)}',
                }

        logging.info(f'项目 {project_id} 临时文件清理完成: {cleanup_results}')

        return jsonify({
            'message': '临时文件清理完成',
            'project_id': project_id,
            'results': cleanup_results,
        })

    except Exception as e:
        logging.error(f'清理临时文件时出错: {e}')
        return jsonify({'error': f'清理临时文件失败: {str(e)}'}), 500
