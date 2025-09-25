# pyright: reportGeneralTypeIssues=false
# mypy: ignore-errors
import uvicorn
import os
import shutil
import datetime
from datetime import timezone
import json
import re
import asyncio
import logging
import sys
import traceback
from typing import List, Optional, Dict, Any
from concurrent.futures import ProcessPoolExecutor
import concurrent.futures
from pathlib import Path

from fastapi import (
    FastAPI,
    Request,
    UploadFile,
    File,
    Depends,
    BackgroundTasks,
)
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from modules.database import (
    SessionLocal,
    engine,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer
from modules.price_score_calculator import PriceScoreCalculator
from modules.summary_generator import generate_summary_data
from modules.runtime_config import (
    load_config,
    save_config,
    load_config_for_project,
    save_config_for_project,
)
from modules.pdf_processor import PDFProcessor

# 导出功能需要的模块
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
import io
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH


# 评分规则提取器
from modules.scoring_extractor import IntelligentScoringExtractor


# 跨平台路径处理
def get_platform_safe_path(*path_parts):
    """跨平台安全的路径处理"""
    path = Path(*path_parts)
    return str(path)


# 跨平台文件操作
def safe_makedirs(path):
    """跨平台安全的创建目录"""
    Path(path).mkdir(parents=True, exist_ok=True)


# 1. Setup Logging
# 设置控制台输出编码为UTF-8
if sys.platform == 'win32':
    import codecs

    # 修复日志缓冲区分离问题
    try:
        if (
            hasattr(sys.stdout, 'detach')
            and callable(getattr(sys.stdout, 'detach', None))
            and not sys.stdout.closed
        ):
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())  # type: ignore[attr-defined]
        if (
            hasattr(sys.stderr, 'detach')
            and callable(getattr(sys.stderr, 'detach', None))
            and not sys.stderr.closed
        ):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())  # type: ignore[attr-defined]
    except (ValueError, AttributeError):
        # 当stdout/stderr已经被分离时，使用默认的编码
        pass
else:
    # Linux/Unix系统下的编码处理
    import locale

    try:
        locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            pass

# 配置日志，添加错误处理以防止缓冲区分离问题
try:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler('analysis.log', encoding='utf-8'),
            logging.StreamHandler(),
        ],
        force=True,
    )
except (ValueError, AttributeError):
    # 当stdout被重定向或分离时使用基本配置
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('analysis.log', encoding='utf-8'),
            ],
            force=True,
        )
    except Exception:
        # 最后的备用方案
        pass

# 创建 FastAPI 应用
app = FastAPI()

# 配置CORS以支持前端轮询
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ========== 工具函数：解析价格字符串为数值 ==========
def _extract_numeric_price(price_str: Any) -> Optional[float]:
    """将各种价格字符串解析为数字，支持逗号、小数点以及单位“万/亿”。

    参数:
        price_str: 任意可转字符串的价格表示，例如 "1,234,567.89 元"、"123.45万"、"2.3亿"。

    返回:
        float 或 None
    """
    try:
        s = str(price_str).strip()
        if not s:
            return None

        # 归一化：去掉空格与常见货币字符
        s = s.replace(',', '')
        s = re.sub(r'[人民币元圆¥￥\s]', '', s)

        multiplier = 1.0
        if '亿' in s:
            multiplier = 100000000.0
            s = s.replace('亿', '')
        elif '万' in s:
            multiplier = 10000.0
            s = s.replace('万', '')

        # 提取数字（允许一个小数点）
        m = re.search(r'(\d+(?:\.\d+)?)', s)
        if not m:
            return None
        value = float(m.group(1)) * multiplier

        # 合理性约束：排除极小值（如保证金/页码之类）
        if value < 1000:
            return None
        return value
    except Exception:
        return None


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_project_analysis(project_id: int):
    """
    初始化项目分析，处理招标文件并提取评分规则
    """
    db = SessionLocal()
    try:
        logging.info(f'开始初始化项目分析，项目ID: {project_id}')

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            logging.error(f'项目不存在: {project_id}')
            return False

        tender_file_path = project.tender_file_path
        if not tender_file_path or not Path(tender_file_path).exists():
            logging.error(f'招标文件不存在: {tender_file_path}')
            return False

        logging.info(f'项目 {project_id} 没有评分规则，开始从招标文件提取...')

        # 从招标文件中提取评分规则
        from modules.scoring_extractor import IntelligentScoringExtractor

        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(tender_file_path)

        if scoring_rules:
            # 删除该项目已有的评分规则
            db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()

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
            logging.info('成功提取并保存 %s 条评分规则到数据库', len(scoring_rules))

            # 记录提取到的评分规则详细信息
            for rule_data in scoring_rules:
                logging.info(
                    f'评分规则: criteria_name={rule_data.get("criteria_name")}, max_score={rule_data.get("max_score")}, is_price_criteria={rule_data.get("is_price_criteria")}'
                )

            return True
        else:
            logging.error(
                '提取评分规则失败：未从招标文件解析出评分规则（严格禁止使用默认规则）。'
            )
            return False

    except Exception as e:
        logging.error(f'初始化项目分析时出错: {e}', exc_info=True)
        db.rollback()
        return False
    finally:
        db.close()


# 创建一个进程池
executor = ProcessPoolExecutor(max_workers=os.cpu_count())

# 创建上传目录
UPLOADS_DIR = get_platform_safe_path('uploads')
safe_makedirs(UPLOADS_DIR)

# 配置静态文件和模板
app.mount(
    '/static', StaticFiles(directory=get_platform_safe_path('static')), name='static'
)
templates = Jinja2Templates(directory=get_platform_safe_path('templates'))

# 创建数据库表
TenderProject.metadata.create_all(bind=engine)
BidDocument.metadata.create_all(bind=engine)
AnalysisResult.metadata.create_all(bind=engine)


class UpdateBidderNameRequest(BaseModel):
    """请求体：更新投标方名称

    所有字段中文注释，限制：新名称长度>=2，且应包含“公司/有限/股份/集团”等关键词
    """

    new_name: str


class UpdateRuntimeConfigRequest(BaseModel):
    """请求体：更新运行参数（中文注释）"""

    pdf_page_max_workers: Optional[int] = None
    pdf_page_timeout_sec: Optional[int] = None
    pdf_overall_min_timeout_sec: Optional[int] = None
    ai_analysis_page_limit: Optional[int] = None


# 运行参数（内存缓存）
RUNTIME_CONFIG = load_config()


@app.get('/api/runtime-config')
async def get_runtime_config():
    """获取当前运行参数配置（全局默认）。"""
    return JSONResponse(content=RUNTIME_CONFIG)


@app.post('/api/runtime-config')
async def update_runtime_config(payload: UpdateRuntimeConfigRequest):
    """更新全局运行参数默认配置（数值校验+落盘+内存刷新）。"""
    global RUNTIME_CONFIG
    cfg = dict(RUNTIME_CONFIG)
    if payload.pdf_page_max_workers is not None:
        v = max(1, min(32, int(payload.pdf_page_max_workers)))
        cfg['pdf_page_max_workers'] = v
    if payload.pdf_page_timeout_sec is not None:
        v = max(5, min(300, int(payload.pdf_page_timeout_sec)))
        cfg['pdf_page_timeout_sec'] = v
    if payload.pdf_overall_min_timeout_sec is not None:
        v = max(30, min(3600, int(payload.pdf_overall_min_timeout_sec)))
        cfg['pdf_overall_min_timeout_sec'] = v
    if payload.ai_analysis_page_limit is not None:
        v = max(1, min(100, int(payload.ai_analysis_page_limit)))
        cfg['ai_analysis_page_limit'] = v
    save_config(cfg)
    RUNTIME_CONFIG = load_config()
    return JSONResponse(content=RUNTIME_CONFIG)


