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
from modules.detailed_score_display import get_detailed_score_data, get_price_display_data  # 添加这行导入
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
def get_filename_from_path(file_path: str) -> str:
    """从文件路径中提取文件名"""
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
    db = None
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        try:
            data = request.get_json()
            bid_documents = data.get('bid_documents', [])

            if not bid_documents:
                return jsonify({'error': '没有提供投标文件'}), 400

            # 验证项目存在
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 更新投标人名称
            updated_documents = []
            for bid_doc_data in bid_documents:
                bid_doc_id = bid_doc_data.get('id')
                new_bidder_name = bid_doc_data.get('bidder_name')

                if not bid_doc_id or not new_bidder_name:
                    continue

                bid_doc = db.query(BidDocument).filter(BidDocument.id == bid_doc_id).first()
                if bid_doc and bid_doc.project_id == project_id:
                    bid_doc.bidder_name = new_bidder_name
                    updated_documents.append(bid_doc)

            db.commit()

            # 准备分析任务
            bid_files_info = []
            for doc in updated_documents:
                bid_files_info.append(
                    {
                        'bid_document_id': doc.id,
                        'tender_file_path': project.tender_file_path,
                        'bid_file_path': doc.file_path,
                        'bidder_name': doc.bidder_name,
                    }
                )

            # 启动后台分析任务
            # 注意：在实际应用中，这里可能需要使用线程或任务队列来处理后台任务
            # 这里简化处理，直接调用分析函数
            # run_analysis_and_calculate_prices(project_id, bid_files_info)

            # 更新项目状态
            project.status = 'processing'
            db.commit()

            logging.info(
                f'项目 {project_id} 开始分析，包含 {len(bid_files_info)} 个投标文件'
            )

            return jsonify({
                'message': '分析任务已启动',
                'project_id': project_id,
                'bid_documents_count': len(bid_files_info),
            })
        finally:
            try:
                next(db_gen)  # 触发finally块
            except StopIteration:
                pass

    except Exception as e:
        if db:
            try:
                db.rollback()
            except:
                pass
        logging.error(f'启动分析任务时出错: {e}')
        return jsonify({'error': f'启动分析失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/confirm-names-and-start-analysis', methods=['POST'])
def confirm_names_and_start_analysis(project_id):
    """确认投标人名称并开始分析"""
    db = None
    try:
        # 获取数据库会话
        with get_db() as db:
            data = request.get_json()
            bid_documents = data.get('bid_documents', [])

            if not bid_documents:
                return jsonify({'error': '没有提供投标文件'}), 400

            # 验证项目存在
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 更新投标人名称
            updated_documents = []
            for bid_doc_data in bid_documents:
                bid_doc_id = bid_doc_data.get('id')
                new_bidder_name = bid_doc_data.get('bidder_name')

                if not bid_doc_id or not new_bidder_name:
                    continue

                bid_doc = db.query(BidDocument).filter(BidDocument.id == bid_doc_id).first()
                if bid_doc and bid_doc.project_id == project_id:
                    bid_doc.bidder_name = new_bidder_name
                    updated_documents.append(bid_doc)

            db.commit()

            # 准备分析任务
            bid_files_info = []
            for doc in updated_documents:
                bid_files_info.append(
                    {
                        'bid_document_id': doc.id,
                        'tender_file_path': project.tender_file_path,
                        'bid_file_path': doc.file_path,
                        'bidder_name': doc.bidder_name,
                    }
                )

            # 启动后台分析任务
            # 注意：在实际应用中，这里可能需要使用线程或任务队列来处理后台任务
            # 这里简化处理，直接调用分析函数
            # run_analysis_and_calculate_prices(project_id, bid_files_info)

            # 更新项目状态
            project.status = 'processing'
            db.commit()

            logging.info(
                f'项目 {project_id} 开始分析，包含 {len(bid_files_info)} 个投标文件'
            )

            return jsonify({
                'message': '分析任务已启动',
                'project_id': project_id,
                'bid_documents_count': len(bid_files_info),
            })

    except Exception as e:
        logging.error(f'确认名称并启动分析时出错: {e}')
        return jsonify({'error': f'启动分析失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/progress', methods=['GET'])
def get_project_progress(project_id):
    """获取项目进度信息，包括用时信息"""
    try:
        with get_db() as db:
            # 查询项目信息
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 计算用时信息
            elapsed_time = None
            total_time = None
            
            if project.analysis_start_time:
                if project.analysis_end_time:
                    # 分析已完成，计算总用时
                    total_time = (project.analysis_end_time - project.analysis_start_time).total_seconds()
                else:
                    # 分析进行中，计算已用时
                    elapsed_time = (datetime.utcnow() - project.analysis_start_time).total_seconds()

            # 构造响应数据
            response_data = {
                'project_id': project_id,
                'status': project.status,
                'elapsed_time': elapsed_time,  # 已用时（秒）
                'total_time': total_time,      # 总用时（秒）
                'analysis_start_time': project.analysis_start_time.isoformat() if project.analysis_start_time else None,
                'analysis_end_time': project.analysis_end_time.isoformat() if project.analysis_end_time else None,
            }

            # 如果项目状态是处理中，添加详细进度信息
            if project.status == 'processing' or project.status == 'analyzing':
                # 查询投标文件进度
                bid_documents = db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
                
                overall_progress = 0
                completed_count = 0
                total_count = len(bid_documents)
                
                detailed_progress = {}
                for doc in bid_documents:
                    filename = get_filename_from_path(doc.file_path)
                    if doc.processing_status == 'completed':
                        progress = 100
                        completed_count += 1
                    elif doc.processing_status == 'error':
                        progress = 0
                    else:
                        # 根据规则完成情况计算进度
                        if doc.progress_total_rules > 0:
                            progress = min(100, (doc.progress_completed_rules / doc.progress_total_rules) * 100)
                        else:
                            progress = 0
                    
                    detailed_progress[filename] = round(progress, 1)
                
                if total_count > 0:
                    overall_progress = (completed_count / total_count) * 100
                
                response_data['overall_progress'] = round(overall_progress, 1)
                response_data['detailed_progress'] = detailed_progress
                response_data['completed_files'] = completed_count
                response_data['total_files'] = total_count

            return jsonify(response_data)

    except Exception as e:
        logging.error(f'获取项目进度时出错: {e}')
        return jsonify({'error': f'获取进度失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/results', methods=['GET'])
def get_project_results(project_id):
    """获取项目分析结果"""
    try:
        with get_db() as db:
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 查询分析结果
            results = db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).all()
            
            # 格式化结果数据
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'id': result.id,
                    'bidder_name': result.bidder_name,
                    'total_score': result.total_score,
                    'price_score': result.price_score,
                    'extracted_price': result.extracted_price,
                    'analyzed_at': result.analyzed_at.isoformat() if result.analyzed_at else None,
                })

            # 按总分降序排列
            formatted_results.sort(key=lambda x: x['total_score'] or 0, reverse=True)

            return jsonify({
                'project_id': project_id,
                'project_name': project.name,
                'results': formatted_results,
                'analysis_end_time': project.analysis_end_time.isoformat() if project.analysis_end_time else None,
            })

    except Exception as e:
        logging.error(f'获取项目结果时出错: {e}')
        return jsonify({'error': f'获取结果失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/summary', methods=['GET'])
def get_project_summary(project_id):
    """获取项目汇总数据"""
    try:
        summary_data = generate_summary_data(project_id)
        return jsonify(summary_data)
    except Exception as e:
        logging.error(f'生成项目汇总时出错: {e}')
        return jsonify({'error': f'生成汇总失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/export-summary', methods=['GET'])
def export_project_summary(project_id):
    """导出项目汇总表"""
    try:
        # 生成汇总数据
        summary_data = generate_summary_data(project_id)
        
        if not summary_data or 'error' in summary_data:
            return jsonify({'error': '无法生成汇总数据'}), 500

        # 创建Word文档
        doc = Document()
        doc.add_heading(f'项目 {summary_data["project_name"]} 汇总表', 0)

        # 添加项目信息
        doc.add_paragraph(f'项目ID: {summary_data["project_id"]}')
        doc.add_paragraph(f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

        # 添加汇总表
        if summary_data.get('results'):
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            
            # 表头
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '投标人'
            hdr_cells[1].text = '总分'
            hdr_cells[2].text = '价格分'
            hdr_cells[3].text = '投标报价'
            hdr_cells[4].text = '分析时间'

            # 数据行
            for result in summary_data['results']:
                row_cells = table.add_row().cells
                row_cells[0].text = result.get('bidder_name', '')
                row_cells[1].text = str(result.get('total_score', ''))
                row_cells[2].text = str(result.get('price_score', ''))
                row_cells[3].text = str(result.get('extracted_price', ''))
                row_cells[4].text = result.get('analyzed_at', '')[:19] if result.get('analyzed_at') else ''

        # 保存文档
        filename = f'project_{project_id}_summary.docx'
        filepath = Path('temp') / filename
        filepath.parent.mkdir(exist_ok=True)
        doc.save(str(filepath))

        # 返回文件
        return send_file(str(filepath), as_attachment=True, download_name=filename)

    except Exception as e:
        logging.error(f'导出汇总表时出错: {e}')
        return jsonify({'error': f'导出失败: {str(e)}'}), 500
