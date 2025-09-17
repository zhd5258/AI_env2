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
    for item in detailed_scores:
        # 支持两种格式：旧格式使用criteria_name，新格式使用Child_Item_Name
        criteria_name = item.get('Child_Item_Name') or item.get('criteria_name')
        if criteria_name == rule_name:
            return item.get('score')
    return None


def generate_summary_data(project_id: int, db: Session):
    """为项目生成动态汇总表数据

    返回结构同时兼容历史页前端（history.js）预期：
    - header_rows: 二维表头数组（第一行为父项合并单元格，加上“排名/投标人”的两列 rowSpan=2；第二行为子项名称列）
    - rows: 数据行
    - scoring_items: 按父项分组的子项定义（向后兼容）
    """

    # 1. 获取项目的所有评分规则
    rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
    if not rules:
        return {'error': '该项目没有找到评分规则。'}
    # 直接处理所有评分规则，不再构建复杂的父子项关系树
    # 只需要Child_Item_Name不为空的规则作为表头
    child_items = []
    for rule in rules:
        # 跳过价格评分规则和没有子项名称的规则
        if rule.is_price_criteria or not rule.Child_Item_Name:
            continue
        child_items.append(
            {
                'parent_name': rule.Parent_Item_Name or '未知',
                'name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score or 0,
            }
        )

    # 2. 构建单行表头 (只包含Child_Item_Name)
    # 按照父项名称分组
    scoring_items = {}
    for item in child_items:
        parent_name = item['parent_name']
        if parent_name not in scoring_items:
            scoring_items[parent_name] = []
        scoring_items[parent_name].append(
            {'name': item['name'], 'max_score': item['max_score']}
        )

    # 3. 获取项目的所有分析结果
    results = (
        db.query(AnalysisResult)
        .filter(AnalysisResult.project_id == project_id)
        .order_by(AnalysisResult.total_score.desc())
        .all()
    )
    if not results:
        return {'error': '该项目没有找到分析结果。'}

    # 4. 构建表格行数据
    rows_data = []
    rank = 1
    for result in results:
        detailed_scores = (
            json.loads(result.detailed_scores)
            if isinstance(result.detailed_scores, str)
            else result.detailed_scores
        )

        scores = []
        # 只计算子项得分
        for item in child_items:
            score = get_score_for_rule(detailed_scores, item['name'])
            scores.append(score)

        # 计算总分：只包括子项得分和价格分
        total_score = sum(s for s in scores if s is not None)
        if result.price_score is not None:
            total_score += result.price_score

        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': scores,
            'price_score': result.price_score,
            'total_score': round(total_score, 2),
        }
        rows_data.append(bidder_row)
        rank += 1

    # 5. 生成前端期望的 header_rows 结构（两行表头）
    # 第一行：固定列 + 父项合并单元格
    header_top = []
    # 固定列：排名、投标人
    header_top.append({'name': '排名', 'rowspan': 2})
    header_top.append({'name': '投标人', 'rowspan': 2})

    # 记录父项与其子项顺序（确保与 child_items 顺序一致）
    parent_to_children = {}
    parent_order = []
    for item in child_items:
        p = item['parent_name']
        if p not in parent_to_children:
            parent_to_children[p] = []
            parent_order.append(p)
        parent_to_children[p].append(
            {'name': item['name'], 'max_score': item['max_score']}
        )

    for parent_name in parent_order:
        children = parent_to_children.get(parent_name, [])
        if children:
            header_top.append({'name': parent_name, 'colspan': len(children)})

    # 追加价格分与总分（与数据列对齐）
    header_top.append({'name': '价格分', 'rowspan': 2})
    header_top.append({'name': '总分', 'rowspan': 2})

    # 第二行：所有子项（按父项顺序展开）
    header_bottom = []
    for parent_name in parent_order:
        for child in parent_to_children.get(parent_name, []):
            header_bottom.append(
                {'name': child['name'], 'max_score': child['max_score']}
            )

    header_rows = [header_top, header_bottom]

    # 6. 组合最终结果
    final_summary = {
        'header_rows': header_rows,
        'rows': rows_data,
        'scoring_items': scoring_items,
    }

    return final_summary
