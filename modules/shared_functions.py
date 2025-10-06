#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-03 12:28:33
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-03 12:34:01
#文件相对于项目的路径   : \AI_env2\modules\shared_functions.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
共享函数模块，用于避免循环导入问题
"""

import logging
import json
import asyncio
import time
import threading
import traceback  # 确保导入
from typing import List, Dict, Any
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sqlalchemy.orm import Session

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.price_score_calculator import PriceScoreCalculator
from modules.correct_scoring_extractor import CorrectScoringExtractor
from modules.bidder_name_extractor import extract_bidder_name_from_file_after_analysis

# 创建一个进程池
executor = ProcessPoolExecutor(max_workers=4)


def extract_bidder_name_from_file_after_analysis(file_path: str) -> str:
    """
    从分析后的文件中提取投标人名称

    Args:
        file_path: 文件路径

    Returns:
        str: 提取的投标人名称
    """
    # 实际调用投标人名称提取模块
    try:
        from modules.bidder_name_extractor import extract_bidder_name_from_file
        extracted_name = extract_bidder_name_from_file(file_path)
        return extracted_name if extracted_name else '待确认投标方'
    except Exception as e:
        logging.error(f'从文件中提取投标人名称时出错: {e}')
        return '待确认投标方'


def analysis_task(project_id: int, bid_document_id: int):
    """
    This function runs in a separate process.
    It creates its own database session.
    """
    db = SessionLocal()
    bid_document = None
    try:
        logging.info(
            'Starting analysis for bid_id: %s in project_id: %s',
            bid_document_id,
            project_id,
        )

        bid_document = (
            db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        )
        if not bid_document:
            logging.error('投标文件不存在: %s', bid_document_id)
            return

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            logging.error('项目不存在: %s', project_id)
            return

        tender_file_path = project.tender_file_path
        if not tender_file_path or not Path(tender_file_path).exists():
            logging.error('招标文件不存在: %s', tender_file_path)
            bid_document.processing_status = 'error'
            bid_document.error_message = '招标文件不存在'
            bid_document.progress_current_rule = '分析失败'
            db.commit()
            return

        bid_document.processing_status = 'processing'
        bid_document.progress_completed_rules = 0
        bid_document.progress_total_rules = 0
        bid_document.progress_current_rule = '初始化分析...'
        db.commit()

        # 优化：在分析前预加载PDF文本（这将从缓存中快速读取）
        try:
            from modules.pdf_processor import PDFProcessor

            logging.info(f'为分析任务预加载PDF文本: {bid_document.file_path}')
            pdf_processor = PDFProcessor(bid_document.file_path)
            # 调用extract_text_per_page会优先从缓存加载，速度很快
            extracted_pages = pdf_processor.extract_text_per_page(use_cache=True)
            if not extracted_pages or not any(extracted_pages):
                raise ValueError('未能从缓存或文件中加载有效的PDF文本内容。')
            logging.info(f'成功预加载 {len(extracted_pages)} 页文本')
        except Exception as e:
            logging.error(f'在分析前加载PDF文本失败: {e}')
            bid_document.processing_status = 'error'
            bid_document.error_message = f'加载PDF文本失败: {e}'
            bid_document.progress_current_rule = '分析失败'
            db.commit()
            return

        analyzer = IntelligentBidAnalyzer(
            tender_file_path,
            bid_document.file_path,
            db_session=db,
            bid_document_id=bid_document.id,
            project_id=project_id,
            extracted_text=extracted_pages,  # 传入已提取的文本
        )

        result_data = None
        analysis_error = None

        def run_analysis():
            nonlocal result_data, analysis_error
            try:
                result_data = analyzer.analyze()
            except Exception as e:
                analysis_error = e

        analysis_thread = threading.Thread(target=run_analysis)
        analysis_thread.daemon = True

        try:
            logging.info('开始分析投标文件 %s', bid_document_id)
            start_time = time.time()
            analysis_thread.start()
            analysis_thread.join(timeout=1800)
            end_time = time.time()
            analysis_duration = end_time - start_time

            if analysis_thread.is_alive():
                logging.error('分析超时 for bid_id %s', bid_document.id)
                bid_document.processing_status = 'error'
                bid_document.error_message = '分析超时，请重试'
                bid_document.progress_current_rule = '分析超时'
                db.commit()
                return
            elif analysis_error:
                logging.error(
                    '分析过程中发生异常 for bid_id %s: %s',
                    bid_document.id,
                    str(analysis_error),
                )
                bid_document.processing_status = 'error'
                bid_document.error_message = f'分析异常: {str(analysis_error)}'
                bid_document.progress_current_rule = '分析异常'
                db.commit()
                return
            else:
                logging.info('分析完成，耗时 %.2f 秒', analysis_duration)

        except Exception as e:
            logging.error(
                '分析过程中发生异常 for bid_id %s: %s', bid_document_id, str(e)
            )
            bid_document.processing_status = 'error'
            bid_document.error_message = f'分析异常: {str(e)}'
            bid_document.progress_current_rule = '分析异常'
            db.commit()
            return

        if result_data is None:
            logging.error('分析结果为空 for bid_id %s', bid_document_id)
            bid_document.processing_status = 'error'
            bid_document.error_message = '分析结果为空'
            bid_document.progress_current_rule = '分析失败'
            db.commit()
            return

        if not isinstance(result_data, dict):
            logging.error('分析结果格式错误 for bid_id %s', bid_document_id)
            bid_document.processing_status = 'error'
            bid_document.error_message = '分析结果格式错误'
            bid_document.progress_current_rule = '分析失败'
            db.commit()
            return

        assert isinstance(result_data, dict)

        if 'error' in result_data:
            logging.error(
                'Analysis failed for bid_id %s: %s',
                bid_document_id,
                result_data['error'],
            )
            bid_document.processing_status = 'error'
            bid_document.error_message = result_data['error']
            bid_document.progress_current_rule = '分析出错'
            db.commit()
            return

        total_score = result_data.get('total_score', 0)
        price_score = result_data.get('price_score', 0)
        detailed_scores = result_data.get('detailed_scores', {})
        extracted_price = result_data.get('extracted_price')

        if price_score == 0 and detailed_scores:
            price_score = _extract_price_score_from_detailed_scores(detailed_scores)

        # 确保同一项目下同一投标文件（或同一投标人）不会产生重复结果
        try:
            db.query(AnalysisResult).filter(
                AnalysisResult.project_id == project_id,
                AnalysisResult.bid_document_id == bid_document_id,
            ).delete()
        except Exception:
            pass

        analysis_result = AnalysisResult(
            project_id=project_id,
            bid_document_id=bid_document_id,
            bidder_name=bid_document.bidder_name,
            total_score=total_score,
            price_score=price_score,
            extracted_price=extracted_price,
            detailed_scores=json.dumps(detailed_scores, ensure_ascii=False),
            analysis_summary=result_data.get('analysis_summary', 'Analysis complete.'),
            ai_model=result_data.get('ai_model', 'Unknown'),
            scoring_method=result_data.get('scoring_method', 'AI'),
            is_modified=False,
            modification_count=0,
        )

        db.add(analysis_result)
        bid_document.processing_status = 'completed'
        db.commit()
        logging.info('Successfully completed analysis for bid_id: %s', bid_document_id)
    except Exception as e:
        logging.error(
            'A critical error occurred in analysis_task for bid_id %s:',
            bid_document_id,
        )
        logging.error(traceback.format_exc())
        if db and bid_document:
            bid_document.processing_status = 'error'
            bid_document.error_message = f'Critical error: {str(e)}'
            db.commit()
    finally:
        if db:
            db.close()


def _extract_price_score_from_detailed_scores(detailed_scores):
    try:
        if isinstance(detailed_scores, str):
            try:
                detailed_scores = json.loads(detailed_scores)
            except json.JSONDecodeError:
                return 0.0

        if not isinstance(detailed_scores, list):
            return 0.0

        def find_price_score(scores):
            for score in scores:
                criteria_name = score.get('criteria_name', '').lower()
                is_price_criteria = any(
                    keyword in criteria_name
                    for keyword in ['价格', 'price', '报价', '投标报价']
                ) or score.get('is_price_criteria', False)

                if is_price_criteria and 'score' in score:
                    return float(score['score'])

                if 'children' in score and score['children']:
                    child_price_score = find_price_score(score['children'])
                    if child_price_score is not None and child_price_score > 0:
                        return child_price_score

            return None

        price_score = find_price_score(detailed_scores)
        return float(price_score) if price_score is not None else 0.0

    except Exception as e:
        logging.error(f'从详细评分中提取价格分时出错: {e}')
        return 0.0


def analyze_single_bid_document(project_id: int, bid_document_id: int):
    """
    分析单个投标文件
    这个函数用于并行处理，每个投标文件独立分析
    """
    logging.info(f'开始分析投标文件 project_id: {project_id}, bid_document_id: {bid_document_id}')
    
    # 为每个分析任务创建独立的数据库会话
    db = SessionLocal()
    try:
        # 调用现有的分析任务函数
        analysis_task(project_id, bid_document_id)
        logging.info(f'完成分析投标文件 project_id: {project_id}, bid_document_id: {bid_document_id}')
    except Exception as e:
        logging.error(f'分析投标文件时出错 project_id: {project_id}, bid_document_id: {bid_document_id}: {e}')
    finally:
        db.close()


def run_analysis_and_calculate_prices(project_id: int, bid_files_info: list):
    logging.info(f'开始为项目 {project_id} 执行后台分析和价格计算任务。')

    # 首先提取评分规则并保存到数据库
    db = SessionLocal()
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if (
            project is not None
            and project.tender_file_path
            and Path(str(project.tender_file_path)).exists()
        ):
            # 检查是否已有评分规则
            existing_rules = (
                db.query(ScoringRule)
                .filter(ScoringRule.project_id == project_id)
                .count()
            )
            if existing_rules == 0:
                logging.info(f'项目 {project_id} 没有评分规则，开始提取...')
                # 使用统一的评分规则提取方法
                # extractor = IntelligentScoringExtractor()
                # 使用 CorrectScoringExtractor 直接从PDF中提取评分规则
                extractor = CorrectScoringExtractor(project.tender_file_path)
                # scoring_rules = extractor.extract(project.tender_file_path)
                scoring_rules = extractor.extract_scoring_rules()

                if scoring_rules:
                    # Manually save rules to the database
                    db.query(ScoringRule).filter(
                        ScoringRule.project_id == project_id
                    ).delete()

                    def save_rule_recursive(rule_data, project_id, parent_name=None):
                        """递归保存评分规则（父项填 Parent_Item_Name，子项填 Child_Item_Name）"""
                        is_price = bool(rule_data.get('is_price_criteria', False))
                        children = rule_data.get('children') or []

                        if children or is_price:
                            # 保存父项（或价格父项）
                            db_rule = ScoringRule(
                                project_id=project_id,
                                Parent_Item_Name=rule_data.get('criteria_name'),
                                Parent_max_score=rule_data.get('max_score'),
                                description=rule_data.get('description', ''),
                                is_price_criteria=is_price,
                            )
                            if is_price:
                                db_rule.price_formula = rule_data.get('price_formula')
                            db_rule.Child_Item_Name = None
                            db_rule.Child_max_score = None

                            db.add(db_rule)
                            db.flush()

                            # 递归保存子项，传递父项名称
                            for child_rule in children:
                                save_rule_recursive(
                                    child_rule,
                                    project_id,
                                    parent_name=rule_data.get('criteria_name'),
                                )
                        else:
                            # 保存子项（叶子）
                            db_rule = ScoringRule(
                                project_id=project_id,
                                Parent_Item_Name=parent_name,
                                Parent_max_score=None,
                                Child_Item_Name=rule_data.get('criteria_name'),
                                Child_max_score=rule_data.get('max_score'),
                                description=rule_data.get('description', ''),
                                is_price_criteria=False,
                            )
                            db.add(db_rule)
                            db.flush()

                    for rule_data in scoring_rules:
                        save_rule_recursive(rule_data, project_id)

                    db.commit()
                    logging.info(
                        '成功提取并保存 %s 条评分规则到数据库', len(scoring_rules)
                    )
                else:
                    logging.error('提取评分规则失败')
            else:
                logging.info(f'项目 {project_id} 已存在评分规则，跳过提取步骤')
    except Exception as e:
        logging.error(f'处理项目 {project_id} 的评分规则时出错: {e}')
    finally:
        db.close()

    # 注意：并行处理逻辑已移至控制器中实现，这里不再需要执行并行分析任务
    logging.info(f'项目 {project_id} 的评分规则提取完成，等待控制器中的并行处理任务完成...')
