#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-03 14:24:39
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-03 14:24:42
# 文件相对于项目的路径   : \AI_env2\models\database.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    DateTime,
    JSON,
    Boolean,
    ForeignKey,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Mapped, mapped_column
import datetime
import os

# 获取本地时区
LOCAL_TZ = datetime.timezone(datetime.timedelta(hours=8))


def get_local_time():
    """获取本地时间"""
    return datetime.datetime.now(LOCAL_TZ).replace(tzinfo=None)


DATABASE_URL = 'sqlite:///' + os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'db', 'tender_evaluation.db')
)

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TenderProject(Base):
    __tablename__ = 'tender_project'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_code: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    tender_file_path: Mapped[str] = mapped_column(String)
    scoring_rules_summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=get_local_time
    )
    status: Mapped[str] = mapped_column(String, default='new')
    # 添加评标开始和结束时间字段
    analysis_start_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=True
    )
    analysis_end_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=True
    )
    bid_documents = relationship('BidDocument', back_populates='project')
    analysis_results = relationship('AnalysisResult', back_populates='project')
    scoring_rules = relationship('ScoringRule', back_populates='project')
    audit_logs = relationship('ProjectAuditLog', back_populates='project')


class BidDocument(Base):
    __tablename__ = 'bid_document'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey('tender_project.id'))
    bidder_name: Mapped[str] = mapped_column(String)
    file_path: Mapped[str] = mapped_column(String)
    original_filename: Mapped[str] = mapped_column(String)  # 添加原始文件名字段
    file_size: Mapped[int] = mapped_column(Integer)
    upload_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=get_local_time
    )
    processing_status: Mapped[str] = mapped_column(String, default='pending')
    error_message: Mapped[str] = mapped_column(String, nullable=True)

    # Fields for progress tracking
    progress_total_rules: Mapped[int] = mapped_column(Integer, default=0)
    progress_completed_rules: Mapped[int] = mapped_column(Integer, default=0)
    progress_current_rule: Mapped[str] = mapped_column(String, nullable=True)
    # Adding partial analysis results field
    partial_analysis_results: Mapped[str] = mapped_column(String, nullable=True)
    # Adding detailed progress information field
    detailed_progress_info: Mapped[str] = mapped_column(String, nullable=True)
    # Adding processing phase field
    processing_phase: Mapped[str] = mapped_column(String, nullable=True)
    # Adding PDF processing failed page record field
    failed_pages_info: Mapped[str] = mapped_column(String, nullable=True)
    # Adding price extraction tracking fields
    price_extraction_attempts: Mapped[int] = mapped_column(Integer, default=0)
    price_extraction_error: Mapped[str] = mapped_column(String, nullable=True)
    price_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Adding OCR retry count field
    ocr_retry_count: Mapped[int] = mapped_column(Integer, default=0)

    project = relationship('TenderProject', back_populates='bid_documents')
    analysis_result = relationship(
        'AnalysisResult', back_populates='bid_document', uselist=False
    )


class AnalysisResult(Base):
    __tablename__ = 'analysis_result'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey('tender_project.id'))
    bid_document_id: Mapped[int] = mapped_column(Integer, ForeignKey('bid_document.id'))
    bidder_name: Mapped[str] = mapped_column(String)
    total_score: Mapped[float] = mapped_column(Float)
    price_score: Mapped[float] = mapped_column(Float)  # Adding price score field
    extracted_price: Mapped[float] = mapped_column(Float)  # Extracted bid price
    detailed_scores: Mapped[dict] = mapped_column(JSON)
    # 添加动态评分项字段，用于存储各评分项的得分
    dynamic_scores: Mapped[dict] = mapped_column(
        JSON, default=dict
    )  # 存储动态评分项得分，key为评分项简称，value为得分
    analysis_summary: Mapped[str] = mapped_column(String)
    analyzed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=get_local_time
    )
    scoring_method: Mapped[str] = mapped_column(String, default='AI')
    ai_model: Mapped[str] = mapped_column(
        String, nullable=True
    )  # To store the AI model name
    is_modified: Mapped[bool] = mapped_column(Boolean, default=False)
    original_scores: Mapped[dict] = mapped_column(JSON)
    modification_count: Mapped[int] = mapped_column(Integer, default=0)
    last_modified_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    last_modified_by: Mapped[str] = mapped_column(String)
    project = relationship('TenderProject', back_populates='analysis_results')
    bid_document = relationship('BidDocument', back_populates='analysis_result')
    modification_history = relationship(
        'ScoreModificationHistory', back_populates='analysis_result'
    )


class ScoringRule(Base):
    __tablename__ = 'scoring_rule'
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey('tender_project.id'))
    Parent_Item_Name: Mapped[str] = mapped_column(
        String(100), nullable=True
    )  # 增加长度以容纳清理后的名称
    Parent_max_score: Mapped[int] = mapped_column(Integer, nullable=True)
    Child_Item_Name: Mapped[str] = mapped_column(
        String(100), nullable=True
    )  # 增加长度以容纳清理后的名称
    Child_max_score: Mapped[int] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(
        String(500), nullable=True
    )  # 增加描述字段长度
    is_veto: Mapped[bool] = mapped_column(Boolean, default=False)
    is_price_criteria: Mapped[bool] = mapped_column(Boolean, default=False)
    price_formula: Mapped[str] = mapped_column(
        String(500), nullable=True
    )  # 增加价格公式字段长度

    project = relationship('TenderProject', back_populates='scoring_rules')


class ScoreModificationHistory(Base):
    __tablename__ = 'score_modification_history'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    analysis_result_id: Mapped[int] = mapped_column(
        Integer, ForeignKey('analysis_result.id')
    )
    criteria_name: Mapped[str] = mapped_column(String)
    original_score: Mapped[float] = mapped_column(Float)
    new_score: Mapped[float] = mapped_column(Float)
    original_reason: Mapped[str] = mapped_column(String)
    new_reason: Mapped[str] = mapped_column(String)
    modification_type: Mapped[str] = mapped_column(String)
    modified_by: Mapped[str] = mapped_column(String)
    modified_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=get_local_time
    )
    modification_reason: Mapped[str] = mapped_column(String)
    approval_status: Mapped[str] = mapped_column(String, default='approved')
    approved_by: Mapped[str] = mapped_column(String)
    approved_at: Mapped[datetime.datetime] = mapped_column(DateTime)
    analysis_result = relationship(
        'AnalysisResult', back_populates='modification_history'
    )


class ProjectAuditLog(Base):
    __tablename__ = 'project_audit_log'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey('tender_project.id'))
    operation_type: Mapped[str] = mapped_column(String)
    operation_details: Mapped[dict] = mapped_column(JSON)
    operator: Mapped[str] = mapped_column(String)
    operation_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=get_local_time
    )
    ip_address: Mapped[str] = mapped_column(String)
    user_agent: Mapped[str] = mapped_column(String)
    project = relationship('TenderProject', back_populates='audit_logs')


Base.metadata.create_all(bind=engine)
