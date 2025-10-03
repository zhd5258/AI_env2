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
from pathlib import Path
from werkzeug.utils import secure_filename
from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
)
from modules.bidder_name_extractor import extract_bidder_name_from_file
from modules.shared_functions import extract_bidder_name_from_file_after_analysis, run_analysis_and_calculate_prices

# 跨平台路径处理
def get_platform_safe_path(*path_parts):
    """跨平台安全的路径处理"""
    path = Path(*path_parts)
    return str(path)

# 跨平台文件操作
def safe_makedirs(path):
    """跨平台安全的创建目录"""
    Path(path).mkdir(parents=True, exist_ok=True)

def save_upload_file(upload_file, destination: str) -> str:
    try:
        # 确保目标目录存在
        dest_path = Path(destination)
        safe_makedirs(dest_path.parent)

        with open(destination, 'wb') as buffer:
            shutil.copyfileobj(upload_file.stream, buffer)
    finally:
        upload_file.close()
    return destination

# 创建上传目录
UPLOADS_DIR = get_platform_safe_path('uploads')
safe_makedirs(UPLOADS_DIR)

def init_upload_logic(tender_file, bid_files):
    """初始化上传业务逻辑"""
    db = None
    try:
        # 获取数据库会话
        db = SessionLocal()
        
        tender_filename = secure_filename(tender_file.filename)
        project_code = f'PRJ-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
        project = TenderProject(
            project_code=project_code,
            name=f'Project {project_code}',
            description=f'Tender: {tender_filename}',
            status='pending',
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        
        # 保存项目ID以便在会话关闭后使用
        project_id = project.id

        tender_file_path = save_upload_file(
            tender_file,
            get_platform_safe_path(
                UPLOADS_DIR, f'{project_id}_tender_{tender_filename}'
            ),
        )
        project.tender_file_path = tender_file_path
        db.commit()

        bidders_payload = []
        bid_files_info = []

        for bid_file in bid_files:
            bid_filename = secure_filename(bid_file.filename)
            bid_file_path = save_upload_file(
                bid_file,
                get_platform_safe_path(
                    UPLOADS_DIR, f'{project_id}_bid_{bid_filename}'
                ),
            )

            # 使用文件名作为占位符名称
            suggested_name = (
                f'待确认_{Path(bid_filename).stem}'
                if bid_filename
                else '待确认投标方'
            )

            bid_document = BidDocument(
                project_id=project_id,
                bidder_name=suggested_name,
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
                    'suggested_name': suggested_name,
                    'file_name': bid_filename,
                    'file_size': bid_file.content_length,
                }
            )
            
            # 收集投标文件信息用于后续分析
            bid_files_info.append({
                'id': bid_document_id,
                'tender_file_path': tender_file_path,
                'bid_file_path': bid_file_path,
                'bidder_name': suggested_name,
            })
            
        db.close()

        # 启动后台分析任务
        def start_analysis_in_background():
            try:
                run_analysis_and_calculate_prices(project_id, bid_files_info)
            except Exception as e:
                logging.error(f'后台分析任务启动失败: {e}')

        # 在后台线程中启动分析
        analysis_thread = threading.Thread(target=start_analysis_in_background)
        analysis_thread.daemon = True
        analysis_thread.start()

        return {
            'project_id': project_id,
            'tender_file': tender_filename,
            'bidders': bidders_payload,
            'message': '文件上传成功，分析任务已自动启动'
        }
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

        # 在返回之前，尝试从分析后的文件中提取投标人名称
        updated_bidders = []
        for doc in docs:
            # 检查是否需要从分析后的文件中提取投标人名称
            if doc.bidder_name.startswith('待确认_') or doc.bidder_name == '待确认投标方':
                # 从文件中提取投标人名称
                extracted_name = extract_bidder_name_from_file_after_analysis(doc.file_path)
                if extracted_name:
                    doc.bidder_name = extracted_name
                    db.commit()

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
