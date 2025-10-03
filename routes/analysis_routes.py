#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 分析相关路由
# 处理投标分析、评分计算等功能
#

from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
import logging
import json
from pathlib import Path

from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.shared_functions import run_analysis_and_calculate_prices
from modules.summary_generator import generate_summary_data

# 辅助函数：从文件路径提取文件名
def get_filename_from_path(file_path: str) -> str:
    """从文件路径中提取文件名"""
    if not file_path:
        return ''
    return Path(file_path).name

from modules.price_score_calculator import PriceScoreCalculator
from modules.scoring_extractor import IntelligentScoringExtractor

# 创建蓝图
router = Blueprint('analysis', __name__, url_prefix='/api')

# 数据库依赖
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

@router.route('/projects/<int:project_id>/confirm-names-and-start-analysis', methods=['POST'])
def confirm_names_and_start_analysis(project_id):
    """确认投标人名称并开始分析"""
    db = None
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
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
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
    if not project:
        return jsonify({'error': '项目不存在'}), 404

    # 统计分析进度
    total_docs = (
        db.query(BidDocument).filter(BidDocument.project_id == project_id).count()
    )

    completed_docs = (
        db.query(AnalysisResult)
        .join(BidDocument, AnalysisResult.bid_document_id == BidDocument.id)
        .filter(BidDocument.project_id == project_id)
        .filter(AnalysisResult.total_score.isnot(None))
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

        document_statuses.append(
            {
                'id': doc.id,
                'filename': get_filename_from_path(doc.file_path or ''),
                'bidder_name': doc.bidder_name,
                'processing_status': doc.processing_status,
                'has_analysis_result': analysis_result is not None,
                'total_score': analysis_result.total_score if analysis_result else None,
            }
        )

    return jsonify({
        'project_id': project_id,
        'processing_status': project.status,
        'total_documents': total_docs,
        'completed_documents': completed_docs,
        'progress_percentage': (completed_docs / total_docs * 100)
        if total_docs > 0
        else 0,
        'document_statuses': document_statuses,
    })

@router.route('/projects/<int:project_id>/results', methods=['GET'])
def get_analysis_results(project_id):
    """获取项目分析结果"""
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
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
        # 解析详细评分
        detailed_scores = []
        try:
            if result.detailed_scores:
                # 确保从数据库字段中获取字符串值
                detailed_scores_data = result.detailed_scores
                if isinstance(detailed_scores_data, str):
                    scores_data = json.loads(detailed_scores_data)
                    if isinstance(scores_data, list):
                        detailed_scores = scores_data
        except (json.JSONDecodeError, TypeError):
            pass

        formatted_results.append(
            {
                'id': result.id,
                'bidder_name': result.bidder_name,
                'total_score': result.total_score,
                'extracted_price': result.extracted_price,
                'detailed_scores': detailed_scores,
                'bid_document_id': result.bid_document_id,
                'created_at': result.created_at.isoformat()
                if result.created_at
                else None,
                'updated_at': result.updated_at.isoformat()
                if result.updated_at
                else None,
            }
        )

    # 按总分降序排列
    formatted_results.sort(key=lambda x: x['total_score'] or 0, reverse=True)

    return jsonify({'results': formatted_results})

@router.route('/projects/<int:project_id>/scoring-rules', methods=['GET'])
def get_scoring_rules(project_id):
    """获取项目评分规则"""
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
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

@router.route('/projects/<int:project_id>/dynamic-summary', methods=['GET'])
def get_dynamic_summary(project_id):
    """获取项目动态汇总信息"""
    try:
        # 获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        
        summary_data = generate_summary_data(project_id, db)
        return jsonify(summary_data)
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
