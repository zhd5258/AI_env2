# pyright: ignore[reportGeneralTypeIssues,reportOperatorIssue,reportIndexIssue,reportUnnecessaryComparison,reportUnnecessaryCondition,reportAttributeAccessIssue,reportOptionalMemberAccess,reportAssignmentType,reportArgumentType,reportUnnecessaryCondition,reportUnnecessaryComparison]
import uvicorn
import os
import shutil
import datetime
import json
import asyncio
import logging
import sys
import traceback
import time
import threading
from typing import List, Optional
from concurrent.futures import ProcessPoolExecutor

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
from modules.bidder_name_extractor import extract_bidder_name_from_file
from modules.summary_generator import generate_summary_data


# 评分规则提取器
from modules.scoring_extractor import IntelligentScoringExtractor

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
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
        if (
            hasattr(sys.stderr, 'detach')
            and callable(getattr(sys.stderr, 'detach', None))
            and not sys.stderr.closed
        ):
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
    except (ValueError, AttributeError):
        # 当stdout/stderr已经被分离时，使用默认的编码
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


# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 创建一个进程池
executor = ProcessPoolExecutor(max_workers=os.cpu_count())

# 创建上传目录
UPLOADS_DIR = 'uploads'
os.makedirs(UPLOADS_DIR, exist_ok=True)

# 配置静态文件和模板
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory='templates')

# 创建数据库表
TenderProject.metadata.create_all(bind=engine)
BidDocument.metadata.create_all(bind=engine)
AnalysisResult.metadata.create_all(bind=engine)


# 首页
@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse('index.html', {'request': request})
    except Exception as e:
        logging.error('Error rendering template: %s', str(e))
        return HTMLResponse(content=f'Error: {str(e)}', status_code=500)


@app.get('/history', response_class=HTMLResponse)
async def history_page(request: Request):
    try:
        return templates.TemplateResponse('history.html', {'request': request})
    except Exception as e:
        logging.error('Error rendering template: %s', str(e))
        return HTMLResponse(content=f'Error: {str(e)}', status_code=500)


