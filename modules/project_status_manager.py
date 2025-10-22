#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-22 21:16:49
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-22 21:16:51
# 文件相对于项目的路径   : \AI_ENV2\modules\project_status_manager.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
项目状态管理器模块
统一处理项目状态更新逻辑，避免在多个地方重复实现相似的功能
"""

import logging
import datetime
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

    def update_project_status_when_all_completed(self, project_id: int):
        """
        当所有分析任务都完成时更新项目状态

        Args:
            project_id: 项目ID
        """
        try:
            self.logger.info(f'检查项目 {project_id} 是否所有任务都已完成')

            if not self.db:
                self.logger.error('数据库会话未提供')
                return False

            # 检查是否所有分析都已完成（这里可以调用AnalysisManager中的检查方法）
            from modules.analysis_manager import AnalysisManager

            analysis_manager = AnalysisManager(db_session=self.db)

            if not analysis_manager._check_all_analysis_completed(project_id):
                self.logger.info(f'项目 {project_id} 还有未完成的分析任务')
                return False

            # 更新项目状态为completed
            return self.update_project_status(project_id, 'completed')

        except Exception as e:
            self.logger.error(f'更新项目状态时出错: {e}')
            return False
