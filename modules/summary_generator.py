#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-09-11 18:18:34
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-09-14 19:59:11
#文件相对于项目的路径   : /AI_env2/modules/summary_generator.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
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
    """为项目生成具有单行表头的动态汇总表数据"""
    
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
        child_items.append({
            'parent_name': rule.Parent_Item_Name or "未知",
            'name': rule.Child_Item_Name,
            'max_score': rule.Child_max_score or 0
        })

    # 2. 构建单行表头 (只包含Child_Item_Name)
    # 按照父项名称分组
    scoring_items = {}
    for item in child_items:
        parent_name = item['parent_name']
        if parent_name not in scoring_items:
            scoring_items[parent_name] = []
        scoring_items[parent_name].append({
            'name': item['name'],
            'max_score': item['max_score']
        })

    # 3. 获取项目的所有分析结果
    results = db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).order_by(AnalysisResult.total_score.desc()).all()
    if not results:
        return {'error': '该项目没有找到分析结果。'}

    # 4. 构建表格行数据
    rows_data = []
    rank = 1
    for result in results:
        detailed_scores = json.loads(result.detailed_scores) if isinstance(result.detailed_scores, str) else result.detailed_scores
        
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
            'total_score': round(total_score, 2)
        }
        rows_data.append(bidder_row)
        rank += 1
        
    # 5. 组合最终结果
    final_summary = {
        'scoring_items': scoring_items,
        'rows': rows_data
    }
    
    return final_summary