@app.get('/api/projects/{project_id}/runtime-config')
async def get_project_runtime_config(project_id: int):
    """获取项目级运行参数配置（不存在则返回并创建默认）。"""
    try:
        cfg = load_config_for_project(project_id)
        return JSONResponse(content=cfg)
    except Exception as e:
        logging.error('获取项目运行参数失败: %s', e)
        return JSONResponse(status_code=500, content={'error': '读取项目配置失败'})


@app.post('/api/projects/{project_id}/runtime-config')
async def update_project_runtime_config(
    project_id: int, payload: UpdateRuntimeConfigRequest
):
    """更新项目级运行参数配置。"""
    try:
        cfg = load_config_for_project(project_id)
        if payload.pdf_page_max_workers is not None:
            v = max(1, min(32, int(payload.pdf_page_max_workers)))
            cfg['pdf_page_max_workers'] = v
        if payload.pdf_page_timeout_sec is not None:
            v = max(5, min(300, int(payload.pdf_page_timeout_sec)))
            cfg['pdf_page_timeout_sec'] = v
        if payload.pdf_overall_min_timeout_sec is not None:
            v = max(30, min(3600, int(payload.pdf_overall_min_timeout_sec)))
            cfg['pdf_overall_min_timeout_sec'] = v
        if payload.ai_analysis_page_limit is not None:
            v = max(1, min(100, int(payload.ai_analysis_page_limit)))
            cfg['ai_analysis_page_limit'] = v
        save_config_for_project(project_id, cfg)
        return JSONResponse(content=cfg)
    except Exception as e:
        logging.error('更新项目运行参数失败: %s', e)
        return JSONResponse(status_code=500, content={'error': '保存项目配置失败'})


class OCRConfigRequest(BaseModel):
    """OCR配置请求模型"""

    use_gpu: Optional[bool] = None
    use_paddle: Optional[bool] = None


@app.get('/api/ocr-config')
async def get_ocr_config():
    """获取当前OCR配置"""
    return JSONResponse(
        content={
            'use_gpu': os.getenv('USE_GPU', 'false').lower() == 'true',
            'use_paddle': True,  # 默认使用PaddleOCR
            'available_engines': ['paddle', 'onnx'],
            'current_engine': 'paddle',
        }
    )


@app.post('/api/ocr-config')
async def update_ocr_config(payload: OCRConfigRequest):
    """更新OCR配置"""
    try:
        if payload.use_gpu is not None:
            os.environ['USE_GPU'] = str(payload.use_gpu).lower()
            logging.info('OCR GPU设置已更新: %s', payload.use_gpu)

        # 同步Paddle OCR引擎开关到环境变量，供PDF处理器选择OCR引擎
        if payload.use_paddle is not None:
            os.environ['USE_PADDLE'] = str(payload.use_paddle).lower()
            logging.info('OCR 引擎设置为Paddle: %s', payload.use_paddle)

        return JSONResponse(
            content={
                'message': 'OCR配置已更新',
                'use_gpu': os.getenv('USE_GPU', 'false').lower() == 'true',
                'use_paddle': os.getenv('USE_PADDLE', 'true').lower() == 'true',
            }
        )
    except Exception as e:
        logging.error('更新OCR配置失败: %s', e)
        return JSONResponse(status_code=500, content={'error': f'更新OCR配置失败: {e}'})


@app.patch('/api/bids/{bid_id}/name')
async def update_bidder_name(
    bid_id: int, payload: UpdateBidderNameRequest, db: Session = Depends(get_db)
):
    """修改指定投标文件的投标方名称。

    - 校验名称有效性（基本关键词、长度、去空格）
    - 更新`bid_document.bidder_name`以及对应`analysis_result.bidder_name`
    - 返回更新后的记录信息
    """
    try:
        new_name = (payload.new_name or '').strip()
        if len(new_name) < 2:
            return JSONResponse(status_code=400, content={'error': '名称过短'})

        company_keywords = ['公司', '有限', '股份', '集团', '厂', '院', '所', '中心']
        if not any(k in new_name for k in company_keywords):
            return JSONResponse(
                status_code=400, content={'error': '名称缺少公司关键词'}
            )

        bid = db.query(BidDocument).filter(BidDocument.id == bid_id).first()
        if not bid:
            return JSONResponse(status_code=404, content={'error': '投标文件未找到'})

        old_name = bid.bidder_name
        bid.bidder_name = new_name  # type: ignore[assignment]
        db.commit()

        ar = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.bid_document_id == bid.id)
            .first()
        )
        if ar:
            ar.bidder_name = new_name  # type: ignore[assignment]
            db.commit()

        logging.info(
            f'已将投标方名称由 "{old_name}" 更新为 "{new_name}" (bid_id={bid_id})'
        )
        # 返回更新后的列表项，供前端即时刷新
        return JSONResponse(
            content={
                'id': bid.id,
                'old_name': old_name,
                'new_name': new_name,
                'project_id': bid.project_id,
            }
        )
    except Exception as e:
        logging.error(f'修改投标方名称失败: {e}')
        return JSONResponse(
            status_code=500, content={'error': f'服务器内部错误: {str(e)}'}
        )


# 首页
@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse('index.html', {'request': request})
    except Exception as e:
        logging.error('Error rendering template: %s', str(e))
        return HTMLResponse(content=f'Error: {str(e)}', status_code=500)


@app.get('/favicon.ico')
async def favicon():
    """返回站点图标，避免浏览器404请求。"""
    try:
        from fastapi.responses import FileResponse

        icon_path = get_platform_safe_path('templates', 'favicon.ico')
        if not Path(icon_path).exists():
            return JSONResponse(status_code=404, content={'error': 'favicon not found'})
        return FileResponse(icon_path)
    except Exception as e:
        logging.error('返回favicon失败: %s', e)
        return JSONResponse(status_code=500, content={'error': 'favicon error'})


@app.get('/history', response_class=HTMLResponse)
async def history_page(request: Request):
    try:
        return templates.TemplateResponse('history.html', {'request': request})
    except Exception as e:
        logging.error('Error rendering template: %s', str(e))
        return HTMLResponse(content=f'Error: {str(e)}', status_code=500)


def save_upload_file(upload_file: UploadFile, destination: str) -> str:
    try:
        # 将文件保存到临时目录
        temp_dir = get_platform_safe_path('temp_uploads')
        safe_makedirs(temp_dir)
        temp_destination = get_platform_safe_path(temp_dir, destination)

        # 确保目标目录存在
        dest_path = Path(temp_destination)
        safe_makedirs(dest_path.parent)

        with open(temp_destination, 'wb') as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()
    return temp_destination


