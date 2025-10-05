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
        if db:
            try:
                db.rollback()
            except:
                pass
        logging.error(f'启动分析任务时出错: {e}')
        return jsonify({'error': f'启动分析失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/analysis-status', methods=['GET'])
def get_analysis_status(project_id):
    """获取项目分析状态"""
    import os  # 添加导入
    try:
        # 使用上下文管理器获取数据库会话
        with get_db() as db:
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 统计分析进度
            total_docs = (
                db.query(BidDocument).filter(BidDocument.project_id == project_id).count()
            )

            # 修正：只统计处理状态为completed的文档
            completed_docs = (
                db.query(BidDocument)
                .filter(BidDocument.project_id == project_id)
                .filter(BidDocument.processing_status == 'completed')
                .count()
            )

            # 获取详细状态
            bid_docs = db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
            document_statuses = []

            for doc in bid_docs:
                analysis_result = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == doc.id)
                    .first()
                )

                # 确保显示正确的投标人名称
                display_bidder_name = doc.bidder_name
                if not display_bidder_name or display_bidder_name in ['未知投标方', '待确认', 'pdf']:
                    # 如果还没有有效的投标人名称，尝试重新提取
                    try:
                        from modules.bidder_name_extractor import extract_bidder_name_from_file
                        from modules.pdf_processor import PDFProcessor
                        # 优先从MD文件提取投标人名称
                        pdf_processor = PDFProcessor(doc.file_path)
                        md_file_path = pdf_processor.get_md_file_path()
                        if os.path.exists(md_file_path):
                            extracted_name = extract_bidder_name_from_file(md_file_path)
                        else:
                            extracted_name = extract_bidder_name_from_file(doc.file_path)
                        if extracted_name and extracted_name != '未提取':
                            display_bidder_name = extracted_name
                            # 更新数据库中的投标人名称
                            doc.bidder_name = extracted_name
                            db.commit()
                        else:
                            # 如果提取失败，使用文件名作为备用方案
                            if doc.file_path:
                                filename = os.path.basename(doc.file_path)
                                display_bidder_name = os.path.splitext(filename)[0]
                            else:
                                display_bidder_name = doc.bidder_name  # 保持原值
                    except Exception as e:
                        logging.warning(f'重新提取投标人名称时出错: {e}')
                        # 如果提取失败，使用文件名作为备用方案
                        if doc.file_path:
                            filename = os.path.basename(doc.file_path)
                            display_bidder_name = os.path.splitext(filename)[0]
                        else:
                            display_bidder_name = doc.bidder_name  # 保持原值

                document_statuses.append(
                    {
                        'id': doc.id,
                        'filename': get_filename_from_path(doc.file_path or ''),  # 使用原始文件名
                        'bidder_name': display_bidder_name,
                        'processing_status': doc.processing_status,
                        'processing_phase': getattr(doc, 'processing_phase', None),
                        'has_analysis_result': analysis_result is not None,
                        'total_score': analysis_result.total_score if analysis_result else None,
                    }
                )

            # 确保进度百分比不超过100%
            progress_percentage = 0
            if total_docs > 0:
                progress_percentage = min(100.0, (completed_docs / total_docs * 100))

            return jsonify({
                'project_id': project_id,
                'processing_status': project.status,
                'total_documents': total_docs,
                'completed_documents': completed_docs,
                'progress_percentage': progress_percentage,
                'document_statuses': document_statuses,
            })
    except Exception as e:
        logging.error(f'获取项目分析状态时出错: {e}')
        return jsonify({'error': f'获取分析状态失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/results', methods=['GET'])
def get_analysis_results(project_id):
    """获取项目分析结果"""
    try:
        # 使用上下文管理器获取数据库会话
        with get_db() as db:
            results = (
                db.query(AnalysisResult)
                .join(BidDocument, AnalysisResult.bid_document_id == BidDocument.id)
                .filter(BidDocument.project_id == project_id)
                .all()
            )

            if not results:
                return jsonify({'results': []})

            # 格式化结果
            formatted_results = []
            for result in results:
                # 获取详细的评分信息
                detailed_scores = []
                if result.detailed_scores:
                    try:
                        if isinstance(result.detailed_scores, str):
                            import json
                            detailed_scores = json.loads(result.detailed_scores)
                        else:
                            detailed_scores = result.detailed_scores
                    except Exception as e:
                        logging.warning(f"解析详细评分时出错: {e}")
                        detailed_scores = []

                formatted_results.append({
                    'id': result.id,
                    'bid_document_id': result.bid_document_id,
                    'bidder_name': result.bidder_name,
                    'total_score': float(result.total_score) if result.total_score is not None else 0,
                    'price_score': float(result.price_score) if result.price_score is not None else 0,
                    'extracted_price': float(result.extracted_price) if result.extracted_price is not None else 0,
                    'analysis_summary': result.analysis_summary,
                    'analyzed_at': result.analyzed_at.isoformat() if result.analyzed_at else None,
                    'detailed_scores': detailed_scores,
                    'scoring_method': result.scoring_method,
                    'ai_model': result.ai_model,
                    'is_modified': result.is_modified,
                    'modification_count': result.modification_count,
                })

            return jsonify({'results': formatted_results})
    except Exception as e:
        logging.error(f'获取项目分析结果时出错: {e}')
        return jsonify({'error': f'获取分析结果失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/scoring-rules', methods=['GET'])
def get_scoring_rules(project_id):
    """获取项目评分规则"""
    try:
        # 获取数据库会话
        with get_db() as db:
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()

            formatted_rules = []
            for rule in rules:
                formatted_rules.append(
                    {
                        'id': rule.id,
                        'Parent_Item_Name': rule.Parent_Item_Name,
                        'Child_Item_Name': rule.Child_Item_Name,
                        'Parent_max_score': rule.Parent_max_score,
                        'Child_max_score': rule.Child_max_score,
                        'description': rule.description,
                        'project_id': rule.project_id,
                    }
                )

            return jsonify({'scoring_rules': formatted_rules})
    except Exception as e:
        logging.error(f'获取项目评分规则时出错: {e}')
        return jsonify({'error': f'获取评分规则失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/dynamic-summary', methods=['GET'])
def get_dynamic_summary(project_id):
    """获取项目动态汇总信息"""
    try:
        # 获取数据库会话
        db = SessionLocal()
        try:
            summary_data = generate_summary_data(project_id, db)
            
            # 检查是否有错误信息
            if isinstance(summary_data, dict) and 'error' in summary_data:
                return jsonify(summary_data), 404
            
            return jsonify(summary_data)
        finally:
            db.close()
    except Exception as e:
        logging.error(f'生成项目 {project_id} 动态汇总时出错: {e}')
        return jsonify({'error': f'生成汇总信息失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/recalculate-price-scores', methods=['POST'])
def recalculate_price_scores(project_id):
    """重新计算价格分"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return jsonify({'error': '项目不存在'}), 404

        # 使用价格分计算器
        calculator = PriceScoreCalculator()
        success = calculator.calculate_project_price_scores(project_id)

        if success:
            return jsonify({
                'message': '价格分重新计算完成',
                'project_id': project_id
            })
        else:
            return jsonify({'error': '价格分计算失败'}), 500

    except Exception as e:
        logging.error(f'重新计算项目 {project_id} 价格分时出错: {e}')
        return jsonify({'error': f'重新计算价格分失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/summary-table', methods=['GET'])
def get_summary_table(project_id):
    """获取项目汇总表格数据"""
    try:
        # 使用ResultDisplay生成汇总数据
        display = ResultDisplay(project_id)
        summary_data = display.generate_multi_level_table()
        
        return jsonify(summary_data)
    except Exception as e:
        logging.error(f"生成汇总表格时出错: {e}")
        return jsonify({'error': f'生成汇总表格失败: {str(e)}'}), 500

@router.route('/analysis-results/bulk-update-scores', methods=['POST'])
def bulk_update_scores():
    """批量更新评分"""
    db = None
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        data = request.get_json()
        score_updates = data.get('score_updates', [])
        
        updated_count = 0
        for update in score_updates:
            result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.id == update['result_id'])
                .first()
            )
            if result:
                # 更新评分
                result.total_score = update['scores'].get(
                    'total_score', result.total_score
                )
                updated_count += 1

        if updated_count > 0:
            db.commit()
            logging.info(f'成功更新了 {updated_count} 条分析结果的评分。')
            return jsonify({
                'message': f'成功更新了 {updated_count} 条分析结果的评分。'
            })
        else:
            logging.warning('批量更新评分请求未找到任何有效的分析结果。')
            return jsonify({'error': '未找到任何有效的分析结果进行更新。'}), 404

    except Exception as e:
        if db:
            try:
                db.rollback()
            except:
                pass
        logging.error(f'批量更新评分时出错: {e}')
        return jsonify({'error': f'批量更新评分失败: {str(e)}'}), 500
