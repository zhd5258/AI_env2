#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
文件上传相关业务逻辑控制器
"""

import os
import shutil
import datetime
import logging
import threading
import traceback  # 添加导入
import re
from pathlib import Path
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
)
from modules.bidder_name_extractor import extract_bidder_name_from_file
from modules.shared_functions import extract_bidder_name_from_file_after_analysis, run_analysis_and_calculate_prices
from modules.pdf_processor import PDFProcessor  # 添加导入

# 跨平台路径处理
def get_platform_safe_path(*path_parts):
    """跨平台安全的路径处理"""
    path = Path(*path_parts)
    return str(path)

# 跨平台文件操作
def safe_makedirs(path):
    """跨平台安全的创建目录"""
    Path(path).mkdir(parents=True, exist_ok=True)

def save_upload_file(upload_file, destination: str, original_filename: str = None) -> str:
    try:
        # 确保目标目录存在
        dest_path = Path(destination)
        safe_makedirs(dest_path.parent)

        # 如果提供了原始文件名，则使用原始文件名但确保安全
        if original_filename:
            # 创建一个更安全的文件名处理方式，尽可能保持原始文件名
            # 1. 移除或替换危险字符，但保留大部分原始字符
            safe_filename = original_filename
            
            # 移除或替换文件系统危险字符
            # Windows 不允许的字符: < > : " | ? * \
            dangerous_chars = r'[<>:"|?*\\]'
            safe_filename = re.sub(dangerous_chars, '_', safe_filename)
            
            # 确保文件名不以空格或点开头或结尾
            safe_filename = safe_filename.strip(' .')
            
            # 如果处理后文件名为空，使用默认名称
            if not safe_filename:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"unnamed_file_{timestamp}.pdf"
            
            # 处理文件名长度，确保不超过系统限制（Windows最大255字符）
            if len(safe_filename) > 250:
                name_stem = Path(safe_filename).stem[:240]  # 留一些空间给后缀
                name_suffix = Path(safe_filename).suffix
                safe_filename = f"{name_stem}{name_suffix}"
            
            # 确保文件名唯一性
            counter = 1
            final_filename = safe_filename
            while (dest_path.parent / final_filename).exists():
                name_stem = Path(safe_filename).stem
                name_suffix = Path(safe_filename).suffix
                final_filename = f"{name_stem}_{counter}{name_suffix}"
                counter += 1
            
            safe_destination = str(dest_path.parent / final_filename)
        else:
            # 如果没有提供原始文件名，使用目标路径中的文件名并确保安全
            base_filename = dest_path.name
            # 移除或替换文件系统危险字符
            dangerous_chars = r'[<>:"|?*\\]'
            safe_filename = re.sub(dangerous_chars, '_', base_filename)
            
            # 确保文件名不以空格或点开头或结尾
            safe_filename = safe_filename.strip(' .')
            
            # 如果处理后文件名为空，使用默认名称
            if not safe_filename:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"unnamed_file_{timestamp}.pdf"
            
            # 处理文件名长度
            if len(safe_filename) > 250:
                name_stem = Path(safe_filename).stem[:240]
                name_suffix = Path(safe_filename).suffix
                safe_filename = f"{name_stem}{name_suffix}"
            
            # 确保文件名唯一性
            counter = 1
            final_filename = safe_filename
            while (dest_path.parent / final_filename).exists():
                name_stem = Path(safe_filename).stem
                name_suffix = Path(safe_filename).suffix
                final_filename = f"{name_stem}_{counter}{name_suffix}"
                counter += 1
            
            safe_destination = str(dest_path.parent / final_filename)

        with open(safe_destination, 'wb') as buffer:
            shutil.copyfileobj(upload_file.stream, buffer)
    finally:
        upload_file.close()
    return safe_destination

# 创建上传目录
UPLOADS_DIR = get_platform_safe_path('uploads')
safe_makedirs(UPLOADS_DIR)

def init_upload_logic(tender_file, bid_files):
    """初始化上传业务逻辑"""
    db = None
    try:
        # 获取数据库会话
        db = SessionLocal()
        
        # 保存原始文件名
        tender_original_filename = tender_file.filename
        
        project_code = f'PRJ-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
        project = TenderProject(
            project_code=project_code,
            name=f'Project {project_code}',
            description=f'Tender: {tender_original_filename}',
            status='pending',
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 保存项目ID以便在会话关闭后使用
        project_id = project.id

        # 按照原始文件名保存招标文件（确保路径安全）
        tender_file_path = save_upload_file(
            tender_file,
            get_platform_safe_path(
                UPLOADS_DIR, tender_original_filename
            ),
            tender_original_filename
        )
        project.tender_file_path = tender_file_path
        db.commit()

        bidders_payload = []
        bid_files_info = []

        for bid_file in bid_files:
            # 保存原始文件名
            bid_original_filename = bid_file.filename
            
            # 按照原始文件名保存投标文件（确保路径安全）
            bid_file_path = save_upload_file(
                bid_file,
                get_platform_safe_path(
                    UPLOADS_DIR, bid_original_filename
                ),
                bid_original_filename
            )

            # 立即使用MinerU处理PDF文件生成MD文件
            try:
                pdf_processor = PDFProcessor(bid_file_path)
                md_file_path = pdf_processor.process_pdf_to_md()
                logging.info(f"成功使用MinerU处理PDF文件，生成MD文件: {md_file_path}")
            except Exception as e:
                logging.error(f"使用MinerU处理PDF文件时出错: {e}")
                md_file_path = None

            # 从MD文件中提取投标人名称
            extracted_bidder_name = '未知投标方'
            if md_file_path and os.path.exists(md_file_path):
                try:
                    extracted_bidder_name = extract_bidder_name_from_file(md_file_path)
                    if not extracted_bidder_name or extracted_bidder_name == '未提取':
                        # 如果提取失败，使用文件名作为备用方案
                        extracted_bidder_name = (
                            f'{Path(bid_original_filename).stem}'
                            if bid_original_filename
                            else '未知投标方'
                        )
                except Exception as e:
                    logging.warning(f'从MD文件中提取投标人名称时出错: {e}')
                    # 如果提取失败，使用文件名作为备用方案
                    extracted_bidder_name = (
                        f'{Path(bid_original_filename).stem}'
                        if bid_original_filename
                        else '未知投标方'
                    )
            else:
                # 如果没有MD文件，则尝试直接从PDF文件提取
                try:
                    extracted_bidder_name = extract_bidder_name_from_file(bid_file_path)
                    if not extracted_bidder_name or extracted_bidder_name == '未提取':
                        # 如果提取失败，使用文件名作为备用方案
                        extracted_bidder_name = (
                            f'{Path(bid_original_filename).stem}'
                            if bid_original_filename
                            else '未知投标方'
                        )
                except Exception as e:
                    logging.warning(f'从文件中提取投标人名称时出错: {e}')
                    # 如果提取失败，使用文件名作为备用方案
                    extracted_bidder_name = (
                        f'{Path(bid_original_filename).stem}'
                        if bid_original_filename
                        else '未知投标方'
                    )

            # 确保投标人名称不为空且不是默认值
            if not extracted_bidder_name or extracted_bidder_name in ['未知投标方', '未提取']:
                # 使用文件名作为备用方案
                extracted_bidder_name = f'{Path(bid_original_filename).stem}' if bid_original_filename else '未知投标方'

            bid_document = BidDocument(
                project_id=project_id,
                bidder_name=extracted_bidder_name,  # 使用提取的投标人名称
                file_path=bid_file_path,
                file_size=bid_file.content_length,
                processing_status='pending',
                progress_total_rules=0,
                progress_completed_rules=0,
                progress_current_rule='等待分析',
            )
            db.add(bid_document)
            db.commit()
            db.refresh(bid_document)
            
            # 保存投标文档ID以便在会话关闭后使用
            bid_document_id = bid_document.id

            bidders_payload.append(
                {
                    'id': bid_document_id,
                    'suggested_name': extracted_bidder_name,  # 使用提取的投标人名称
                    'file_name': bid_original_filename,  # 使用原始文件名
                    'file_size': bid_file.content_length,
                }
            )
            
            # 收集投标文件信息用于后续分析
            bid_files_info.append({
                'id': bid_document_id,
                'tender_file_path': tender_file_path,
                'bid_file_path': bid_file_path,
                'bidder_name': extracted_bidder_name,  # 使用提取的投标人名称
            })
            
        db.close()

        # 启动后台分析任务（修改为并行处理）
        def start_analysis_in_background():
            try:
                # 为每个投标文件启动独立的分析任务
                analysis_threads = []
                for bid_info in bid_files_info:
                    def analyze_single_bid(bid_info_local):
                        try:
                            # 为每个投标文件创建单独的分析任务
                            from modules.shared_functions import analyze_single_bid_document
                            analyze_single_bid_document(project_id, bid_info_local['id'])
                        except Exception as e:
                            logging.error(f'分析投标文件 {bid_info_local["id"]} 时出错: {e}')
                    
                    # 创建并启动分析线程
                    analysis_thread = threading.Thread(target=analyze_single_bid, args=(bid_info,))
                    analysis_thread.daemon = True
                    analysis_thread.start()
                    analysis_threads.append(analysis_thread)
                
                # 等待所有分析任务完成
                for thread in analysis_threads:
                    thread.join()
                
                # 所有分析完成后，统一计算价格分
                db_session = SessionLocal()
                try:
                    logging.info(f'开始为项目 {project_id} 计算价格分。')
                    from modules.price_score_calculator import PriceScoreCalculator
                    calculator = PriceScoreCalculator(db_session)
                    price_scores_result = calculator.calculate_project_price_scores(project_id)

                    if price_scores_result:
                        # 重新获取分析结果以计算更新了多少个投标人
                        analysis_results = (
                            db_session.query(AnalysisResult)
                            .filter(AnalysisResult.project_id == project_id)
                            .all()
                        )
                        logging.info(
                            '项目 %s 价格分计算完成，更新了 %s 个投标方。',
                            project_id,
                            len(analysis_results),
                        )
                    else:
                        logging.warning('项目 %s 未能计算出任何价格分。', project_id)

                    project = db_session.query(TenderProject).filter(TenderProject.id == project_id).first()
                    if project is not None:
                        has_errors = (
                            db_session.query(BidDocument)
                            .filter(
                                BidDocument.project_id == project_id,
                                BidDocument.processing_status == 'error',
                            )
                            .count()
                            > 0
                        )

                        project.status = 'completed_with_errors' if has_errors else 'completed'
                        db_session.commit()
                        logging.info('项目 %s 的状态已更新为 %s。', project_id, project.status)

                except Exception as e:
                    logging.error(f'为项目 {project_id} 计算价格分时出错: {e}')
                    logging.error(traceback.format_exc())
                finally:
                    db_session.close()
                    
            except Exception as e:
                logging.error(f'后台分析任务启动失败: {e}')

        # 在后台线程中启动分析
        analysis_thread = threading.Thread(target=start_analysis_in_background)
        analysis_thread.daemon = True
        analysis_thread.start()

        return {
            'project_id': project_id,
            'tender_file': tender_original_filename,  # 返回原始文件名
            'bidders': bidders_payload,
            'message': '文件上传成功，分析任务已自动启动'
        }
    except RequestEntityTooLarge:
        if db:
            db.close()
        logging.error('文件上传大小超出限制')
        raise RequestEntityTooLarge('文件大小超出限制，请上传小于500MB的文件')
    except Exception as e:
        if db:
            db.close()
        logging.error(f'初始化上传业务逻辑失败: {e}')
        raise e

def list_project_bidders_logic(project_id):
    """列出项目投标方业务逻辑"""
    db = None
    try:
        # 获取数据库会话
        db = SessionLocal()
        
        docs = db.query(BidDocument).filter(BidDocument.project_id == project_id).all()

        # 在返回之前，尝试从分析后的文件中提取投标人名称（如果还没有提取到）
        updated_bidders = []
        for doc in docs:
            # 检查是否需要从分析后的文件中提取投标人名称
            if doc.bidder_name.startswith('待确认') or doc.bidder_name == '未知投标方':
                # 从文件中提取投标人名称
                try:
                    from modules.bidder_name_extractor import extract_bidder_name_from_file
                    extracted_name = extract_bidder_name_from_file(doc.file_path)
                    if extracted_name and extracted_name != '未提取':
                        doc.bidder_name = extracted_name
                        db.commit()
                except Exception as e:
                    logging.warning(f'从文件中提取投标人名称时出错: {e}')

            updated_bidders.append(
                {
                    'id': doc.id,
                    'bidder_name': doc.bidder_name,
                    'status': doc.processing_status,
                    'file_path': doc.file_path,
                    'file_size': doc.file_size,
                    'original_filename': os.path.basename(doc.file_path)
                    if doc.file_path
                    else None,
                }
            )
            
        db.close()

        return updated_bidders
    except Exception as e:
        if db:
            db.close()
        logging.error(f'获取投标方列表业务逻辑失败: {e}')
        raise e