# 添加一个新的函数用于在后台提取PDF文本
def extract_pdf_text_background(file_path: str, bidder_name: str):
    """
    在后台提取PDF文本的函数，用于多线程处理

    Args:
        file_path: PDF文件路径
        bidder_name: 投标方名称

    Returns:
        tuple: (bidder_name, pages_text, success)
    """
    try:
        logging.info(f'开始后台提取 {bidder_name} 的PDF文本')
        from modules.pdf_processor import PDFProcessor

        # 检查是否启用GPU（从环境变量或配置中读取）
        use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
        processor = PDFProcessor(
            file_path, use_gpu=use_gpu, file_type='bid'
        )  # 投标文件使用ONNX
        # 使用单线程执行器为PDF提取增加超时保护，避免卡死
        local_executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = local_executor.submit(
            processor.process_pdf_per_page
        )  # 自动选择OCR引擎
        try:
            pages_text = future.result(timeout=180)
        except concurrent.futures.TimeoutError:
            logging.error('提取 %s 的PDF文本超时(>180s)', bidder_name)
            future.cancel()
            return (bidder_name, [], False)
        finally:
            local_executor.shutdown(wait=False, cancel_futures=True)
        logging.info(f'完成 {bidder_name} 的PDF文本提取，共 {len(pages_text)} 页')
        return (bidder_name, pages_text, True)
    except Exception as e:
        logging.error(f'提取 {bidder_name} 的PDF文本时出错: {e}')
        return (bidder_name, [], False)


def analysis_task(
    project_id: int, bid_document_id: int, tender_file_path: str, bid_file_path: str
):
    """
    分析任务：分析单个投标文件，支持流式处理
    """
    db = SessionLocal()
    bid_document = None
    try:
        logging.info(f'开始分析任务: 项目ID={project_id}, 投标文件ID={bid_document_id}')

        # 获取投标文件记录
        bid_document = (
            db.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        )
        if not bid_document:
            logging.error(f'未找到投标文件记录: {bid_document_id}')
            return

        # 检查是否已存在对应的分析结果记录，如果不存在则创建
        analysis_result = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.bid_document_id == bid_document_id)
            .first()
        )
        if not analysis_result:
            analysis_result = AnalysisResult(
                project_id=project_id,
                bid_document_id=bid_document_id,
                bidder_name=bid_document.bidder_name or '未知投标方',
            )
            db.add(analysis_result)
            db.commit()
            logging.info(f'为投标文件 {bid_document_id} 创建了新的分析结果记录')

        # 更新处理状态
        bid_document.processing_status = 'processing'
        bid_document.progress_current_rule = '开始处理'
        db.commit()

        # 检查是否启用GPU（从环境变量中读取）
        use_gpu = os.getenv('USE_GPU', 'false').lower() == 'true'
        logging.info(f'OCR GPU设置: {use_gpu}')

        # 使用流式处理方式提取投标文件文本内容
        pdf_processor = PDFProcessor(bid_file_path, use_gpu=use_gpu, file_type='bid')
        # 创建分析器实例，不传递预提取的文本，让分析器在流式处理过程中自行处理
        analyzer = IntelligentBidAnalyzer(
            tender_file_path,
            bid_document.file_path,
            db_session=db,
            bid_document_id=bid_document_id,
            project_id=project_id,
            extracted_text=None,  # 不传递预提取的文本，启用流式处理
        )

        # 执行分析（流式处理会在分析过程中自动进行）
        analysis_result = analyzer.analyze_bidding_document()

        # 更新处理状态
        if analysis_result['status'] == 'success':
            bid_document.processing_status = 'completed'
            bid_document.progress_current_rule = '分析完成'
            # 记录提取到的投标人名称和投标总价
            if 'details' in analysis_result:
                details = analysis_result['details']
                if '投标人名称' in details and details['投标人名称'] != '待分析确认':
                    bid_document.bidder_name = details['投标人名称']
                if '投标总价' in details and details['投标总价'] != '未提取':
                    try:
                        # 尝试保存投标总价到数据库
                        price_str = str(details['投标总价'])
                        # 移除常见的非数字字符并转换为浮点数
                        price_value = _extract_numeric_price(price_str)
                        if price_value is not None:
                            # 价格信息将在AnalysisResult中保存
                            pass
                    except (ValueError, TypeError) as e:
                        logging.warning(
                            f'无法解析投标总价: {details["投标总价"]}, 错误: {e}'
                        )
            logging.info(f'投标文件分析完成: {bid_document.bidder_name}')
        else:
            bid_document.processing_status = 'error'
            bid_document.error_message = analysis_result['message']
            bid_document.progress_current_rule = '分析失败'
            logging.error(f'投标文件分析失败: {analysis_result["message"]}')

        db.commit()

    except Exception as e:
        logging.error(f'分析任务执行过程中发生意外错误: {e}', exc_info=True)
        if bid_document:
            bid_document.processing_status = 'error'
            bid_document.error_message = f'分析过程中发生意外错误: {str(e)}'
            bid_document.progress_current_rule = '分析失败'
            db.commit()
    finally:
        db.close()


