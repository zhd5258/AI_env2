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
import logging
from sqlalchemy.orm import Session
from models.database import AnalysisResult, ScoringRule


def get_score_for_rule(detailed_scores, rule_name):
    """从详细评分中查找特定规则的分数"""
    # 处理空的详细评分
    if not detailed_scores or detailed_scores is None:
        return None

    # 确保detailed_scores是列表格式
    if isinstance(detailed_scores, str):
        try:
            detailed_scores = json.loads(detailed_scores)
        except json.JSONDecodeError:
            return None
    elif isinstance(detailed_scores, dict):
        # 如果是字典格式，尝试获取其中的列表
        if 'detailed_scores' in detailed_scores:
            detailed_scores = detailed_scores['detailed_scores']
        else:
            # 如果是简单的字典格式，直接使用
            return detailed_scores.get(rule_name)

    # 确保detailed_scores是列表
    if not isinstance(detailed_scores, list):
        return None

    for item in detailed_scores:
        # 确保item是字典格式
        if not isinstance(item, dict):
            continue

        # 支持多种格式：Child_Item_Name, criteria_name, name
        criteria_name = (
            item.get('Child_Item_Name') or item.get('criteria_name') or item.get('name')
        )

        # 精确匹配规则名称
        if criteria_name == rule_name:
            score = item.get('score')
            # 确保返回的是数字类型
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    return 0.0
            return 0.0

        # 递归搜索子项
        if 'children' in item and isinstance(item['children'], list):
            child_score = get_score_for_rule(item['children'], rule_name)
            if child_score is not None:
                return child_score

    return None


