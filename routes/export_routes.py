#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 导出功能路由
# 处理Excel和Word格式的数据导出
#

from flask import Blueprint, jsonify, send_file
from sqlalchemy.orm import Session
import pandas as pd
from io import BytesIO
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
import os

# Word导出相关
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH

from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)

# 创建蓝图
router = Blueprint('export', __name__, url_prefix='/api')

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.route('/projects/<int:project_id>/export-excel', methods=['GET'])
def export_project_results_excel(project_id):
    """导出项目结果到Excel文件"""
    try:
        # 使用上下文管理器获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        try:
            # 验证项目存在
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 获取分析结果
            results = (
                db.query(AnalysisResult)
                .join(BidDocument, AnalysisResult.bid_document_id == BidDocument.id)
                .filter(BidDocument.project_id == project_id)
                .all()
            )

            if not results:
                return jsonify({'error': '该项目没有分析结果可导出'}), 404

            # 获取评分规则
            scoring_rules = (
                db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
            )

            # 创建Excel文件
            output = BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # 工作表1: 总分排名
                summary_data = []
                detailed_scores_columns = set()

                for result in results:
                    row_data = {
                        '投标人': result.bidder_name,
                        '总分': result.total_score,
                        '投标价格': result.extracted_price,
                        '创建时间': result.created_at.strftime('%Y-%m-%d %H:%M:%S')
                        if result.created_at
                        else '',
                    }

                    # 解析详细评分
                    try:
                        if result.detailed_scores:
                            detailed_scores = json.loads(result.detailed_scores)
                            if isinstance(detailed_scores, list):
                                for score_item in detailed_scores:
                                    if isinstance(score_item, dict):
                                        for score_name, score_value in score_item.items():
                                            row_data[score_name] = score_value
                                            detailed_scores_columns.add(score_name)
                    except (json.JSONDecodeError, TypeError):
                        pass

                    summary_data.append(row_data)

                # 按总分降序排列
                summary_data.sort(key=lambda x: x['总分'] or 0, reverse=True)

                # 创建DataFrame
                summary_df = pd.DataFrame(summary_data)

                # 调整列顺序
                base_columns = ['投标人', '总分', '投标价格']
                score_columns = sorted(list(detailed_scores_columns))
                time_columns = ['创建时间']

                column_order = base_columns + score_columns + time_columns
                summary_df = summary_df.reindex(columns=column_order, fill_value='')

                # 写入Excel
                summary_df.to_excel(writer, sheet_name='投标结果汇总', index=False)

                # 工作表2: 评分规则
                if scoring_rules:
                    rules_data = []
                    for rule in scoring_rules:
                        rules_data.append(
                            {
                                '父级评分项': rule.Parent_Item_Name,
                                '子级评分项': rule.Child_Item_Name,
                                '父级最高分': rule.Parent_max_score,
                                '子级最高分': rule.Child_max_score,
                                '评分说明': rule.description,
                            }
                        )

                    rules_df = pd.DataFrame(rules_data)
                    rules_df.to_excel(writer, sheet_name='评分规则', index=False)

                # 工作表3: 项目信息
                project_info = {
                    '项目名称': [project.name],
                    '招标文件': [project.tender_file_path],
                    '创建时间': [
                        project.created_at.strftime('%Y-%m-%d %H:%M:%S')
                        if project.created_at
                        else ''
                    ],
                    '处理状态': [project.status],
                    '投标文件数量': [len(results)],
                    '导出时间': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                }

                project_df = pd.DataFrame(project_info)
                project_df.to_excel(writer, sheet_name='项目信息', index=False)

            output.seek(0)

            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'投标分析结果_{project.name}_{timestamp}.xlsx'
            
            # 保存到临时文件
            temp_file_path = os.path.join('temp', filename)
            os.makedirs('temp', exist_ok=True)
            with open(temp_file_path, 'wb') as f:
                f.write(output.getvalue())

            logging.info(f'项目 {project_id} Excel导出完成: {filename}')

            return send_file(temp_file_path, as_attachment=True, download_name=filename)
        finally:
            try:
                next(db_gen)  # 触发finally块
            except StopIteration:
                pass

    except Exception as e:
        logging.error(f'导出Excel时出错: {e}')
        return jsonify({'error': f'导出Excel失败: {str(e)}'}), 500

