#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
调试分数计算问题的工具
用于检查数据库中的实际数据格式和分数计算逻辑
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from models.database import SessionLocal, AnalysisResult, ScoringRule, TenderProject
from modules.summary_generator import get_score_for_rule


def debug_project_scores(project_id: int):
    """调试指定项目的分数计算问题"""
    db = SessionLocal()
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            print(f'项目 {project_id} 不存在')
            return

        print(f'=== 调试项目: {project.name} (ID: {project_id}) ===')

        # 获取评分规则
        rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
        print(f'\n评分规则数量: {len(rules)}')

        # 按父项分组显示规则
        parent_groups = {}
        for rule in rules:
            parent_name = rule.Parent_Item_Name or '未分类'
            if parent_name not in parent_groups:
                parent_groups[parent_name] = []
            parent_groups[parent_name].append(rule)

        for parent_name, child_rules in parent_groups.items():
            print(f'\n父项: {parent_name}')
            for rule in child_rules:
                print(
                    f'  - {rule.Child_Item_Name} (满分: {rule.Child_max_score}, 价格项: {rule.is_price_criteria})'
                )

        # 获取分析结果
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )
        print(f'\n分析结果数量: {len(results)}')

        for result in results:
            print(f'\n=== 投标人: {result.bidder_name} ===')
            print(f'总分: {result.total_score}')
            print(f'价格分: {result.price_score}')
            print(f'提取价格: {result.extracted_price}')

            # 检查detailed_scores格式
            detailed_scores = result.detailed_scores
            print(f'detailed_scores类型: {type(detailed_scores)}')

            if detailed_scores:
                if isinstance(detailed_scores, str):
                    try:
                        detailed_scores = json.loads(detailed_scores)
                        print('detailed_scores已从JSON字符串解析')
                    except json.JSONDecodeError as e:
                        print(f'JSON解析失败: {e}')
                        continue

                if isinstance(detailed_scores, list):
                    print(f'detailed_scores包含 {len(detailed_scores)} 个评分项')

                    # 显示每个评分项的详细信息
                    for i, item in enumerate(detailed_scores):
                        if isinstance(item, dict):
                            print(f'  评分项 {i + 1}:')
                            print(
                                f'    名称: {item.get("Child_Item_Name", item.get("criteria_name", item.get("name", "未知")))}'
                            )
                            print(f'    分数: {item.get("score", "无")}')
                            print(
                                f'    是否价格项: {item.get("is_price_criteria", False)}'
                            )
                            if 'children' in item and item['children']:
                                print(f'    子项数量: {len(item["children"])}')
                elif isinstance(detailed_scores, dict):
                    print(
                        f'detailed_scores是字典格式，包含 {len(detailed_scores)} 个键'
                    )
                    print('字典内容:')
                    for key, value in detailed_scores.items():
                        print(f'  {key}: {value}')
                    # 检查是否有detailed_scores键
                    if 'detailed_scores' in detailed_scores:
                        print('发现detailed_scores键，内容:')
                        inner_scores = detailed_scores['detailed_scores']
                        if isinstance(inner_scores, list):
                            for i, item in enumerate(inner_scores):
                                if isinstance(item, dict):
                                    print(
                                        f'    评分项 {i + 1}: {item.get("Child_Item_Name", "未知")} = {item.get("score", "无")}'
                                    )
                        else:
                            print(f'    detailed_scores内容类型: {type(inner_scores)}')
                            print(f'    内容: {inner_scores}')
                else:
                    print(f'detailed_scores不是列表或字典格式: {detailed_scores}')

            # 测试get_score_for_rule函数
            print('\n--- 测试get_score_for_rule函数 ---')
            for rule in rules:
                if not rule.is_price_criteria:  # 只测试非价格项
                    score = get_score_for_rule(
                        result.detailed_scores, rule.Child_Item_Name
                    )
                    print(f'  {rule.Child_Item_Name}: {score}')

    finally:
        db.close()


def debug_all_projects():
    """调试所有项目的分数计算问题"""
    db = SessionLocal()
    try:
        projects = db.query(TenderProject).all()
        print(f'找到 {len(projects)} 个项目')

        for project in projects:
            print(f'\n{"=" * 50}')
            debug_project_scores(project.id)

    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            project_id = int(sys.argv[1])
            debug_project_scores(project_id)
        except ValueError:
            print('项目ID必须是整数')
    else:
        debug_all_projects()
