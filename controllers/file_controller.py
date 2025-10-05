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


def update_processing_phase(bid_document_id: int, phase: str):
    """更新投标文件的处理阶段"""
    db = SessionLocal()
    try:
        bid_document = db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        if bid_document:
            bid_document.processing_phase = phase
            db.commit()
            logging.info(f"更新投标文件 {bid_document_id} 的处理阶段为: {phase}")
    except Exception as e:
        logging.error(f"更新处理阶段时出错: {e}")
    finally:
        db.close()


def update_project_status(project_id: int, status: str):
    """更新项目状态"""
    db = SessionLocal()
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if project:
            project.status = status
            db.commit()
            logging.info(f"更新项目 {project_id} 的状态为: {status}")
    except Exception as e:
        logging.error(f"更新项目状态时出错: {e}")
    finally:
        db.close()

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

            # 从PDF文件中提取投标人名称（在并行处理中会再次提取，这里仅作为初步信息）
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
                logging.warning(f'从PDF文件中提取投标人名称时出错: {e}')
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
                # 使用生产者-消费者模式实现并行处理
                # 一边处理PDF转换为MD，一边对已转换完成的MD文件进行AI分析
                
                import queue
                import threading
                import time
                
                # 创建队列用于存储已完成PDF处理的文件
                processed_queue = queue.Queue()
                processing_complete = threading.Event()
                
                # PDF处理线程函数
                def process_pdfs():
                    try:
                        logging.info(f"PDF处理线程启动，共需处理 {len(bid_files_info)} 个文件")
                        # 按顺序处理每个PDF文件
                        for i, bid_info in enumerate(bid_files_info):
                            bid_document_id = bid_info['id']
                            bid_file_path = bid_info['bid_file_path']
                            
                            logging.info(f"[{i+1}/{len(bid_files_info)}] 开始处理PDF文件: {bid_file_path}")
                            
                            # 更新处理阶段为PDF转换阶段
                            update_processing_phase(bid_info['id'], 'PDF转换中')
                            
                            # 处理PDF文件生成MD文件
                            try:
                                pdf_processor = PDFProcessor(bid_file_path)
                                
                                # 检查temp/md目录中是否已存在对应的txt（招标文件）或md文档（投标文件）
                                existing_file_path = pdf_processor._check_output_exists()
                                if existing_file_path:
                                    md_file_path = existing_file_path
                                    logging.info(f"[{i+1}/{len(bid_files_info)}] 文件已存在，跳过PDF转换: {md_file_path}")
                                else:
                                    md_file_path = pdf_processor.process_pdf_to_md()
                                    logging.info(f"[{i+1}/{len(bid_files_info)}] 成功处理PDF文件，生成MD文件: {md_file_path}")
                                
                                # 将处理完成的文件信息放入队列
                                processed_queue.put({
                                    'bid_info': bid_info,
                                    'md_file_path': md_file_path,
                                    'status': 'success'
                                })
                                logging.info(f"[{i+1}/{len(bid_files_info)}] 已将处理完成的文件放入队列: {bid_file_path}")
                            except Exception as e:
                                logging.error(f"[{i+1}/{len(bid_files_info)}] 处理PDF文件时出错: {e}")
                                # 将错误信息放入队列
                                processed_queue.put({
                                    'bid_info': bid_info,
                                    'error': str(e),
                                    'status': 'error'
                                })
                        
                        # 标记PDF处理完成
                        processing_complete.set()
                        logging.info(f"所有PDF文件处理完成，共处理 {len(bid_files_info)} 个文件")
                    except Exception as e:
                        logging.error(f"PDF处理线程出错: {e}")
                        processing_complete.set()
                
                # AI分析线程函数
                def analyze_mds():
                    try:
                        completed_analyses = 0
                        total_files = len(bid_files_info)
                        
                        logging.info(f"AI分析线程启动，共需分析 {total_files} 个文件")
                        
                        while not (processing_complete.is_set() and processed_queue.empty()):
                            try:
                                # 从队列中获取已完成处理的文件
                                try:
                                    # 使用阻塞方式获取队列数据，超时1秒
                                    processed_item = processed_queue.get(timeout=1.0)
                                    
                                    if processed_item['status'] == 'success':
                                        # 更新处理阶段为AI分析阶段
                                        update_processing_phase(processed_item['bid_info']['id'], 'AI分析中')
                                        
                                        # 启动AI分析
                                        bid_info = processed_item['bid_info']
                                        logging.info(f"[{completed_analyses+1}/{total_files}] 开始AI分析投标文件: {bid_info['id']}")
                                        
                                        try:
                                            from modules.shared_functions import analyze_single_bid_document
                                            analyze_single_bid_document(project_id, bid_info['id'])
                                            logging.info(f"[{completed_analyses+1}/{total_files}] 完成AI分析投标文件: {bid_info['id']}")
                                        except Exception as e:
                                            logging.error(f"[{completed_analyses+1}/{total_files}] 分析投标文件 {bid_info['id']} 时出错: {e}")
                                    elif processed_item['status'] == 'error':
                                        logging.error(f"PDF处理出错: {processed_item.get('error', '未知错误')}")
                                    
                                    completed_analyses += 1
                                    logging.info(f"AI分析进度: {completed_analyses}/{total_files}")
                                    
                                    # 标记任务完成
                                    processed_queue.task_done()
                                except queue.Empty:
                                    # 队列为空，继续等待
                                    logging.debug("队列为空，继续等待...")
                                    continue
                            except Exception as e:
                                logging.error(f"AI分析线程处理时出错: {e}")
                                time.sleep(0.1)
                        
                        logging.info(f"所有AI分析任务完成，共分析 {completed_analyses} 个文件")
                    except Exception as e:
                        logging.error(f"AI分析线程出错: {e}")
                
                # 创建并启动PDF处理线程和AI分析线程
                logging.info("创建PDF处理线程和AI分析线程")
                pdf_thread = threading.Thread(target=process_pdfs, name="PDFProcessor")
                ai_thread = threading.Thread(target=analyze_mds, name="AIAnalyzer")
                
                pdf_thread.daemon = True
                ai_thread.daemon = True
                
                # 先启动AI分析线程，使其处于等待状态
                logging.info("启动AI分析线程")
                ai_thread.start()
                # 稍后启动PDF处理线程
                logging.info("启动PDF处理线程")
                pdf_thread.start()
                
                # 等待所有线程完成
                pdf_thread.join()
                ai_thread.join()
                
                # 所有分析完成后，统一计算价格分
                try:
                    logging.info(f'开始为项目 {project_id} 计算价格分。')
                    db_session = SessionLocal()
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
                    # 更新项目状态为错误
                    update_project_status(project_id, 'error')
                finally:
                    if 'db_session' in locals():
                        db_session.close()
                    
            except Exception as e:
                logging.error(f'后台分析任务启动失败: {e}')
                # 更新项目状态为错误
                update_project_status(project_id, 'error')

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