def run_analysis_and_calculate_prices(project_id: int, bid_files_info: list):
    logging.info(f'开始为项目 {project_id} 执行后台分析和价格计算任务。')

    # 首先提取评分规则并保存到数据库
    if not initialize_project_analysis(project_id):
        logging.error(f'项目 {project_id} 评分规则初始化失败')

    # 获取项目信息
    db = SessionLocal()
    project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
    if not project:
        logging.error(f'项目 {project_id} 未找到')
        db.close()
        return
    tender_file_path = project.tender_file_path
    db.close()

    # 为每个投标文件创建分析任务
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    futures = []
    for bid_info in bid_files_info:
        try:
            future = loop.run_in_executor(
                executor,
                analysis_task,
                project_id,
                bid_info['id'],
                tender_file_path,
                bid_info['path'],
            )
            futures.append(future)
        except Exception as e:
            logging.error(f'为投标文件 {bid_info["id"]} 创建分析任务时出错: {e}')

    # 等待所有分析任务完成
    if futures:
        try:
            loop.run_until_complete(asyncio.gather(*futures, return_exceptions=True))
            logging.info(f'项目 {project_id} 的所有分析任务已完成。')
        except Exception as e:
            logging.error(f'等待项目 {project_id} 的分析任务完成时出错: {e}')
    else:
        logging.warning(f'项目 {project_id} 没有需要分析的投标文件。')

    loop.close()

    # 计算价格分
    db = SessionLocal()
    try:
        logging.info(f'开始为项目 {project_id} 计算价格分。')
        calculator = PriceScoreCalculator(db_session=db)
        price_scores_result = calculator.calculate_project_price_scores(project_id)

        if price_scores_result:
            # 重新获取分析结果以计算更新了多少个投标人
            analysis_results = (
                db.query(AnalysisResult)
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

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if project is not None:
            has_errors = (
                db.query(BidDocument)
                .filter(
                    BidDocument.project_id == project_id,
                    BidDocument.processing_status == 'error',
                )
                .count()
                > 0
            )

            project.status = 'completed_with_errors' if has_errors else 'completed'
            db.commit()
            logging.info('项目 %s 的状态已更新为 %s。', project_id, project.status)

    except Exception as e:
        logging.error(f'为项目 {project_id} 计算价格分时出错: {e}')
        logging.error(traceback.format_exc())
    finally:
        db.close()


@app.post('/api/projects/{project_id}/confirm-names-and-start-analysis')
async def confirm_names_and_start_analysis(
    project_id: int,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    接收前端确认后的投标方名称，更新数据库，并启动后台分析流程。
    """
    try:
        data = await request.json()
        bidders_updates = data.get('bidders')

        if not bidders_updates:
            return JSONResponse(status_code=400, content={'error': '缺少投标方信息'})

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目未找到'})

        bid_files_info = []
        for bidder_update in bidders_updates:
            bid_id = bidder_update.get('id')
            confirmed_name = bidder_update.get('name')

            doc = db.query(BidDocument).filter(BidDocument.id == bid_id).first()
            if doc and confirmed_name:
                # 更新名称和状态
                doc.bidder_name = confirmed_name
                doc.processing_status = 'pending'
                doc.progress_current_rule = '准备中...'

                # 确保对应的分析结果记录存在
                analysis_result = (
                    db.query(AnalysisResult)
                    .filter(AnalysisResult.bid_document_id == bid_id)
                    .first()
                )
                if not analysis_result:
                    analysis_result = AnalysisResult(
                        project_id=project_id,
                        bid_document_id=bid_id,
                        bidder_name=confirmed_name,
                    )
                    db.add(analysis_result)

                bid_files_info.append(
                    {
                        'id': doc.id,
                        'path': doc.file_path,
                        'bidder_name': doc.bidder_name,
                    }
                )

        project.status = 'processing'
        db.commit()

        logging.info(f'项目 {project_id} 名称已确认，即将开始后台分析...')

        # 启动后台分析任务
        background_tasks.add_task(
            run_analysis_and_calculate_prices,
            project.id,
            bid_files_info,
        )

        return JSONResponse(
            content={'project_id': project.id, 'message': '分析已成功启动'}
        )

    except Exception as e:
        logging.error(f'启动分析时出错: {e}')
        db.rollback()
        return JSONResponse(status_code=500, content={'error': '服务器内部错误'})


@app.get('/api/projects/{project_id}/analysis-status')
async def get_analysis_status(project_id: int, db: Session = Depends(get_db)):
    project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
    if not project:
        return JSONResponse(status_code=404, content={'error': 'Project not found'})

    bid_documents = (
        db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
    )

    status_data = []
    all_completed = True
    has_errors = False
    for doc in bid_documents:
        partial_results = None
        if bool(doc.partial_analysis_results):
            try:
                partial_str = (
                    doc.partial_analysis_results
                    if isinstance(doc.partial_analysis_results, str)
                    else str(doc.partial_analysis_results)
                )
                partial_results = json.loads(partial_str)
            except json.JSONDecodeError as e:
                logging.error('解析部分分析结果失败: %s', e)

        status_data.append(
            {
                'bidder_name': doc.bidder_name,
                'status': doc.processing_status,
                'error_message': doc.error_message,
                'progress_completed': doc.progress_completed_rules or 0,
                'progress_total': doc.progress_total_rules or 0,
                'current_rule': doc.progress_current_rule,
                'detailed_progress_info': doc.detailed_progress_info,
                'partial_analysis_results': partial_results,
                'id': doc.id,
            }
        )
        if doc.processing_status not in ['completed', 'error']:
            all_completed = False
        if doc.processing_status == 'error':
            has_errors = True

    # 状态更新由后台统一流程在价格分计算完成后设置，避免前端过早认为已完成

    return JSONResponse(content={'project_status': project.status, 'bids': status_data})


@app.get('/api/projects/{project_id}/results')
async def get_analysis_results(project_id: int, db: Session = Depends(get_db)):
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.total_score.desc())
        .all()
    )
    if not results:
        return JSONResponse(
            status_code=404, content={'error': 'Results not found for this project'}
        )

    response_data = []
    for res in results:
        price_score = getattr(res, 'price_score', None)
        # 确保价格分正确处理，如果为None则尝试从detailed_scores中提取
        if price_score is None:
            try:
                detailed_scores = (
                    json.loads(res.detailed_scores)
                    if isinstance(res.detailed_scores, str)
                    else res.detailed_scores
                )
                # 如果detailed_scores是字典格式，尝试从中查找价格分
                if isinstance(detailed_scores, dict):
                    for key, value in detailed_scores.items():
                        if '价格' in key or 'price' in key.lower():
                            if isinstance(value, (int, float)):
                                price_score = value
                                break
                            elif isinstance(value, dict) and 'score' in value:
                                price_score = value['score']
                                break
                # 如果detailed_scores是列表格式，尝试从中查找价格分
                elif isinstance(detailed_scores, list):
                    for item in detailed_scores:
                        if isinstance(item, dict) and item.get(
                            'is_price_criteria', False
                        ):
                            price_score = item.get('score', 0)
                            break
            except Exception as e:
                logging.error(f'解析价格分时出错: {e}')

        response_data.append(
            {
                'id': res.id,
                'bidder_name': res.bidder_name,
                'total_score': res.total_score,
                'price_score': price_score,
                'extracted_price': res.extracted_price,
                'detailed_scores': json.loads(res.detailed_scores)
                if isinstance(res.detailed_scores, str)
                else res.detailed_scores,
                'dynamic_scores': json.loads(res.dynamic_scores)
                if isinstance(res.dynamic_scores, str)
                else (res.dynamic_scores or {}),
                'ai_model': res.ai_model,
            }
        )

    return JSONResponse(content=response_data)


@app.get('/api/projects/{project_id}/scoring-rules')
async def get_scoring_rules(project_id: int, db: Session = Depends(get_db)):
    project = db.query(TenderProject).filter(TenderProject.id == project_id).first()

    if not project:
        return JSONResponse(
            status_code=404,
            content={'error': 'Project not found'},
        )

    if project.scoring_rules_summary:
        if isinstance(project.scoring_rules_summary, list):
            return JSONResponse(content=project.scoring_rules_summary)
        else:
            logging.warning(
                f'Project {project_id} 的 scoring_rules_summary 格式不正确，将从 ScoringRule 表中回退。'
            )

    scoring_rules = (
        db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
    )

    if not scoring_rules:
        return JSONResponse(
            status_code=404,
            content={'error': 'Scoring rules not found for this project'},
        )

    response_data = []
    for rule in scoring_rules:
        response_data.append(
            {
                'id': rule.id,
                'category': rule.Parent_Item_Name,  # 修复字段名
                'criteria_name': rule.Child_Item_Name
                if rule.Child_Item_Name
                else rule.Parent_Item_Name,
                'max_score': rule.Child_max_score
                if rule.Child_max_score
                else rule.Parent_max_score,
                'weight': 1.0,
                'description': rule.description,
                'is_veto': rule.is_veto,
            }
        )

    return JSONResponse(content=response_data)


@app.get('/api/projects')
async def get_all_projects(db: Session = Depends(get_db)):
    projects = db.query(TenderProject).all()

    # 使用单次查询获取所有相关的投标文件和分析结果信息
    project_ids = [project.id for project in projects]

    # 批量查询投标文件数量
    bid_counts = {}
    if project_ids:
        bid_count_results = (
            db.query(BidDocument.project_id, func.count(BidDocument.id))
            .filter(BidDocument.project_id.in_(project_ids))
            .group_by(BidDocument.project_id)
            .all()
        )
        bid_counts = {project_id: count for project_id, count in bid_count_results}

    # 批量查询分析结果数量
    result_counts = {}
    if project_ids:
        result_count_results = (
            db.query(AnalysisResult.project_id, func.count(AnalysisResult.id))
            .filter(AnalysisResult.project_id.in_(project_ids))
            .group_by(AnalysisResult.project_id)
            .all()
        )
        result_counts = {
            project_id: count for project_id, count in result_count_results
        }

    response_data = []
    for project in projects:
        response_data.append(
            {
                'id': project.id,
                'project_code': project.project_code,
                'name': project.name,
                'description': project.description,
                'created_at': project.created_at.isoformat()
                if project.created_at
                else None,
                'status': project.status,
                'bid_count': bid_counts.get(project.id, 0),
                'result_count': result_counts.get(project.id, 0),
            }
        )

    return JSONResponse(content=response_data)


@app.get('/api/projects/{project_id}/bid-documents/{bid_document_id}/failed-pages')
async def get_failed_pages_info(
    project_id: int, bid_document_id: int, db: Session = Depends(get_db)
):
    bid_document = (
        db.query(BidDocument)
        .filter(BidDocument.id == bid_document_id, BidDocument.project_id == project_id)
        .first()
    )

    if not bid_document:
        return JSONResponse(
            status_code=404, content={'error': 'Bid document not found'}
        )

    if not bid_document.failed_pages_info:
        return JSONResponse(
            status_code=404,
            content={
                'error': 'No failed pages information available for this document'
            },
        )

    try:
        failed_pages_data = json.loads(bid_document.failed_pages_info)
        return JSONResponse(content=failed_pages_data)
    except json.JSONDecodeError:
        return JSONResponse(
            status_code=500,
            content={'error': 'Failed to parse failed pages information'},
        )


@app.get('/api/projects/{project_id}/dynamic-summary')
async def get_dynamic_summary(project_id: int, db: Session = Depends(get_db)):
    try:
        summary_data = generate_summary_data(project_id, db)
        if isinstance(summary_data, dict) and 'error' in summary_data:
            return JSONResponse(status_code=404, content=summary_data)
        return JSONResponse(content=summary_data)
    except Exception as e:
        logging.error(f'生成动态汇总表时出错: {e}')
        logging.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={'error': f'服务器内部错误: {str(e)}'},
        )


@app.post('/api/projects/{project_id}/recalculate-price-scores')
async def recalculate_price_scores(project_id: int, db: Session = Depends(get_db)):
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        bid_documents = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )
        if not bid_documents:
            return JSONResponse(
                status_code=404, content={'error': '项目中没有投标文件'}
            )

        incomplete_bids = [
            doc
            for doc in bid_documents
            if doc.processing_status not in ['completed', 'error']
        ]
        if incomplete_bids:
            return JSONResponse(
                status_code=400,
                content={
                    'error': f'还有 {len(incomplete_bids)} 个投标文件未完成分析，请等待分析完成后再重新计算价格分'
                },
            )

        calculator = PriceScoreCalculator(db_session=db)
        price_scores = calculator.calculate_project_price_scores(project_id)

        if not price_scores:
            return JSONResponse(
                status_code=400,
                content={
                    'error': '无法计算价格分，请检查投标文件中是否包含有效的价格信息'
                },
            )

        return JSONResponse(
            content={
                'message': '价格分重新计算完成',
                'price_scores': price_scores,
                'updated_count': len(price_scores),
            }
        )

    except Exception as e:
        logging.error(f'重新计算项目 {project_id} 价格分时出错: {e}')
        return JSONResponse(
            status_code=500,
            content={'error': f'重新计算价格分时出错: {str(e)}'},
        )


class ScoreUpdateItem(BaseModel):
    id: int
    total_score: float


# 添加临时文件清理的请求模型
class CleanupRequest(BaseModel):
    delete_uploads: Optional[bool] = True
    delete_cache: Optional[bool] = True
    delete_temp_word: Optional[bool] = True


# ========== 新增：分步上传与名称确认 API ==========


class InitUploadResponse(BaseModel):
    """初始化上传响应体（中文注释）"""

    project_id: int
    tender_file: str
    bidders: List[Dict[str, Any]]


class StartAnalysisRequest(BaseModel):
    """开始分析请求体：前端确认后的投标方名称列表（中文注释）"""

    bidders: List[Dict[str, Any]]  # 每项包含 id 和 confirmed_name


@app.post('/api/projects/{project_id}/cleanup')
async def cleanup_temp_files(
    project_id: int, payload: CleanupRequest, db: Session = Depends(get_db)
):
    """清理项目相关的临时文件"""
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        deleted_paths = []

        # 删除上传的临时文件
        if payload.delete_uploads:
            temp_uploads_dir = get_platform_safe_path('temp_uploads')
            if Path(temp_uploads_dir).exists():
                # 删除与该项目相关的文件
                for file_path in Path(temp_uploads_dir).glob('*'):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                            deleted_paths.append(str(file_path))
                        except Exception as e:
                            logging.warning(f'删除文件失败 {file_path}: {e}')

        # 删除生成的中间文件
        if payload.delete_cache:
            temp_cache_dir = get_platform_safe_path('temp_pdf_cache')
            if Path(temp_cache_dir).exists():
                for file_path in Path(temp_cache_dir).glob('*'):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                            deleted_paths.append(str(file_path))
                        except Exception as e:
                            logging.warning(f'删除文件失败 {file_path}: {e}')

        # 删除生成的文本文件
        if payload.delete_temp_word:
            temp_word_dir = get_platform_safe_path('temp_word')
            if Path(temp_word_dir).exists():
                for file_path in Path(temp_word_dir).glob('*'):
                    if file_path.is_file():
                        try:
                            file_path.unlink()
                            deleted_paths.append(str(file_path))
                        except Exception as e:
                            logging.warning(f'删除文件失败 {file_path}: {e}')

        logging.info(f'项目 {project_id} 清理了 {len(deleted_paths)} 个临时文件')
        return JSONResponse(
            content={
                'message': f'成功清理 {len(deleted_paths)} 个临时文件',
                'deleted_count': len(deleted_paths),
                'deleted_paths': deleted_paths,
            }
        )

    except Exception as e:
        logging.error(f'清理临时文件时出错: {e}')
        return JSONResponse(
            status_code=500, content={'error': f'清理临时文件失败: {str(e)}'}
        )


@app.post('/api/init-upload')
async def init_upload(
    files: List[UploadFile] = File(...), db: Session = Depends(get_db)
):
    """
    初始化上传接口：接收招标文件和投标文件，快速提取投标人名称供用户确认
    """
    try:
        tender_file = None
        bid_files = []

        # 分离招标文件和投标文件
        for file in files:
            if file.filename and '招标' in file.filename:
                tender_file = file
            else:
                bid_files.append(file)

        if not tender_file:
            return JSONResponse(status_code=400, content={'error': '未找到招标文件'})

        # 保存招标文件
        tender_file_path = save_upload_file(
            tender_file, f'tender_{tender_file.filename}'
        )

        # 保存投标文件并提取投标人名称
        bidder_info = []
        bid_documents = []  # 保存创建的投标文档记录
        for bid_file in bid_files:
            if bid_file.filename:
                # 保存文件
                bid_file_path = save_upload_file(bid_file, f'bid_{bid_file.filename}')

                # 创建投标文档记录
                bid_document = BidDocument(
                    file_path=bid_file_path,
                    upload_time=datetime.datetime.now(timezone.utc),
                    processing_status='pending',
                )
                db.add(bid_document)
                db.flush()  # 获取生成的ID

                # 使用文件名作为默认投标人名称
                default_bidder_name = bid_file.filename or '未知投标人'
                # 移除文件扩展名
                if '.' in default_bidder_name:
                    default_bidder_name = default_bidder_name.rsplit('.', 1)[0]

                # 更新投标文档记录的投标人名称
                bid_document.bidder_name = default_bidder_name
                bid_documents.append(bid_document)  # 保存到列表中

                bidder_info.append(
                    {
                        'id': bid_document.id,
                        'original_filename': bid_file.filename,
                        'bidder_name': default_bidder_name,
                        'file_path': bid_file_path,
                    }
                )

        # 创建项目记录
        project = TenderProject(
            tender_file_path=tender_file_path,
            created_at=datetime.datetime.now(timezone.utc),
            name=f'项目-{datetime.datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")}',
            project_code=f'PROJ-{datetime.datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}',
            description=f'通过招标文件 {tender_file.filename} 创建的项目',
        )
        db.add(project)
        db.flush()

        # 更新投标文档记录，关联到项目
        for bid_document in bid_documents:
            bid_document.project_id = project.id

            # 为每个投标文件创建对应的分析结果记录
            analysis_result = AnalysisResult(
                project_id=project.id,
                bid_document_id=bid_document.id,
                bidder_name=bid_document.bidder_name,
            )
            db.add(analysis_result)

        db.commit()

        # 在后台初始化项目分析（提取评分规则）
        # 使用线程而不是进程来避免数据库会话问题
        def init_project_analysis():
            try:
                initialize_project_analysis(project.id)
            except Exception as e:
                logging.error(f'初始化项目分析失败: {e}', exc_info=True)

        # 启动后台线程进行评分规则提取
        import threading

        thread = threading.Thread(target=init_project_analysis)
        thread.start()

        return JSONResponse(
            content={
                'project_id': project.id,
                'tender_file_path': tender_file_path,
                'bidder_info': bidder_info,
            }
        )

    except Exception as e:
        db.rollback()
        logging.error(f'初始化上传时出错: {e}')
        return JSONResponse(status_code=500, content={'error': f'上传失败: {str(e)}'})


@app.get('/api/projects/{project_id}/bidders')
async def list_project_bidders(project_id: int, db: Session = Depends(get_db)):
    """列出项目下的投标文件与当前名称，供前端展示和编辑。"""
    docs = db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
    return JSONResponse(
        content=[
            {
                'id': d.id,
                'bidder_name': d.bidder_name,
                'status': d.processing_status,
                'file_path': d.file_path,
                'file_size': d.file_size,
            }
            for d in docs
        ]
    )


@app.post('/api/projects/{project_id}/start-analysis')
async def start_analysis(
    project_id: int,
    payload: StartAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """根据前端确认后的名称启动分析，名称写回数据库并用于后续流程。"""
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        # 更新投标方名称
        ids = {
            item.get('id'): (item.get('confirmed_name') or '').strip()
            for item in payload.bidders
        }

        # 不在此处校验公司名称合法性，延后至AI分析结果产出后再统一校正

        bid_documents = (
            db.query(BidDocument).filter(BidDocument.project_id == project_id).all()
        )

        if not bid_documents:
            return JSONResponse(status_code=404, content={'error': '未找到投标文件'})

        updated_count = 0
        for doc in bid_documents:
            if doc.id in ids and ids[doc.id]:
                old_name = doc.bidder_name
                doc.bidder_name = ids[doc.id]  # type: ignore[assignment]
                logging.info(f'更新投标方名称: {old_name} -> {ids[doc.id]}')
                updated_count += 1

            # 切换状态为待处理
            doc.processing_status = 'pending'
            doc.progress_current_rule = '准备中...'

            # 确保对应的分析结果记录存在
            analysis_result = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.bid_document_id == doc.id)
                .first()
            )
            if not analysis_result:
                analysis_result = AnalysisResult(
                    project_id=project_id,
                    bid_document_id=doc.id,
                    bidder_name=doc.bidder_name,
                )
                db.add(analysis_result)

        project.status = 'processing'
        db.commit()
        logging.info(f'项目 {project_id} 已更新 {updated_count} 个投标方名称，开始分析')

        # 启动后台分析
        bid_files_info = [
            {'id': d.id, 'path': d.file_path, 'bidder_name': d.bidder_name}
            for d in bid_documents
        ]

        # 确保为每个投标文件都创建分析任务
        if bid_files_info:
            background_tasks.add_task(
                run_analysis_and_calculate_prices, project_id, bid_files_info
            )
        else:
            logging.warning(f'项目 {project_id} 没有需要分析的投标文件')
            project.status = 'completed'
            db.commit()

        return JSONResponse(content={'message': '分析已启动', 'project_id': project_id})
    except Exception as e:
        logging.error(f'启动分析时出错: {e}')
        db.rollback()
        return JSONResponse(
            status_code=500, content={'error': f'服务器内部错误: {str(e)}'}
        )


@app.post('/api/analysis-results/bulk-update-scores')
async def bulk_update_scores(
    score_updates: List[ScoreUpdateItem], db: Session = Depends(get_db)
):
    updated_count = 0
    for update in score_updates:
        result = db.query(AnalysisResult).filter(AnalysisResult.id == update.id).first()
        if result:
            result.total_score = update.total_score
            updated_count += 1

    if updated_count > 0:
        db.commit()
        logging.info(f'成功更新了 {updated_count} 条分析结果的总分。')
        return JSONResponse(
            content={'message': f'成功更新了 {updated_count} 条分析结果的总分。'}
        )
    else:
        logging.warning('批量更新分数请求未找到任何有效的分析结果。')
        return JSONResponse(
            status_code=404, content={'error': '未找到任何有效的分析结果进行更新。'}
        )


@app.post('/api/projects/{project_id}/extract-scoring-rules')
async def extract_scoring_rules_api(
    project_id: int, request: Request, db: Session = Depends(get_db)
) -> JSONResponse:
    """
    从项目关联的招标文件中提取评分规则

    Args:
        project_id: 项目ID
        request: 请求对象
        db: 数据库会话

    Returns:
        JSON响应
    """
    # 添加返回类型提示以提高类型安全性
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        # 检查项目是否有招标文件
        if not project.tender_file_path or not Path(project.tender_file_path).exists():
            return JSONResponse(
                status_code=400, content={'error': '项目没有关联的招标文件'}
            )

        # 使用评分提取器提取评分规则
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(project.tender_file_path)

        # 保存到数据库
        if scoring_rules:
            # 删除该项目已有的评分规则
            db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()

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
            return JSONResponse(
                content={
                    'message': '评分规则提取并保存成功',
                    'count': len(scoring_rules),
                    'rules': scoring_rules,
                }
            )
        else:
            return JSONResponse(status_code=500, content={'error': '提取评分规则失败'})

    except Exception as e:
        logging.error(f'提取评分规则API出错: {e}')
        return JSONResponse(
            status_code=500, content={'error': f'提取评分规则时发生错误: {str(e)}'}
        )


@app.get('/api/projects/{project_id}/export-excel')
async def export_project_results_excel(project_id: int, db: Session = Depends(get_db)):
    """导出项目结果到Excel文件"""
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        # 获取分析结果
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .order_by(AnalysisResult.total_score.desc())
            .all()
        )

        if not results:
            return JSONResponse(status_code=404, content={'error': '未找到分析结果'})

        # 获取动态汇总表数据
        summary_data = generate_summary_data(project_id, db)
        if 'error' in summary_data:
            return JSONResponse(status_code=404, content=summary_data)

        # 创建Excel文件
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 创建汇总表
            if 'header_rows' in summary_data and len(summary_data['header_rows']) >= 2:
                # 准备数据
                rows_data = []
                for row in summary_data['rows']:
                    row_data = [row['rank'], row['bidder_name']]

                    # 添加子项得分
                    for score in row['scores']:
                        row_data.append(score if score is not None else 0)

                    # 添加价格分和总分
                    row_data.append(
                        row['price_score'] if row['price_score'] is not None else 0
                    )
                    row_data.append(row['total_score'])

                    rows_data.append(row_data)

                # 创建DataFrame
                if (
                    'header_rows' in summary_data
                    and len(summary_data['header_rows']) >= 2
                ):
                    # 构建表头
                    header_top = summary_data['header_rows'][0]
                    header_bottom = summary_data['header_rows'][1]

                    # 构建列名
                    columns = []
                    for item in header_top:
                        if 'rowspan' in item and item['rowspan'] == 2:
                            columns.append(item['name'])
                        elif 'colspan' in item:
                            # 父项，跳过
                            pass

                    # 添加子项列名
                    for item in header_bottom:
                        columns.append(item['name'])

                    # 添加价格分和总分列
                    columns.append('价格分')
                    columns.append('总分')

                    df = pd.DataFrame(rows_data, columns=columns)
                else:
                    # 默认列名
                    columns = ['排名', '投标人']
                    # 添加子项列名
                    if 'scoring_items' in summary_data:
                        for parent_name, children in summary_data[
                            'scoring_items'
                        ].items():
                            for child in children:
                                columns.append(child['name'])
                    columns.extend(['价格分', '总分'])

                    df = pd.DataFrame(rows_data, columns=columns)

                # 写入Excel
                df.to_excel(writer, sheet_name='评标结果汇总', index=False)

                # 获取工作簿和工作表对象以进行格式化
                workbook = writer.book
                worksheet = writer.sheets['评标结果汇总']

                # 设置列宽
                for i, col in enumerate(df.columns):
                    max_len = max(
                        len(str(col)),  # 列名长度
                        df[col].astype(str).str.len().max(),  # 数据最大长度
                    )
                    worksheet.set_column(i, i, min(max_len + 2, 50))  # 最大宽度50

                # 设置表头格式
                header_format = workbook.add_format(
                    {
                        'bold': True,
                        'text_wrap': True,
                        'valign': 'top',
                        'fg_color': '#D7E4BC',
                        'border': 1,
                    }
                )

                # 应用表头格式
                for col_num, value in enumerate(df.columns.values):
                    worksheet.write(0, col_num, value, header_format)

            # 为每个投标人创建详细评分表
            for result in results:
                # 创建详细评分数据
                detailed_data = []
                if result.detailed_scores:
                    try:
                        scores = (
                            json.loads(result.detailed_scores)
                            if isinstance(result.detailed_scores, str)
                            else result.detailed_scores
                        )

                        # 处理不同格式的详细评分
                        if isinstance(scores, list):
                            for score_item in scores:
                                # 新格式：包含Child_Item_Name、score、reason等字段
                                if 'Child_Item_Name' in score_item:
                                    detailed_data.append(
                                        {
                                            '评分项': score_item.get(
                                                'Child_Item_Name', ''
                                            ),
                                            '满分': score_item.get('max_score', ''),
                                            '得分': score_item.get('score', ''),
                                            '评分说明': score_item.get('reason', ''),
                                        }
                                    )
                                # 旧格式：包含criteria_name、max_score、score、reason等字段
                                elif 'criteria_name' in score_item:
                                    detailed_data.append(
                                        {
                                            '评分项': score_item.get(
                                                'criteria_name', ''
                                            ),
                                            '满分': score_item.get('max_score', ''),
                                            '得分': score_item.get('score', ''),
                                            '评分说明': score_item.get('reason', ''),
                                        }
                                    )
                        elif isinstance(scores, dict):
                            # 旧格式：字典形式
                            for criteria_name, score_info in scores.items():
                                if isinstance(score_info, dict):
                                    detailed_data.append(
                                        {
                                            '评分项': criteria_name,
                                            '满分': score_info.get('max_score', ''),
                                            '得分': score_info.get('score', ''),
                                            '评分说明': score_info.get('reason', ''),
                                        }
                                    )
                                else:
                                    detailed_data.append(
                                        {
                                            '评分项': criteria_name,
                                            '满分': '',
                                            '得分': score_info,
                                            '评分说明': '',
                                        }
                                    )
                    except Exception as e:
                        logging.error(
                            f'解析投标人 {result.bidder_name} 的详细评分时出错: {e}'
                        )

                # 创建DataFrame并写入Excel
                if detailed_data:
                    df_detailed = pd.DataFrame(detailed_data)
                    # 限制工作表名称长度
                    sheet_name = (
                        result.bidder_name[:31]
                        if result.bidder_name
                        else f'投标人_{result.id}'
                    )
                    # 确保工作表名称唯一
                    sheet_name = (
                        sheet_name.replace(':', '_')
                        .replace('\\', '_')
                        .replace('/', '_')
                        .replace('?', '_')
                        .replace('*', '_')
                        .replace('[', '_')
                        .replace(']', '_')
                    )
                    df_detailed.to_excel(writer, sheet_name=sheet_name, index=False)

                    # 格式化详细评分表
                    if sheet_name in writer.sheets:
                        worksheet_detailed = writer.sheets[sheet_name]
                        for i, col in enumerate(df_detailed.columns):
                            max_len = max(
                                len(str(col)),
                                df_detailed[col].astype(str).str.len().max(),
                            )
                            worksheet_detailed.set_column(i, i, min(max_len + 2, 50))

        # 准备响应
        output.seek(0)
        headers = {
            'Content-Disposition': f'attachment; filename="评标结果_{project_id}.xlsx"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        return StreamingResponse(io.BytesIO(output.getvalue()), headers=headers)

    except Exception as e:
        logging.error(f'导出Excel文件时出错: {e}')
        return JSONResponse(
            status_code=500, content={'error': f'导出Excel文件失败: {str(e)}'}
        )


@app.get('/api/projects/{project_id}/export-word')
async def export_project_results_word(project_id: int, db: Session = Depends(get_db)):
    """导出项目结果到Word文件"""
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            return JSONResponse(status_code=404, content={'error': '项目不存在'})

        # 获取分析结果
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .order_by(AnalysisResult.total_score.desc())
            .all()
        )

        if not results:
            return JSONResponse(status_code=404, content={'error': '未找到分析结果'})

        # 获取动态汇总表数据
        summary_data = generate_summary_data(project_id, db)
        if 'error' in summary_data:
            return JSONResponse(status_code=404, content=summary_data)

        # 创建Word文档
        doc = Document()

        # 添加标题
        title = doc.add_heading('评标结果报告', 0)
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 添加项目信息
        doc.add_heading('项目信息', level=1)
        doc.add_paragraph(f'项目ID: {project.id}')
        doc.add_paragraph(f'项目名称: {project.name or "N/A"}')
        doc.add_paragraph(f'项目代码: {project.project_code or "N/A"}')
        doc.add_paragraph(
            f'创建时间: {project.created_at.strftime("%Y-%m-%d %H:%M:%S") if project.created_at else "N/A"}'
        )

        # 添加汇总表
        doc.add_heading('评标结果汇总表', level=1)

        if 'header_rows' in summary_data and len(summary_data['header_rows']) >= 2:
            # 创建表格
            header_top = summary_data['header_rows'][0]
            header_bottom = summary_data['header_rows'][1]

            # 计算列数
            num_cols = len(header_bottom) + 2  # 加上排名和投标人列

            table = doc.add_table(rows=2, cols=num_cols)
            table.style = 'Table Grid'

            # 填充表头
            # 第一行
            cell_idx = 0
            for item in header_top:
                if 'rowspan' in item and item['rowspan'] == 2:
                    cell = table.cell(0, cell_idx)
                    cell.text = item['name']
                    cell.merge(table.cell(1, cell_idx))
                    cell_idx += 1
                elif 'colspan' in item:
                    # 父项，需要合并单元格
                    start_cell_idx = cell_idx
                    for i in range(item['colspan']):
                        cell_idx += 1
                    # 合并父项单元格
                    cell = table.cell(0, start_cell_idx)
                    cell.text = item['name']
                    cell.merge(table.cell(0, cell_idx - 1))

            # 第二行
            cell_idx = 2  # 跳过排名和投标人列
            for item in header_bottom:
                table.cell(1, cell_idx).text = item['name']
                cell_idx += 1

            # 添加价格分和总分列标题
            table.cell(0, cell_idx).text = '价格分'
            table.cell(0, cell_idx).merge(table.cell(1, cell_idx))
            cell_idx += 1
            table.cell(0, cell_idx).text = '总分'
            table.cell(0, cell_idx).merge(table.cell(1, cell_idx))

            # 填充数据
            for row_data in summary_data['rows']:
                row_cells = table.add_row().cells
                row_cells[0].text = str(row_data['rank'])
                row_cells[1].text = row_data['bidder_name']

                # 填充子项得分
                for i, score in enumerate(row_data['scores']):
                    row_cells[i + 2].text = f'{score:.2f}' if score is not None else '—'

                # 填充价格分和总分
                row_cells[-2].text = (
                    f'{row_data["price_score"]:.2f}'
                    if row_data['price_score'] is not None
                    else '—'
                )
                row_cells[-1].text = f'{row_data["total_score"]:.2f}'
        else:
            # 简化版表格
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = '排名'
            hdr_cells[1].text = '投标人'
            hdr_cells[2].text = '总分'
            hdr_cells[3].text = '价格分'

            # 填充数据
            for row_data in summary_data['rows']:
                row_cells = table.add_row().cells
                row_cells[0].text = str(row_data['rank'])
                row_cells[1].text = row_data['bidder_name']
                row_cells[2].text = f'{row_data["total_score"]:.2f}'
                row_cells[3].text = (
                    f'{row_data["price_score"]:.2f}'
                    if row_data['price_score'] is not None
                    else '—'
                )

        # 为每个投标人添加详细评分
        for result in results:
            doc.add_page_break()
            doc.add_heading(f'投标人详细评分 - {result.bidder_name}', level=1)

            # 添加基本信息
            doc.add_paragraph(
                f'投标总价: {result.extracted_price if result.extracted_price else "N/A"}'
            )
            doc.add_paragraph(f'AI模型: {result.ai_model or "N/A"}')

            # 添加详细评分表
            if result.detailed_scores:
                try:
                    scores = (
                        json.loads(result.detailed_scores)
                        if isinstance(result.detailed_scores, str)
                        else result.detailed_scores
                    )

                    if scores:
                        # 创建详细评分表格
                        table = doc.add_table(rows=1, cols=4)
                        table.style = 'Table Grid'
                        hdr_cells = table.rows[0].cells
                        hdr_cells[0].text = '评分项'
                        hdr_cells[1].text = '满分'
                        hdr_cells[2].text = '得分'
                        hdr_cells[3].text = '评分说明'

                        # 填充数据
                        if isinstance(scores, list):
                            for score_item in scores:
                                # 新格式
                                if 'Child_Item_Name' in score_item:
                                    row_cells = table.add_row().cells
                                    row_cells[0].text = str(
                                        score_item.get('Child_Item_Name', '')
                                    )
                                    row_cells[1].text = str(
                                        score_item.get('max_score', '')
                                    )
                                    row_cells[2].text = (
                                        f'{score_item.get("score", ""):.2f}'
                                        if score_item.get('score') is not None
                                        else ''
                                    )
                                    row_cells[3].text = str(
                                        score_item.get('reason', '')
                                    )
                                # 旧格式
                                elif 'criteria_name' in score_item:
                                    row_cells = table.add_row().cells
                                    row_cells[0].text = str(
                                        score_item.get('criteria_name', '')
                                    )
                                    row_cells[1].text = str(
                                        score_item.get('max_score', '')
                                    )
                                    row_cells[2].text = (
                                        f'{score_item.get("score", ""):.2f}'
                                        if score_item.get('score') is not None
                                        else ''
                                    )
                                    row_cells[3].text = str(
                                        score_item.get('reason', '')
                                    )
                        elif isinstance(scores, dict):
                            # 旧格式：字典形式
                            for criteria_name, score_info in scores.items():
                                row_cells = table.add_row().cells
                                row_cells[0].text = criteria_name
                                if isinstance(score_info, dict):
                                    row_cells[1].text = str(
                                        score_info.get('max_score', '')
                                    )
                                    row_cells[2].text = (
                                        f'{score_info.get("score", ""):.2f}'
                                        if score_info.get('score') is not None
                                        else ''
                                    )
                                    row_cells[3].text = str(
                                        score_info.get('reason', '')
                                    )
                                else:
                                    row_cells[1].text = ''
                                    row_cells[2].text = (
                                        f'{score_info:.2f}'
                                        if score_info is not None
                                        else ''
                                    )
                                    row_cells[3].text = ''
                except Exception as e:
                    logging.error(
                        f'生成投标人 {result.bidder_name} 的详细评分表时出错: {e}'
                    )
                    doc.add_paragraph(f'详细评分数据解析错误: {str(e)}')

        # 保存到内存
        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        # 准备响应
        headers = {
            'Content-Disposition': f'attachment; filename="评标结果_{project_id}.docx"',
            'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        return StreamingResponse(io.BytesIO(buffer.getvalue()), headers=headers)

    except Exception as e:
        logging.error(f'导出Word文件时出错: {e}')
        return JSONResponse(
            status_code=500, content={'error': f'导出Word文件失败: {str(e)}'}
        )


if __name__ == '__main__':
    # 启动FastAPI应用
    uvicorn.run(app, host='0.0.0.0', port=8000, access_log=False)
