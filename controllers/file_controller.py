#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-06 08:35:24
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-08 08:48:06
# 文件相对于项目的路径   : \AI_ENV2\controllers\file_controller.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
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
    AnalysisResult,  # 添加AnalysisResult导入
)
from modules.bidder_name_extractor import extract_bidder_name_from_file
from modules.shared_functions import extract_bidder_name_from_file_after_analysis
from modules.pdf_processor import PDFProcessor  # 添加导入
from modules.runtime_config import load_config


# 跨平台路径处理
def get_platform_safe_path(*path_parts):
    """跨平台安全的路径处理"""
    path = Path(*path_parts)
    return str(path)


# 跨平台文件操作
def safe_makedirs(path):
    """跨平台安全的创建目录"""
    Path(path).mkdir(parents=True, exist_ok=True)


def save_upload_file(upload_file, destination: str, original_filename: str = '') -> str:
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
                timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                safe_filename = f'unnamed_file_{timestamp}.pdf'

            # 处理文件名长度，确保不超过系统限制（Windows最大255字符）
            if len(safe_filename) > 250:
                name_stem = Path(safe_filename).stem[:240]  # 留一些空间给后缀
                name_suffix = Path(safe_filename).suffix
                safe_filename = f'{name_stem}{name_suffix}'

            # 确保文件名唯一性
            counter = 1
            final_filename = safe_filename
            while (dest_path.parent / final_filename).exists():
                name_stem = Path(safe_filename).stem
                name_suffix = Path(safe_filename).suffix
                final_filename = f'{name_stem}_{counter}{name_suffix}'
                counter += 1

            safe_destination = str(dest_path.parent / final_filename)
        else:
            # 如果没有提供原始文件名，使用默认名称
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_filename = f'file_{timestamp}.pdf'
            safe_destination = str(dest_path.parent / safe_filename)

        with open(safe_destination, 'wb') as buffer:
            shutil.copyfileobj(upload_file.stream, buffer)
    finally:
        if 'upload_file' in locals() and upload_file:
            upload_file.close()
    return safe_destination