def _find_actual_score_in_detailed_scores(detailed_scores, rule_name):
    """
    在详细评分中查找实际分数，支持模糊匹配

    Args:
        detailed_scores: 详细评分数据
        rule_name: 规则名称

    Returns:
        float or None: 找到的分数，如果未找到则返回None
    """
    if not detailed_scores or not isinstance(detailed_scores, list):
        return None

    for item in detailed_scores:
        if not isinstance(item, dict):
            continue

        # 支持多种字段名
        criteria_name = (
            item.get('Child_Item_Name')
            or item.get('criteria_name')
            or item.get('name', '')
        )

        # 模糊匹配：检查规则名称是否包含在criteria_name中，或相反
        if (
            criteria_name
            and rule_name
            and (rule_name in criteria_name or criteria_name in rule_name)
        ):
            score = item.get('score')
            if score is not None:
                try:
                    return float(score)
                except (ValueError, TypeError):
                    continue

        # 递归搜索子项
        if 'children' in item and isinstance(item['children'], list):
            child_score = _find_actual_score_in_detailed_scores(
                item['children'], rule_name
            )
            if child_score is not None:
                return child_score

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
    # 首先收集所有父项和子项
    parent_items = {}
    child_items = []
    price_rules = []
    qualitative_rules = []  # 定性规则列表

    for rule in rules:
        # 分离价格评分规则
        if getattr(rule, 'is_price_criteria', False):
            price_rules.append(rule)
            continue

        # 分离定性规则
        if getattr(rule, 'is_qualitative', False):
            qualitative_rules.append(rule)
            continue

        # 修复：正确识别父项和子项
        parent_name_attr = getattr(rule, 'Parent_Item_Name', None)
        child_name_attr = getattr(rule, 'Child_Item_Name', None)

        # 如果是父项（有Parent_Item_Name但Child_Item_Name为空）
        if (
            parent_name_attr is not None
            and parent_name_attr.strip()
            and (child_name_attr is None or not child_name_attr.strip())
        ):
            parent_name = str(parent_name_attr).strip()
            parent_items[parent_name] = {
                'name': parent_name,
                'max_score': rule.Parent_max_score or 0,
                'children': [],
            }
        # 如果是子项（Parent_Item_Name和Child_Item_Name都不为空）
        elif (
            parent_name_attr is not None
            and parent_name_attr.strip()
            and child_name_attr is not None
            and child_name_attr.strip()
        ):
            parent_name = str(parent_name_attr).strip()
            child_items.append(
                {
                    'parent_name': parent_name,
                    'name': str(child_name_attr).strip(),
                    'max_score': rule.Child_max_score or 0,
                }
            )
        # 如果是独立项（没有Parent_Item_Name但有Child_Item_Name）
        elif (
            (parent_name_attr is None or not parent_name_attr.strip())
            and child_name_attr is not None
            and child_name_attr.strip()
        ):
            child_items.append(
                {
                    'parent_name': '其他',  # 为独立项创建一个默认父项
                    'name': str(child_name_attr).strip(),
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
                'max_score': sum(
                    c['max_score']
                    for c in child_items
                    if c['parent_name'] == parent_name
                ),
                'children': [c for c in child_items if c['parent_name'] == parent_name],
            }

    # 按照父项在数据库中的出现顺序排序
    ordered_parents = []
    for rule in rules:
        parent_name_attr = getattr(rule, 'Parent_Item_Name', None)
        child_name_attr = getattr(rule, 'Child_Item_Name', None)

        parent_name = None
        # 父项记录
        if (
            parent_name_attr is not None
            and parent_name_attr.strip()
            and (child_name_attr is None or not child_name_attr.strip())
        ):
            parent_name = str(parent_name_attr).strip()
        # 子项记录
        elif (
            parent_name_attr is not None
            and parent_name_attr.strip()
            and child_name_attr is not None
            and child_name_attr.strip()
        ):
            parent_name = str(parent_name_attr).strip()

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
        # 按照父项和子项的顺序收集分数（只收集定量规则的分数）
        for parent in ordered_parents:
            for child in parent['children']:
                score = get_score_for_rule(detailed_scores, child['name'])
                # 如果分数为None，尝试使用0作为默认值
                if score is None:
                    # 检查是否是价格分
                    is_price_score = any(
                        price_rule.Child_Item_Name == child['name']
                        for price_rule in price_rules
                    )
                    # 如果是价格分且AnalysisResult中有price_score，则使用price_score
                    if is_price_score and hasattr(result, 'price_score'):
                        score = result.price_score
                    else:
                        # 修复：对于非价格分项，尝试从detailed_scores中查找实际分数
                        # 而不是直接设置为0
                        score = _find_actual_score_in_detailed_scores(
                            detailed_scores, child['name']
                        )
                        if score is None:
                            score = 0
                scores.append(score)

        # 重新计算总分，确保总分是所有子项得分之和（包括价格分）
        # 总分应该是所有子项得分之和，不超过100分
        calculated_total_score = sum(
            score
            for score in scores
            if score is not None and isinstance(score, (int, float))
        )

        # 添加价格分到总分计算中
        if result.price_score is not None:
            calculated_total_score += result.price_score

        # 确保总分不超过100分
        calculated_total_score = min(calculated_total_score, 100.0)

        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': scores,
            'price_score': result.price_score,
            'total_score': round(float(calculated_total_score), 2),
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

    # 处理价格规则
    price_header_added = False
    for price_rule in price_rules:
        if hasattr(price_rule, 'Child_Item_Name') and price_rule.Child_Item_Name:
            price_name = str(price_rule.Child_Item_Name).strip()
            if not price_header_added and price_name:
                header_top.append({'name': price_name, 'rowspan': 2})
                price_header_added = True
                break

    # 如果没有找到有效的价格规则名称，使用默认名称
    if not price_header_added:
        header_top.append({'name': '价格分', 'rowspan': 2})

    # 追加总分
    header_top.append({'name': '总分', 'rowspan': 2})

    # 第二行：所有子项（按父项顺序展开）
    header_bottom = []
    for parent in ordered_parents:
        for child in parent['children']:
            # 确保子项名称不为空
            child_name = (
                child.get('name', '') if isinstance(child, dict) else str(child)
            )
            if not child_name:
                child_name = '未知子项'
            header_bottom.append({'name': child_name})

    header_rows = [header_top, header_bottom]

    # 7. 组合最终结果
    final_summary = {
        'header_rows': header_rows,
        'rows': rows_data,
        'scoring_items': scoring_items,
        # 添加定性规则信息
        'qualitative_rules': [
            {
                'id': rule.id,
                'Child_Item_Name': rule.Child_Item_Name,
                'description': rule.description,
                'is_veto': rule.is_veto,
            }
            for rule in qualitative_rules
        ],
        # 添加定性规则分析结果
        'qualitative_analysis_results': {},
    }

    # 同时生成兼容旧格式的summary数据
    summary_data = []
    for result in results:
        # 找到对应的bidder_row以获取重新计算的总分
        calculated_total_score = 0
        for row in rows_data:
            if row['bidder_name'] == result.bidder_name:
                calculated_total_score = row['total_score']
                break

        summary_data.append(
            {
                'bidder_name': result.bidder_name,
                'total_score': calculated_total_score,  # 使用重新计算的总分
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

    # 为每个分析结果添加定性规则分析结果
    for result in results:
        # 获取定性规则分析结果
        qualitative_results = getattr(result, 'qualitative_analysis_results', {})
        final_summary['qualitative_analysis_results'][result.bidder_name] = (
            qualitative_results
        )

    return final_summary
