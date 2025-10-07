#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 分析相关路由
# 处理投标分析、评分计算等功能
#

from flask import Blueprint, request, jsonify, send_file
from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from contextlib import contextmanager
from modules.price_score_calculator import PriceScoreCalculator
from modules.summary_generator import generate_summary_data
from modules.result_display import ResultDisplay  # 添加这行导入
from modules.detailed_score_display import (
    get_detailed_score_data,
    get_price_display_data,
)  # 添加这行导入
from pathlib import Path
import logging
import json
import pandas as pd
from datetime import datetime
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

# 设置url_prefix为/api，保持与其他路由一致
router = Blueprint('analysis', __name__, url_prefix='/api')


# 辅助函数：从文件路径提取文件名
def get_filename_from_path(file_path) -> str:
    """从文件路径中提取文件名"""
    # 处理SQLAlchemy Column类型
    if hasattr(file_path, 'value'):
        file_path = file_path.value
    elif hasattr(file_path, '__str__'):
        file_path = str(file_path)

    if not file_path:
        return ''
    return Path(file_path).name


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 数据模型（简化版，替代Pydantic模型）
class StartAnalysisRequest:
    def __init__(self, bid_documents=None, bidders=None):
        self.bid_documents = bid_documents
        self.bidders = bidders

    def get_bid_documents(self):
        """获取投标文件列表，兼容两种字段名"""
        return self.bid_documents or self.bidders or []


class ScoreUpdateItem:
    def __init__(self, result_id, bidder_name, scores):
        self.result_id = result_id
        self.bidder_name = bidder_name
        self.scores = scores


@router.route('/projects/<int:project_id>/start-analysis', methods=['POST'])
def start_analysis(project_id):
    """启动项目分析"""
    try:
        # 获取数据库会话
        with get_db() as db:
            data = request.get_json()
            bid_documents = data.get('bid_documents', [])

            if not bid_documents:
                return jsonify({'error': '没有提供投标文件'}), 400

            # 验证项目存在
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 更新投标人名称
            updated_documents = []
            for bid_doc_data in bid_documents:
                bid_doc_id = bid_doc_data.get('id')
                new_bidder_name = bid_doc_data.get('bidder_name')

                if not bid_doc_id or not new_bidder_name:
                    continue

                bid_doc = (
                    db.query(BidDocument).filter(BidDocument.id == bid_doc_id).first()
                )
                if bid_doc and bid_doc.project_id == project_id:
                    bid_doc.bidder_name = new_bidder_name
                    updated_documents.append(bid_doc)

            db.commit()

            # 准备分析任务
            bid_files_info = []
            for doc in updated_documents:
                bid_files_info.append(
                    {
                        'id': doc.id,
                        'tender_file_path': project.tender_file_path,
                        'bid_file_path': doc.file_path,
                        'bidder_name': doc.bidder_name,
                    }
                )

            # 启动后台分析任务
            # 注意：在实际应用中，这里可能需要使用线程或任务队列来处理后台任务
            # 这里简化处理，直接调用分析函数
            from modules.analysis_manager import AnalysisManager

            analysis_manager = AnalysisManager(db_session=db)
            # 在新线程中运行分析任务，避免阻塞主线程
            import threading

            analysis_thread = threading.Thread(
                target=analysis_manager.run_analysis_and_calculate_prices,
                args=(project_id, bid_files_info),
            )
            analysis_thread.start()

            # 更新项目状态
            project.status = 'processing'
            db.commit()

            logging.info(
                f'项目 {project_id} 开始分析，包含 {len(bid_files_info)} 个投标文件'
            )

            return jsonify(
                {
                    'message': '分析任务已启动',
                    'project_id': project_id,
                    'bid_documents_count': len(bid_files_info),
                }
            )

    except Exception as e:
        logging.error(f'启动分析任务时出错: {e}')
        return jsonify({'error': f'启动分析失败: {str(e)}'}), 500