def cleanup_upload_directory(project_id: int):
    """
    清理上传文件目录
    在项目完成后（不管成功还是失败）清空上传文件保存目录
    """
    db = None
    try:
        db = SessionLocal()
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()

        if project:
            # 获取上传目录路径
            UPLOADS_DIR = get_platform_safe_path('uploads')

            # 检查目录是否存在
            if os.path.exists(UPLOADS_DIR):
                # 删除目录中的所有文件和子目录
                for filename in os.listdir(UPLOADS_DIR):
                    file_path = os.path.join(UPLOADS_DIR, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                        elif os.path.isdir(file_path):
                            shutil.rmtree(file_path)
                    except Exception as e:
                        logging.error(f'删除文件 {file_path} 时出错: {e}')

                logging.info(f'项目 {project_id} 完成，已清空上传目录: {UPLOADS_DIR}')
            else:
                logging.info(f'上传目录不存在: {UPLOADS_DIR}')
        else:
            logging.warning(f'项目 {project_id} 不存在，无法清理上传目录')

    except Exception as e:
        logging.error(f'清理上传目录时出错: {e}')
        raise  # 重新抛出异常以便上层捕获
    finally:
        if db:
            db.close()


# 创建上传目录
UPLOADS_DIR = get_platform_safe_path('uploads')
safe_makedirs(UPLOADS_DIR)


def update_processing_phase(bid_document_id: int, phase: str):
    """更新投标文件的处理阶段"""
    db = SessionLocal()
    try:
        bid_document = (
            db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        )
        if bid_document:
            bid_document.processing_phase = phase
            db.commit()
            logging.info(f'更新投标文件 {bid_document_id} 的处理阶段为: {phase}')
    except Exception as e:
        logging.error(f'更新处理阶段时出错: {e}')
    finally:
        db.close()


def update_project_status(project_id: int, status: str):
    """更新项目状态"""
    db = SessionLocal()
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if project:
            project.status = status
            # 如果项目状态是完成或错误，则记录结束时间
            if status in ['completed', 'completed_with_errors', 'error']:
                project.analysis_end_time = datetime.datetime.now()
                cleanup_upload_directory(project_id)
            db.commit()
            logging.info(f'更新项目 {project_id} 的状态为: {status}')
    except Exception as e:
        logging.error(f'更新项目状态时出错: {e}')
    finally:
        db.close()


def init_upload_logic(tender_file, bid_files):
    """初始化上传业务逻辑"""
    db = None
    try:
        # 在上传文件前检查文件大小限制
        runtime_config = load_config()
        single_file_max_size = runtime_config.get(
            'single_file_max_size', 100 * 1024 * 1024
        )  # 默认100MB

        # 检查招标文件大小
        if tender_file and tender_file.filename != '':
            if tender_file.content_length > single_file_max_size:
                max_mb = single_file_max_size // (1024 * 1024)
                raise RequestEntityTooLarge(
                    f'招标文件大小超出限制，请上传小于{max_mb}MB的文件'
                )

        # 检查投标文件大小
        for bid_file in bid_files:
            if bid_file and bid_file.filename != '':
                if bid_file.content_length > single_file_max_size:
                    max_mb = single_file_max_size // (1024 * 1024)
                    raise RequestEntityTooLarge(
                        f'投标文件大小超出限制，请上传小于{max_mb}MB的文件'
                    )

        # 在上传文件前自动清空上传文件夹
        from modules.system_maintenance import cleanup_before_upload

        cleanup_before_upload()

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
            analysis_start_time=datetime.datetime.now(),  # 记录分析开始时间
        )
        db.add(project)
        db.commit()
        db.refresh(project)

        # 保存项目ID以便在会话关闭后使用
        project_id = int(project.id)

        # 按照原始文件名保存招标文件（确保路径安全）
        tender_file_path = save_upload_file(
            tender_file,
            get_platform_safe_path(UPLOADS_DIR, tender_original_filename),
            tender_original_filename,
        )

        # 更新项目中的招标文件路径
        project.tender_file_path = tender_file_path
        db.commit()

        # 保存投标文件
        bidders_payload = []
        bid_files_info = []
        for bid_file in bid_files:
            original_filename = bid_file.filename

            # 按照原始文件名保存投标文件（确保路径安全）
            bid_file_path = save_upload_file(
                bid_file,
                get_platform_safe_path(UPLOADS_DIR, original_filename),
                original_filename,
            )

            # 从文件名提取投标人名称（去除扩展名）
            bidder_name = os.path.splitext(original_filename)[0]

            # 创建投标文件记录
            bid_document = BidDocument(
                project_id=project_id,
                original_filename=original_filename,
                file_path=bid_file_path,
                bidder_name=bidder_name,  # 设置默认投标人名称为文件名
                processing_phase='uploaded',
                processing_status='pending',  # 设置初始处理状态为pending
            )
            db.add(bid_document)
            db.commit()
            db.refresh(bid_document)

            bidders_payload.append(
                {
                    'id': int(bid_document.id),
                    'original_filename': original_filename,
                    'file_path': bid_file_path,
                }
            )

            # 准备分析任务信息
            bid_files_info.append(
                {
                    'bid_document_id': int(bid_document.id),
                    'tender_file_path': tender_file_path,
                    'bid_file_path': bid_file_path,
                    'bidder_name': bid_document.bidder_name
                    if bid_document.bidder_name
                    else '',
                }
            )

        if db:
            db.close()
        db = None

        # 在后台线程中启动分析
        def start_analysis_in_background():
            try:
                # 更新项目状态为分析中
                update_project_status(project_id, 'analyzing')

                # 执行完整的分析任务 - 使用AnalysisManager统一处理
                from modules.analysis_manager import AnalysisManager
                from models.database import SessionLocal

                # 创建分析管理器实例并执行完整的分析流程
                db_local = SessionLocal()
                analysis_manager = AnalysisManager(db_session=db_local)
                # 在新线程中运行分析任务，避免阻塞主线程
                import threading

                analysis_thread = threading.Thread(
                    target=analysis_manager.run_analysis_and_calculate_prices,
                    args=(project_id, bid_files_info),
                )
                analysis_thread.start()
                db_local.close()

                # 移除手动更新项目状态的代码，让价格计算工作流自己更新项目状态
                # update_project_status(project_id, 'completed')
            except Exception as e:
                logging.error(f'后台分析任务执行失败: {e}')
                traceback.print_exc()
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
            'message': '文件上传成功，分析任务已自动启动',
        }
    except RequestEntityTooLarge:
        if 'db' in locals() and db:
            db.close()
        logging.error('文件上传大小超出限制')
        # 从运行时配置获取文件大小限制
        runtime_config = load_config()
        single_file_max_size = runtime_config.get(
            'single_file_max_size', 100 * 1024 * 1024
        )
        max_mb = single_file_max_size // (1024 * 1024)
        raise RequestEntityTooLarge(f'文件大小超出限制，请上传小于{max_mb}MB的文件')
    except Exception as e:
        if 'db' in locals() and db:
            db.close()
        logging.error(f'初始化上传业务逻辑失败: {e}')
        raise e


def list_project_bidders_logic(project_id):
    """列出项目投标方业务逻辑"""
    db = None
    try:
        # 获取数据库会话
        db = SessionLocal()

        # 查询项目下的所有投标文件
        bid_documents = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )

        # 构造返回数据
        bidders = []
        for doc in bid_documents:
            bidders.append(
                {
                    'id': int(doc.id),
                    'original_filename': doc.original_filename
                    if doc.original_filename
                    else '',
                    'bidder_name': doc.bidder_name if doc.bidder_name else '',
                    'processing_status': doc.processing_status
                    if doc.processing_status
                    else '',
                    'error_message': doc.error_message if doc.error_message else '',
                }
            )

        return bidders
    except Exception as e:
        logging.error(f'获取项目 {project_id} 投标方列表失败: {e}')
        raise e
    finally:
        if db:
            db.close()