@router.route('/projects/<int:project_id>/export-word', methods=['GET'])
def export_project_results_word(project_id):
    """导出项目结果到Word文件"""
    try:
        # 使用上下文管理器获取数据库会话
        db_gen = get_db()
        db = next(db_gen)
        try:
            # 验证项目存在
            project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
            if not project:
                return jsonify({'error': '项目不存在'}), 404

            # 获取分析结果
            results = (
                db.query(AnalysisResult)
                .join(BidDocument, AnalysisResult.bid_document_id == BidDocument.id)
                .filter(BidDocument.project_id == project_id)
                .all()
            )

            if not results:
                return jsonify({'error': '该项目没有分析结果可导出'}), 404

            # 获取评分规则
            scoring_rules = (
                db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
            )

            # 创建Word文档
            doc = Document()

            # 文档标题
            title = doc.add_heading(f'投标分析报告 - {project.name}', 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            # 项目基本信息
            doc.add_heading('1. 项目基本信息', level=1)

            project_table = doc.add_table(rows=5, cols=2)
            project_table.style = 'Table Grid'

            project_info = [
                ('项目名称', project.name),
                (
                    '招标文件',
                    project.tender_file_path.split('/')[-1]
                    if project.tender_file_path
                    else '',
                ),
                ('投标文件数量', str(len(results))),
                (
                    '创建时间',
                    project.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    if project.created_at
                    else '',
                ),
                ('导出时间', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
            ]

            for i, (key, value) in enumerate(project_info):
                project_table.cell(i, 0).text = key
                project_table.cell(i, 1).text = value

            # 详细分析结果
            doc.add_heading('2. 详细分析结果', level=1)

            # 按总分排序
            sorted_results = sorted(results, key=lambda x: x.total_score or 0, reverse=True)

            for i, result in enumerate(sorted_results, 1):
                doc.add_heading(f'2.{i} {result.bidder_name}', level=2)

                # 基本信息表格
                info_table = doc.add_table(rows=3, cols=2)
                info_table.style = 'Table Grid'
                info_table.cell(0, 0).text = '总分'
                info_table.cell(0, 1).text = str(result.total_score or 0)
                info_table.cell(1, 0).text = '投标价格'
                info_table.cell(1, 1).text = str(result.extracted_price or 0)
                info_table.cell(2, 0).text = '分析时间'
                info_table.cell(2, 1).text = (
                    result.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')
                    if result.analyzed_at
                    else ''
                )

                # 详细评分
                if result.detailed_scores:
                    try:
                        detailed_scores = json.loads(result.detailed_scores)
                        if isinstance(detailed_scores, list) and detailed_scores:
                            doc.add_paragraph('详细评分:', style='Heading 3')

                            scores_table = doc.add_table(
                                rows=len(detailed_scores) + 1, cols=2
                            )
                            scores_table.style = 'Table Grid'
                            scores_table.cell(0, 0).text = '评分项'
                            scores_table.cell(0, 1).text = '得分'

                            for j, score_item in enumerate(detailed_scores):
                                if isinstance(score_item, dict):
                                    for score_name, score_value in score_item.items():
                                        scores_table.cell(j + 1, 0).text = score_name
                                        scores_table.cell(j + 1, 1).text = str(score_value)
                    except (json.JSONDecodeError, TypeError):
                        pass

                doc.add_paragraph()  # 添加空行

            # 评分规则
            if scoring_rules:
                doc.add_heading('3. 评分规则', level=1)

                rules_table = doc.add_table(rows=len(scoring_rules) + 1, cols=5)
                rules_table.style = 'Table Grid'
                rules_table.cell(0, 0).text = '父级评分项'
                rules_table.cell(0, 1).text = '子级评分项'
                rules_table.cell(0, 2).text = '父级最高分'
                rules_table.cell(0, 3).text = '子级最高分'
                rules_table.cell(0, 4).text = '评分说明'

                for i, rule in enumerate(scoring_rules):
                    rules_table.cell(i + 1, 0).text = rule.Parent_Item_Name or ''
                    rules_table.cell(i + 1, 1).text = rule.Child_Item_Name or ''
                    rules_table.cell(i + 1, 2).text = str(rule.Parent_max_score or '')
                    rules_table.cell(i + 1, 3).text = str(rule.Child_max_score or '')
                    rules_table.cell(i + 1, 4).text = rule.description or ''

            # 保存到临时文件
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'投标分析报告_{project.name}_{timestamp}.docx'
            temp_file_path = os.path.join('temp', filename)
            os.makedirs('temp', exist_ok=True)
            doc.save(temp_file_path)

            logging.info(f'项目 {project_id} Word导出完成: {filename}')

            return send_file(temp_file_path, as_attachment=True, download_name=filename)
        finally:
            try:
                next(db_gen)  # 触发finally块
            except StopIteration:
                pass

    except Exception as e:
        logging.error(f'导出Word时出错: {e}')
        return jsonify({'error': f'导出Word失败: {str(e)}'}), 500
