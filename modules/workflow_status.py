#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-10-08 09:05:01
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-10-08 09:08:17
# 文件相对于项目的路径   : \AI_ENV2\modules\workflow_status.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
工作流状态标记模块
定义各种任务和流程的状态标记
"""

from enum import Enum


class WorkflowStatus(Enum):
    """工作流状态枚举"""

    NOT_STARTED = 'NotStarts'
    IN_PROGRESS = 'InProgress'
    COMPLETED = 'completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'
    TIMEOUT = 'Timeout'


class AnalysisTaskStatus(Enum):
    """分析任务状态枚举"""

    NOT_STARTED = 'NotStarts'
    IN_PROGRESS = 'InProgress'
    COMPLETED = 'completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'
    TIMEOUT = 'Timeout'


class PriceCalculationStatus(Enum):
    """价格计算状态枚举"""

    NOT_STARTED = 'NotStarts'
    IN_PROGRESS = 'InProgress'
    COMPLETED = 'completed'
    CANCELLED = 'Cancelled'
    FAILED = 'Failed'
    TIMEOUT = 'Timeout'
