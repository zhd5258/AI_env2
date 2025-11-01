#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
项目状态管理器模块
统一处理项目状态更新逻辑，避免在多个地方重复实现相似的功能
"""

import logging
import datetime
import time
from typing import Optional
from sqlalchemy.orm import Session
from models.database import TenderProject


class ProjectStatusManager:
    """项目状态管理器，统一处理项目状态更新逻辑"""

    def __init__(self, db_session: Optional[Session] = None):
        self.db = db_session
        self.logger = logging.getLogger(__name__)

    def update_project_status(self, project_id: int, status: str):
        """
        更新项目状态

        Args:
            project_id: 项目ID
            status: 新的项目状态
        """
        try:
            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 获取项目信息
            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )

            if not project:
                self.logger.error(f'项目 {project_id} 不存在')
                return False

            # 记录旧状态
            old_status = project.status

            # 更新项目状态
            project.status = status

            # 如果状态是完成或错误，记录结束时间
            if status in ['completed', 'completed_with_errors', 'error']:
                project.analysis_end_time = datetime.datetime.now()

            # 提交更改
            self.db.commit()

            self.logger.info(
                f'项目 {project_id} 状态已从 "{old_status}" 更新为 "{status}"'
            )
            return True

        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}')
            if self.db:
                self.db.rollback()
            return False

    def wait_and_update_project_status_when_all_completed(
        self,
        project_id: int,
        max_wait_time: int = 60,
        force_complete_after_timeout: bool = True,
        max_retries: int = 1,
        retry_interval: int = 10,
    ):
        """
        等待所有分析任务完成后再更新项目状态，解决竞态条件问题

        Args:
            project_id: 项目ID
            max_wait_time: 最大等待时间（秒）
            force_complete_after_timeout: 超时后是否强制完成卡住的任务
            max_retries: 超时后的最大重试次数
            retry_interval: 重试间隔（秒）
        """
        try:
            self.logger.info(f'等待项目 {project_id} 所有任务完成后再更新状态')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 等待所有分析任务完成
            wait_time = 0
            check_interval = 2  # 每2秒检查一次
            retry_count = 0

            # 获取项目信息用于日志记录
            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
            project_name = (
                project.name
                if project and hasattr(project, 'name')
                else f'项目{project_id}'
            )

            # 记录初始状态
            initial_completed_count = 0
            initial_total_count = 0

            while wait_time < max_wait_time:
                # 刷新数据库会话以确保获取最新数据
                self.db.flush()

                # 检查是否所有分析都已完成
                from modules.analysis_manager import AnalysisManager

                analysis_manager = AnalysisManager(db_session=self.db)

                # 获取完成和未完成的任务数量
                completed_count, total_count = (
                    analysis_manager._get_analysis_completion_stats(project_id)
                )

                # 记录初始状态
                if initial_total_count == 0:
                    initial_completed_count = completed_count
                    initial_total_count = total_count
                    self.logger.info(
                        f'项目 [{project_name}] 初始状态: {initial_completed_count}/{initial_total_count} 完成'
                    )

                if completed_count == total_count and total_count > 0:
                    self.logger.info(
                        f'项目 [{project_name}] 所有任务已完成 ({completed_count}/{total_count})，准备更新状态'
                    )
                    # 更新项目状态为completed
                    return self.update_project_status(project_id, 'completed')
                else:
                    # 检查是否状态有变化
                    if (
                        completed_count != initial_completed_count
                        or total_count != initial_total_count
                    ):
                        self.logger.info(
                            f'项目 [{project_name}] 状态发生变化: {completed_count}/{total_count} 完成'
                        )
                        initial_completed_count = completed_count
                        initial_total_count = total_count

                    remaining = max_wait_time - wait_time
                    self.logger.info(
                        f'项目 [{project_name}] 仍有任务未完成 ({completed_count}/{total_count})，'
                        f'剩余等待时间: {remaining}秒，等待 {check_interval} 秒后重试...'
                    )
                    time.sleep(check_interval)
                    wait_time += check_interval

            self.logger.warning(
                f'项目 [{project_name}] 等待超时 ({max_wait_time}秒)，仍有一些任务未完成'
            )

            # 尝试重试几次，有时候可能是暂时性问题
            if retry_count < max_retries:
                retry_count += 1
                self.logger.info(
                    f'项目 [{project_name}] 尝试第 {retry_count}/{max_retries} 次重试，等待 {retry_interval} 秒...'
                )
                time.sleep(retry_interval)
                return self.wait_and_update_project_status_when_all_completed(
                    project_id,
                    max_wait_time,
                    force_complete_after_timeout,
                    max_retries - 1,
                    retry_interval,
                )

            # 如果设置了超时后强制完成，则将所有卡住的任务标记为错误状态
            if force_complete_after_timeout:
                stuck_count = self.handle_stuck_processes(project_id)
                status = 'completed_with_errors' if stuck_count > 0 else 'completed'
                self.logger.warning(
                    f'项目 [{project_name}] 处理了 {stuck_count} 个卡住的任务，将状态更新为 {status}'
                )
                return self.update_project_status(project_id, status)

            return False

        except Exception as e:
            self.logger.error(f'等待并更新项目状态时出错: {e}')
            return False

    def handle_stuck_processes(self, project_id: int, max_retries: int = 3, force_all_processing: bool = False) -> int:
        """
        处理卡住的分析任务，将其状态更新为错误

        Args:
            project_id: 项目ID
            max_retries: 最大重试次数
            force_all_processing: 是否强制处理所有processing状态的任务（用于超时情况）

        Returns:
            int: 处理的卡住任务数量
        """
        if not self.db:
            self.logger.error('数据库会话未提供')
            return 0

        # 获取项目信息用于日志记录
        try:
            from models.database import TenderProject

            project = None
            if self.db is not None:
                project = (
                    self.db.query(TenderProject)
                    .filter(TenderProject.id == project_id)
                    .first()
                )
            project_name = (
                project.name
                if project and hasattr(project, 'name')
                else f'项目{project_id}'
            )
        except Exception:
            project_name = f'项目{project_id}'

        retry_count = 0
        while retry_count < max_retries:
            try:
                # 查找所有处于processing状态的投标文档
                from models.database import BidDocument

                if force_all_processing:
                    # 强制处理所有processing状态的任务（用于超时情况）
                    stuck_docs = []
                    if self.db is not None:
                        stuck_docs = (
                            self.db.query(BidDocument)
                            .filter(
                                BidDocument.project_id == project_id,
                                BidDocument.processing_status == 'processing',
                            )
                            .all()
                        )
                    self.logger.info(
                        f'项目 [{project_name}] 强制处理所有processing状态的任务，共 {len(stuck_docs)} 个'
                    )
                else:
                    # 查找处理时间超过30分钟的任务
                    time_threshold = datetime.datetime.now() - datetime.timedelta(
                        minutes=30
                    )

                    stuck_docs = []
                    if self.db is not None:
                        stuck_docs = (
                            self.db.query(BidDocument)
                            .filter(
                                BidDocument.project_id == project_id,
                                BidDocument.processing_status == 'processing',
                            )
                            .all()
                        )
                    
                    # 过滤出超过时间阈值的任务
                    stuck_docs = [
                        doc for doc in stuck_docs
                        if hasattr(doc, 'updated_at') and doc.updated_at and doc.updated_at < time_threshold
                    ]

                count = len(stuck_docs)
                if count == 0:
                    self.logger.info(f'项目 [{project_name}] 没有卡住的分析任务')
                    return 0

                # 更新卡住的任务状态
                for doc in stuck_docs:
                    bidder_name = doc.bidder_name or f'未知投标人_{doc.id}'
                    # 检查是否有分析结果，如果有则标记为completed，否则标记为error
                    from models.database import AnalysisResult
                    has_result = (
                        self.db.query(AnalysisResult)
                        .filter(AnalysisResult.bid_document_id == doc.id)
                        .first()
                    )
                    
                    if has_result:
                        # 如果有分析结果，标记为completed（分析已完成，只是状态更新失败）
                        doc.processing_status = 'completed'
                        doc.progress_current_rule = '分析完成（状态已修复）'
                        # 确保processing_phase也被设置
                        if hasattr(doc, 'processing_phase'):
                            doc.processing_phase = '分析完成'
                        self.logger.warning(
                            f'项目 [{project_name}] 投标人 [{bidder_name}] 分析已完成但状态未更新，'
                            f'将状态从processing更新为completed'
                        )
                    else:
                        # 如果没有分析结果，检查是否在分析过程中（通过processing_phase判断）
                        processing_phase = getattr(doc, 'processing_phase', '')
                        if processing_phase and '完成' in processing_phase:
                            # 如果processing_phase显示已完成，即使没有结果也标记为completed
                            doc.processing_status = 'completed'
                            doc.progress_current_rule = '分析完成（状态已修复，但未找到结果记录）'
                            self.logger.warning(
                                f'项目 [{project_name}] 投标人 [{bidder_name}] 分析阶段显示已完成但无结果记录，'
                                f'将状态从processing更新为completed'
                            )
                        else:
                            # 真正卡住的任务，标记为error
                            doc.processing_status = 'error'
                            doc.progress_current_rule = '分析超时，已强制终止'
                            self.logger.warning(
                                f'项目 [{project_name}] 投标人 [{bidder_name}] 分析卡住，'
                                f'将状态从processing更新为error'
                            )
                    
                    # 确保updated_at字段存在且正确设置
                    if hasattr(doc, 'updated_at'):
                        doc.updated_at = datetime.datetime.now()

                if self.db is not None:
                    self.db.commit()
                self.logger.info(
                    f'项目 [{project_name}] 成功处理了 {count} 个卡住的分析任务'
                )
                return count

            except Exception as e:
                retry_count += 1
                self.logger.error(
                    f'处理卡住的分析任务时出错 (尝试 {retry_count}/{max_retries}): {str(e)}'
                )
                if self.db is not None:
                    self.db.rollback()

                if retry_count >= max_retries:
                    self.logger.error(
                        f'项目 [{project_name}] 处理卡住的分析任务失败，已达到最大重试次数'
                    )
                    return 0

                # 短暂等待后重试
                time.sleep(1)

        # 确保所有代码路径都有返回值
        return 0

    def update_project_status_when_all_completed(
        self, project_id: int, force_complete_stuck: bool = True
    ):
        """
        检查所有分析是否完成，如果完成则更新项目状态

        Args:
            project_id: 项目ID
            force_complete_stuck: 是否强制完成卡住的任务
        """
        from modules.analysis_manager import AnalysisManager

        analysis_manager = AnalysisManager(db_session=self.db)

        # 获取项目信息用于日志记录
        project = None
        if self.db is not None:
            project = (
                self.db.query(TenderProject)
                .filter(TenderProject.id == project_id)
                .first()
            )
        project_name = (
            project.name
            if project and hasattr(project, 'name')
            else f'项目{project_id}'
        )

        # 检查项目当前状态
        if project and project.status == 'completed':
            self.logger.info(f'项目 [{project_name}] 状态已经是completed，无需再次更新')
            return True

        # 检查是否所有分析都已完成
        try:
            completed_count, total_count = (
                analysis_manager._get_analysis_completion_stats(project_id)
            )

            if completed_count == total_count and total_count > 0:
                self.logger.info(
                    f'项目 [{project_name}] 所有任务已完成 ({completed_count}/{total_count})，更新状态为completed'
                )
                # 更新项目状态为completed
                return self.update_project_status(project_id, 'completed')
            elif force_complete_stuck:
                # 如果设置了强制完成，则将所有卡住的任务标记为错误状态
                stuck_count = self.handle_stuck_processes(project_id)
                status = 'completed_with_errors' if stuck_count > 0 else 'completed'
                self.logger.warning(
                    f'项目 [{project_name}] 处理了 {stuck_count} 个卡住的任务，将状态更新为 {status}'
                )
                return self.update_project_status(project_id, status)
        except Exception as e:
            self.logger.error(f'检查项目 [{project_name}] 分析完成状态时出错: {str(e)}')
            # 出错时尝试处理卡住的任务
            if force_complete_stuck:
                stuck_count = self.handle_stuck_processes(project_id)
                if stuck_count > 0:
                    status = 'error'
                    self.logger.warning(
                        f'项目 [{project_name}] 处理了 {stuck_count} 个卡住的任务，将状态更新为 {status}'
                    )
                    return self.update_project_status(project_id, status)

        # 确保变量已定义
        completed_count, total_count = 0, 0
        try:
            completed_count, total_count = (
                analysis_manager._get_analysis_completion_stats(project_id)
            )
        except Exception:
            pass

        self.logger.info(
            f'项目 [{project_name}] 仍有任务未完成 ({completed_count}/{total_count})，不更新状态'
        )
        return False