def save_upload_file(upload_file: UploadFile, destination: str) -> str:
    try:
        with open(destination, 'wb') as buffer:
            shutil.copyfileobj(upload_file.file, buffer)
    finally:
        upload_file.file.close()
    return destination


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
        if not tender_file_path or not os.path.exists(tender_file_path):
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

        analyzer = IntelligentBidAnalyzer(
            tender_file_path,
            bid_document.file_path,
            db_session=db,
            bid_document_id=bid_document.id,
            project_id=project_id,
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


def run_analysis_and_calculate_prices(project_id: int, bid_files_info: list):
    logging.info(f'开始为项目 {project_id} 执行后台分析和价格计算任务。')

    # 首先提取评分规则并保存到数据库
    db = SessionLocal()
    try:
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if (
            project
            and project.tender_file_path
            and os.path.exists(project.tender_file_path)
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
                extractor = IntelligentScoringExtractor()
                scoring_rules = extractor.extract(
                    project.tender_file_path
                )

                if scoring_rules:
                    # Manually save rules to the database
                    db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
                    
                    def save_rule_recursive(rule_data, project_id, parent_id=None):
                        """递归保存评分规则"""
                        # 创建评分规则对象
                        db_rule = ScoringRule(
                            project_id=project_id,
                            Parent_Item_Name=rule_data.get('criteria_name'),
                            Parent_max_score=rule_data.get('max_score'),
                            description=rule_data.get('description', ''),
                            is_price_criteria='价格' in rule_data.get('criteria_name', '') or 'price' in rule_data.get('criteria_name', '').lower()
                        )
                        
                        # 如果是价格规则，设置价格公式字段
                        if db_rule.is_price_criteria:
                            db_rule.price_formula = None  # 可以根据需要设置具体公式
                            db_rule.Child_Item_Name = None
                            db_rule.Child_max_score = None
                        else:
                            # 对于非价格规则，如果有子项，需要特殊处理
                            if 'children' in rule_data and rule_data['children']:
                                # 父项规则，子项信息将在子项规则中保存
                                db_rule.Child_Item_Name = None
                                db_rule.Child_max_score = None
                            else:
                                # 叶子节点规则（没有子项）
                                db_rule.Child_Item_Name = rule_data.get('criteria_name')
                                db_rule.Child_max_score = rule_data.get('max_score')
                        
                        db.add(db_rule)
                        db.flush()  # 获取生成的ID
                        
                        # 递归保存子项
                        if 'children' in rule_data and rule_data['children']:
                            for child_rule in rule_data['children']:
                                save_rule_recursive(child_rule, project_id, parent_id=db_rule.id)
                    
                    for rule_data in scoring_rules:
                        save_rule_recursive(rule_data, project_id)
                        
                    db.commit()
                    logging.info(
                        f'成功提取并保存 {len(scoring_rules)} 条评分规则到数据库'
                    )
                else:
                    logging.error(f'提取评分规则失败')
            else:
                logging.info(f'项目 {project_id} 已存在评分规则，跳过提取步骤')
    except Exception as e:
        logging.error(f'处理项目 {project_id} 的评分规则时出错: {e}')
    finally:
        db.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    futures = [
        loop.run_in_executor(executor, analysis_task, project_id, bid_info['id'])
        for bid_info in bid_files_info
    ]

    loop.run_until_complete(asyncio.gather(*futures))
    logging.info(f'项目 {project_id} 的所有分析任务已完成。')

    db = SessionLocal()
    try:
        logging.info(f'开始为项目 {project_id} 计算价格分。')
        calculator = PriceScoreCalculator(db_session=db)
        price_scores = calculator.calculate_project_price_scores(project_id)

        if price_scores:
            logging.info(
                f'项目 {project_id} 价格分计算完成，更新了 {len(price_scores)} 个投标方。'
            )
        else:
            logging.warning(f'项目 {project_id} 未能计算出任何价格分。')

        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if project:
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
            logging.info(f'项目 {project_id} 的状态已更新为 {project.status}。')

    except Exception as e:
        logging.error(f'为项目 {project_id} 计算价格分时出错: {e}')
        logging.error(traceback.format_exc())
    finally:
        db.close()
        loop.close()


@app.post('/api/analyze-immediately')
async def analyze_immediately(
    background_tasks: BackgroundTasks,
    tender_file: UploadFile = File(...),
    bid_files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    logging.info(
        "Received request to analyze tender '%s' with %s bid files.",
        tender_file.filename,
        len(bid_files),
    )
    project_code = f'PRJ-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}'
    project = TenderProject(
        project_code=project_code,
        name=f'Project {project_code}',
        description=f'Tender: {tender_file.filename}',
        status='processing',
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logging.info('Created project with id: %s', project.id)

    tender_file_path = save_upload_file(
        tender_file,
        os.path.join(UPLOADS_DIR, f'{project.id}_tender_{tender_file.filename}'),
    )
    project.tender_file_path = tender_file_path
    db.commit()

    bid_files_info = []
    for bid_file in bid_files:
        bid_file_path = save_upload_file(
            bid_file, os.path.join(UPLOADS_DIR, f'{project.id}_bid_{bid_file.filename}')
        )

        extracted_name = extract_bidder_name_from_file(bid_file_path)

        bidder_name = extracted_name
        if not bidder_name:
            bidder_name = (
                os.path.splitext(bid_file.filename)[0]
                if bid_file.filename
                else f'unnamed_bid_{bid_file.size}'
            )
            logging.warning(
                f"无法从 {bid_file.filename} 中提取投标方名称，将使用文件名 '{bidder_name}' 作为备用。"
            )

        bid_document = BidDocument(
            project_id=project.id,
            bidder_name=bidder_name,
            file_path=bid_file_path,
            file_size=bid_file.size,
            processing_status='pending',
            progress_total_rules=0,
            progress_completed_rules=0,
            progress_current_rule='准备中...',
        )
        db.add(bid_document)
        db.commit()
        db.refresh(bid_document)
        bid_files_info.append({'id': bid_document.id, 'path': bid_file_path})

    background_tasks.add_task(
        run_analysis_and_calculate_prices,
        project.id,
        bid_files_info,
    )
    logging.info('已为项目 %s 安排后台分析和价格计算任务。', project.id)

    return JSONResponse(content={'project_id': project.id})


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
        if doc.partial_analysis_results:
            try:
                partial_results = json.loads(doc.partial_analysis_results)
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

    if all_completed and project.status != 'completed':
        project.status = 'completed_with_errors' if has_errors else 'completed'
        db.commit()

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
                'criteria_name': rule.Child_Item_Name if rule.Child_Item_Name else rule.Parent_Item_Name,
                'max_score': rule.Child_max_score if rule.Child_max_score else rule.Parent_max_score,
                'weight': 1.0,
                'description': rule.description,
                'is_veto': rule.is_veto,
            }
        )

    return JSONResponse(content=response_data)


@app.get('/api/projects')
async def get_all_projects(db: Session = Depends(get_db)):
    projects = db.query(TenderProject).all()

    response_data = []
    for project in projects:
        bid_count = (
            db.query(BidDocument).filter(BidDocument.project_id == project.id).count()
        )
        result_count = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project.id)
            .count()
        )

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
                'bid_count': bid_count,
                'result_count': result_count,
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
        if 'error' in summary_data:
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
        if not project.tender_file_path or not os.path.exists(project.tender_file_path):
            return JSONResponse(
                status_code=400, content={'error': '项目没有关联的招标文件'}
            )

        # 使用评分提取器提取评分规则
        extractor = IntelligentScoringExtractor()
        scoring_rules = extractor.extract(
            project.tender_file_path
        )

        # 保存到数据库
        if scoring_rules:
            # Manually save rules to the database
            db.query(ScoringRule).filter(ScoringRule.project_id == project_id).delete()
            
            def save_rule_recursive(rule_data, project_id, parent_id=None):
                """递归保存评分规则"""
                # 创建评分规则对象
                db_rule = ScoringRule(
                    project_id=project_id,
                    Parent_Item_Name=rule_data.get('criteria_name'),
                    Parent_max_score=rule_data.get('max_score'),
                    description=rule_data.get('description', ''),
                    is_price_criteria='价格' in rule_data.get('criteria_name', '') or 'price' in rule_data.get('criteria_name', '').lower()
                )
                        
                # 如果是价格规则，设置价格公式字段
                if db_rule.is_price_criteria:
                    db_rule.price_formula = None  # 可以根据需要设置具体公式
                    db_rule.Child_Item_Name = None
                    db_rule.Child_max_score = None
                else:
                    # 对于非价格规则，如果有子项，需要特殊处理
                    if 'children' in rule_data and rule_data['children']:
                        # 父项规则，子项信息将在子项规则中保存
                        db_rule.Child_Item_Name = None
                        db_rule.Child_max_score = None
                    else:
                        # 叶子节点规则（没有子项）
                        db_rule.Child_Item_Name = rule_data.get('criteria_name')
                        db_rule.Child_max_score = rule_data.get('max_score')
                        
                        db.add(db_rule)
                        db.flush()  # 获取生成的ID
                        
                        # 递归保存子项
                        if 'children' in rule_data and rule_data['children']:
                            for child_rule in rule_data['children']:
                                save_rule_recursive(child_rule, project_id, parent_id=db_rule.id)
                    
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


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
