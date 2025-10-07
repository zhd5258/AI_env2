#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-11 18:18:34
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-14 19:59:11
# 文件相对于项目的路径   : /AI_env2/modules/summary_generator.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import json
from sqlalchemy.orm import Session
from modules.database import AnalysisResult, ScoringRule


def get_score_for_rule(detailed_scores, rule_name):
    """从详细评分中查找特定规则的分数"""
    if not detailed_scores:
        return None

    # 确保detailed_scores是列表格式
    if isinstance(detailed_scores, str):
        try:
            detailed_scores = json.loads(detailed_scores)
        except json.JSONDecodeError:
            return None

    # 确保detailed_scores是列表
    if not isinstance(detailed_scores, list):
        return None

    for item in detailed_scores:
        # 确保item是字典格式
        if not isinstance(item, dict):
            continue

        # 支持两种格式：旧格式使用criteria_name，新格式使用Child_Item_Name
        criteria_name = item.get('Child_Item_Name') or item.get('criteria_name')
        if criteria_name == rule_name:
            return item.get('score')
    return None


def generate_summary_data(project_id: int, db: Session):
    """为项目生成动态汇总表数据

    返回结构同时兼容历史页前端（history.js）预期：
    - header_rows: 二维表头数组（第一行为父项合并单元格，加上"排名/投标人"的两列 rowSpan=2；第二行为子项名称列）
    - rows: 数据行
    - scoring_items: 按父项分组的子项定义（向后兼容）
    """

    # 1. 获取项目的所有评分规则
    rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
    if not rules:
        return {'error': '该项目没有找到评分规则。'}

    # 2. 处理评分规则，构建父子项关系树
    # 首先收集所有父项
    parent_items = {}
    child_items = []

    for rule in rules:
        # 跳过价格评分规则（这些规则会在最后单独处理）
        if getattr(rule, 'is_price_criteria', False):
            continue

        # 如果是父项（有Parent_Item_Name但没有Child_Item_Name）
        parent_name_attr = getattr(rule, 'Parent_Item_Name', None)
        child_name_attr = getattr(rule, 'Child_Item_Name', None)

        if parent_name_attr is not None and child_name_attr is None:
            parent_name = str(parent_name_attr) if parent_name_attr else '未知'
            parent_items[parent_name] = {
                'name': parent_name,
                'max_score': rule.Parent_max_score or 0,
                'children': [],
            }
        # 如果是子项（有Child_Item_Name）
        elif child_name_attr is not None:
            parent_name = str(parent_name_attr) if parent_name_attr else '未知'
            child_items.append(
                {
                    'parent_name': parent_name,
                    'name': str(child_name_attr),
                    'max_score': rule.Child_max_score or 0,
                }
            )

    # 将子项分配给对应的父项
    for child in child_items:
        parent_name = child['parent_name']
        if parent_name in parent_items:
            parent_items[parent_name]['children'].append(child)
        else:
            # 如果父项不存在，创建一个虚拟父项
            parent_items[parent_name] = {
                'name': parent_name,
                'max_score': 0,
                'children': [child],
            }

    # 按照父项在数据库中的出现顺序排序
    ordered_parents = []
    for rule in rules:
        parent_name_attr = getattr(rule, 'Parent_Item_Name', None)
        child_name_attr = getattr(rule, 'Child_Item_Name', None)

        parent_name = None
        if parent_name_attr is not None and child_name_attr is None:
            parent_name = str(parent_name_attr)
        elif child_name_attr is not None and parent_name_attr is not None:
            parent_name = str(parent_name_attr)

        if parent_name and len(parent_name) > 0:
            if (
                parent_name not in [p['name'] for p in ordered_parents]
                and parent_name in parent_items
            ):
                ordered_parents.append(parent_items[parent_name])

    # 确保所有父项都被包含
    for parent_name, parent_data in parent_items.items():
        if parent_name not in [p['name'] for p in ordered_parents]:
            ordered_parents.append(parent_data)

    # 3. 构建单行表头 (只包含Child_Item_Name)
    # 按照父项名称分组
    scoring_items = {}
    for parent in ordered_parents:
        parent_name = parent['name']
        scoring_items[parent_name] = parent['children']

    # 4. 获取项目的所有分析结果
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.total_score.desc())
        .all()
    )
    if not results:
        return {'error': '该项目没有找到分析结果。'}

    # 5. 构建表格行数据
    rows_data = []
    rank = 1
    for result in results:
        # 直接使用存储的detailed_scores，避免重复解析
        detailed_scores = result.detailed_scores

        scores = []
        # 按照父项和子项的顺序收集分数
        for parent in ordered_parents:
            for child in parent['children']:
                score = get_score_for_rule(detailed_scores, child['name'])
                scores.append(score)

        # 直接使用数据库中存储的总分，避免重复计算
        # 总分已经包含了子项得分和价格分
        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': scores,
            'price_score': result.price_score,
            'total_score': round(float(getattr(result, 'total_score', 0) or 0), 2),
        }
        rows_data.append(bidder_row)
        rank += 1

    # 6. 生成前端期望的 header_rows 结构（两行表头）
    # 第一行：固定列 + 父项合并单元格
    header_top = []
    # 固定列：排名、投标人
    header_top.append({'name': '排名', 'rowspan': 2})
    header_top.append({'name': '投标人', 'rowspan': 2})

    # 按顺序添加父项（带有colspan）
    for parent in ordered_parents:
        children_count = len(parent['children'])
        if children_count > 0:
            header_top.append({'name': parent['name'], 'colspan': children_count})

    # 追加价格分与总分（与数据列对齐）
    header_top.append({'name': '价格分', 'rowspan': 2})
    header_top.append({'name': '总分', 'rowspan': 2})

    # 第二行：所有子项（按父项顺序展开）
    header_bottom = []
    for parent in ordered_parents:
        for child in parent['children']:
            header_bottom.append({'name': child['name']})

    header_rows = [header_top, header_bottom]

    # 7. 组合最终结果
    final_summary = {
        'header_rows': header_rows,
        'rows': rows_data,
        'scoring_items': scoring_items,
    }

    # 同时生成兼容旧格式的summary数据
    summary_data = []
    for result in results:
        summary_data.append(
            {
                'bidder_name': result.bidder_name,
                'total_score': result.total_score,
                'price_score': result.price_score,
                'rank': next(
                    (
                        row['rank']
                        for row in rows_data
                        if row['bidder_name'] == result.bidder_name
                    ),
                    0,
                ),
            }
        )

    final_summary['summary'] = summary_data

    return final_summary