@router.route(
    '/projects/<int:project_id>/confirm-names-and-start-analysis', methods=['POST']
)
def confirm_names_and_start_analysis(project_id):
    """确认投标人名称并开始分析"""
    try:
        # 获取数据库会话
        with get_db() as db:
            data = request.get_json()
            bid_documents = data.get('bid_documents', [])

            if not bid_documents:
                return jsonify({'error': '没有提供投标文件'}), 400

            # 验证项目存在
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 更新投标人名称
            updated_documents = []
            for bid_doc_data in bid_documents:
                bid_doc_id = bid_doc_data.get('id')
                new_bidder_name = bid_doc_data.get('bidder_name')

                if not bid_doc_id or not new_bidder_name:
                    continue

                bid_doc = (
                    db.query(BidDocument).filter(BidDocument.id == bid_doc_id).first()
                )
                if bid_doc and bid_doc.project_id == project_id:
                    bid_doc.bidder_name = new_bidder_name
                    updated_documents.append(bid_doc)

            db.commit()

            # 准备分析任务
            bid_files_info = []
            for doc in updated_documents:
                bid_files_info.append(
                    {
                        'id': doc.id,
                        'tender_file_path': project.tender_file_path,
                        'bid_file_path': doc.file_path,
                        'bidder_name': doc.bidder_name,
                    }
                )

            # 启动后台分析任务
            # 注意：在实际应用中，这里可能需要使用线程或任务队列来处理后台任务
            # 这里简化处理，直接调用分析函数
            from modules.analysis_manager import AnalysisManager

            analysis_manager = AnalysisManager(db_session=db)
            # 在新线程中运行分析任务，避免阻塞主线程
            import threading

            analysis_thread = threading.Thread(
                target=analysis_manager.run_analysis_and_calculate_prices,
                args=(project_id, bid_files_info),
            )
            analysis_thread.start()

            # 更新项目状态
            project.status = 'processing'
            db.commit()

            logging.info(
                f'项目 {project_id} 确认名称并开始分析，包含 {len(bid_files_info)} 个投标文件'
            )

            return jsonify(
                {
                    'message': '分析任务已启动',
                    'project_id': project_id,
                    'bid_documents_count': len(bid_files_info),
                }
            )
    except Exception as e:
        logging.error(f'确认名称并启动分析时出错: {e}')
        return jsonify({'error': f'启动分析失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/progress', methods=['GET'])
def get_project_progress(project_id):
    """获取项目进度信息，包括用时信息"""
    try:
        with get_db() as db:
            # 查询项目信息
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 计算用时信息
            elapsed_time = None
            total_time = None

            if project.analysis_start_time:
                if project.analysis_end_time:
                    # 分析已完成，计算总用时
                    total_time = (
                        project.analysis_end_time - project.analysis_start_time
                    ).total_seconds()
                else:
                    # 分析进行中，计算已用时
                    elapsed_time = (
                        datetime.utcnow() - project.analysis_start_time
                    ).total_seconds()

            # 构造响应数据
            response_data = {
                'project_id': project_id,
                'project_status': project.status,  # 修改字段名以匹配前端期望
                'elapsed_time': elapsed_time,  # 已用时（秒）
                'total_time': total_time,  # 总用时（秒）
                'analysis_start_time': project.analysis_start_time.isoformat()
                if project.analysis_start_time
                else None,
                'analysis_end_time': project.analysis_end_time.isoformat()
                if project.analysis_end_time
                else None,
            }

            # 如果项目状态是处理中，添加详细进度信息
            if project.status == 'processing' or project.status == 'analyzing':
                # 查询投标文件进度
                bid_documents = (
                    db.query(BidDocument)
                    .filter(BidDocument.project_id == project_id)
                    .all()
                )

                overall_progress = 0
                completed_count = 0
                total_count = len(bid_documents)

                # 为前端JavaScript准备数据格式
                document_statuses = []
                bids = []  # 兼容main.js中的数据格式

                for doc in bid_documents:
                    filename = get_filename_from_path(doc.file_path)

                    # 计算进度
                    if doc.processing_status == 'completed':
                        progress = 100
                        completed_count += 1
                    elif doc.processing_status == 'error':
                        progress = 0
                    else:
                        # 根据规则完成情况计算进度
                        if doc.progress_total_rules > 0:
                            progress = min(
                                100,
                                (
                                    doc.progress_completed_rules
                                    / doc.progress_total_rules
                                )
                                * 100,
                            )
                        else:
                            progress = 0

                    # 准备文档状态信息
                    # 确保投标人名称不为空
                    bidder_name = (
                        doc.bidder_name
                        if doc.bidder_name and doc.bidder_name.strip()
                        else '未知投标方'
                    )
                    doc_status = {
                        'id': doc.id,
                        'bidder_name': bidder_name,
                        'file_path': doc.file_path,
                        'processing_status': doc.processing_status,
                        'processing_phase': doc.processing_phase,  # 添加处理阶段信息
                        'progress_total': doc.progress_total_rules,
                        'progress_completed': doc.progress_completed_rules,
                        'current_rule': doc.progress_current_rule,  # 添加当前规则信息
                        'error_message': doc.error_message,
                        'progress': round(progress, 1),
                    }
                    document_statuses.append(doc_status)

                    # 兼容main.js的数据格式
                    # 确保投标人名称不为空
                    bidder_name = (
                        doc.bidder_name
                        if doc.bidder_name and doc.bidder_name.strip()
                        else '未知投标方'
                    )
                    bid_info = {
                        'id': doc.id,
                        'bidder_name': bidder_name,
                        'file_path': doc.file_path,
                        'status': doc.processing_status,
                        'processing_phase': doc.processing_phase,
                        'progress_total': doc.progress_total_rules,
                        'progress_completed': doc.progress_completed_rules,
                        'current_rule': doc.progress_current_rule,
                        'error_message': doc.error_message,
                        'progress': round(progress, 1),
                    }
                    bids.append(bid_info)

                if total_count > 0:
                    overall_progress = (completed_count / total_count) * 100

                response_data['overall_progress'] = round(overall_progress, 1)
                response_data['document_statuses'] = document_statuses
                response_data['bids'] = bids  # 兼容main.js中的数据格式
                response_data['completed_files'] = completed_count
                response_data['total_files'] = total_count
                response_data['processing_status'] = project.status  # 添加处理状态

            # 如果项目已完成，确保触发汇总显示
            elif (
                project.status == 'completed'
                or project.status == 'completed_with_errors'
            ):
                # 确保分析结束时间已设置
                if not project.analysis_end_time:
                    project.analysis_end_time = datetime.datetime.utcnow()
                    db.commit()

                # 添加完成状态信息
                response_data['processing_status'] = project.status
                response_data['completed_files'] = len(
                    db.query(BidDocument)
                    .filter(
                        BidDocument.project_id == project_id,
                        BidDocument.processing_status == 'completed',
                    )
                    .all()
                )
                response_data['total_files'] = len(
                    db.query(BidDocument)
                    .filter(BidDocument.project_id == project_id)
                    .all()
                )

            return jsonify(response_data)
    except Exception as e:
        logging.error(f'获取项目进度时出错: {e}')
        return jsonify({'error': f'获取进度失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/results', methods=['GET'])
def get_project_results(project_id):
    """获取项目分析结果"""
    try:
        with get_db() as db:
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 查询分析结果
            results = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )

            # 格式化结果数据
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        'id': result.id,
                        'bidder_name': result.bidder_name,
                        'total_score': result.total_score,
                        'price_score': result.price_score,
                        'extracted_price': result.extracted_price,
                        'analyzed_at': result.analyzed_at.isoformat()
                        if result.analyzed_at
                        else None,
                    }
                )

            # 按总分降序排列
            formatted_results.sort(key=lambda x: x['total_score'] or 0, reverse=True)

            return jsonify(
                {
                    'project_id': project_id,
                    'project_name': project.name,
                    'results': formatted_results,
                    'analysis_end_time': project.analysis_end_time.isoformat()
                    if project.analysis_end_time
                    else None,
                }
            )
    except Exception as e:
        logging.error(f'获取项目结果时出错: {e}')
        return jsonify({'error': f'获取结果失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/summary', methods=['GET'])
def get_project_summary(project_id):
    """获取项目汇总数据"""
    try:
        with get_db() as db:
            summary_data = generate_summary_data(project_id, db)
            if not summary_data:
                return jsonify({'error': '无法生成汇总数据'}), 500

            # 添加项目信息到返回数据
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if project:
                summary_data['project_id'] = project_id
                summary_data['project_name'] = project.name

            return jsonify(summary_data)
    except Exception as e:
        logging.error(f'生成项目汇总时出错: {e}')
        return jsonify({'error': f'生成汇总失败: {str(e)}'}), 500


@router.route('/projects/<int:project_id>/dynamic-summary', methods=['GET'])
def get_project_dynamic_summary(project_id):
    """获取项目动态汇总表数据"""
    try:
        with get_db() as db:
            summary_data = generate_summary_data(project_id, db)
            if not summary_data:
                return jsonify({'error': '无法生成汇总数据'}), 500

            # 添加项目信息到返回数据
            project = (
                db.query(TenderProject).filter(TenderProject.id == project_id).first()
            )
            if project:
                summary_data['project_id'] = project_id
                summary_data['project_name'] = project.name

            return jsonify(summary_data)
    except Exception as e:
        logging.error(f'生成项目动态汇总时出错: {e}')
        return jsonify({'error': f'生成汇总失败: {str(e)}'}), 500
