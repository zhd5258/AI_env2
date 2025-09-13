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
from sqlalchemy.orm import sessionmaker, relationship
import datetime

DATABASE_URL = 'sqlite:///./tender_evaluation.db'

engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TenderProject(Base):
    __tablename__ = 'tender_project'
    id = Column(Integer, primary_key=True, index=True)
    project_code = Column(String, unique=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    tender_file_path = Column(String)
    scoring_rules_summary = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String, default='new')
    bid_documents = relationship('BidDocument', back_populates='project')
    analysis_results = relationship('AnalysisResult', back_populates='project')
    scoring_rules = relationship('ScoringRule', back_populates='project')
    audit_logs = relationship('ProjectAuditLog', back_populates='project')


class BidDocument(Base):
    __tablename__ = 'bid_document'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('tender_project.id'))
    bidder_name = Column(String)
    file_path = Column(String)
    file_size = Column(Integer)
    upload_time = Column(DateTime, default=datetime.datetime.utcnow)
    processing_status = Column(String, default='pending')
    error_message = Column(String, nullable=True)

    # Fields for progress tracking
    progress_total_rules = Column(Integer, default=0)
    progress_completed_rules = Column(Integer, default=0)
    progress_current_rule = Column(String, nullable=True)
    # Adding partial analysis results field
    partial_analysis_results = Column(String, nullable=True)
    # Adding detailed progress information field
    detailed_progress_info = Column(String, nullable=True)
    # Adding PDF processing failed page record field
    failed_pages_info = Column(String, nullable=True)

    project = relationship('TenderProject', back_populates='bid_documents')
    analysis_result = relationship(
        'AnalysisResult', back_populates='bid_document', uselist=False
    )


class AnalysisResult(Base):
    __tablename__ = 'analysis_result'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('tender_project.id'))
    bid_document_id = Column(Integer, ForeignKey('bid_document.id'))
    bidder_name = Column(String)
    total_score = Column(Float)
    price_score = Column(Float)  # Adding price score field
    extracted_price = Column(Float) # Extracted bid price
    detailed_scores = Column(JSON)
    analysis_summary = Column(String)
    analyzed_at = Column(DateTime, default=datetime.datetime.utcnow)
    scoring_method = Column(String, default='AI')
    ai_model = Column(String, nullable=True)  # To store the AI model name
    is_modified = Column(Boolean, default=False)
    original_scores = Column(JSON)
    modification_count = Column(Integer, default=0)
    last_modified_at = Column(DateTime)
    last_modified_by = Column(String)
    project = relationship('TenderProject', back_populates='analysis_results')
    bid_document = relationship('BidDocument', back_populates='analysis_result')
    modification_history = relationship(
        'ScoreModificationHistory', back_populates='analysis_result'
    )


class ScoringRule(Base):
    __tablename__ = 'scoring_rule'
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('tender_project.id'))
    Parent_Item_Name = Column(String(20))
    Parent_max_score = Column(Integer)
    Child_Item_Name = Column(String(20))
    Child_max_score = Column(Integer)
    description = Column(String(100))
    is_veto = Column(Boolean)
    is_price_criteria = Column(Boolean)
    price_formula = Column(String(100))
    
    project = relationship('TenderProject', back_populates='scoring_rules')


class ScoreModificationHistory(Base):
    __tablename__ = 'score_modification_history'
    id = Column(Integer, primary_key=True, index=True)
    analysis_result_id = Column(Integer, ForeignKey('analysis_result.id'))
    criteria_name = Column(String)
    original_score = Column(Float)
    new_score = Column(Float)
    original_reason = Column(String)
    new_reason = Column(String)
    modification_type = Column(String)
    modified_by = Column(String)
    modified_at = Column(DateTime, default=datetime.datetime.utcnow)
    modification_reason = Column(String)
    approval_status = Column(String, default='approved')
    approved_by = Column(String)
    approved_at = Column(DateTime)
    analysis_result = relationship(
        'AnalysisResult', back_populates='modification_history'
    )


class ProjectAuditLog(Base):
    __tablename__ = 'project_audit_log'
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('tender_project.id'))
    operation_type = Column(String)
    operation_details = Column(JSON)
    operator = Column(String)
    operation_time = Column(DateTime, default=datetime.datetime.utcnow)
    ip_address = Column(String)
    user_agent = Column(String)
    project = relationship('TenderProject', back_populates='audit_logs')


Base.metadata.create_all(bind=engine)