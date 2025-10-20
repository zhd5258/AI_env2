#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
修复分数计算问题的工具
重新计算所有项目的分数，确保汇总表显示正确
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
from modules.price_score_calculator import PriceScoreCalculator


def fix_project_scores(project_id: int):
    """修复指定项目的分数计算问题"""
    db = SessionLocal()
    try:
        # 获取项目信息
        project = db.query(TenderProject).filter(TenderProject.id == project_id).first()
        if not project:
            print(f'项目 {project_id} 不存在')
            return False

        print(f'=== 修复项目: {project.name} (ID: {project_id}) ===')

        # 获取分析结果
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )
        if not results:
            print('没有找到分析结果')
            return False

        print(f'找到 {len(results)} 个分析结果')

        # 重新计算价格分
        print('\n--- 重新计算价格分 ---')
        price_calculator = PriceScoreCalculator(db_session=db)
        price_success = price_calculator.calculate_project_price_scores(project_id)

        if price_success:
            print('价格分计算成功')
        else:
            print('价格分计算失败')

        # 重新计算总分
        print('\n--- 重新计算总分 ---')
        for result in results:
            try:
                # 重新获取更新后的结果
                db.refresh(result)

                # 计算其他分数总和
                detailed_scores_list = []
                if isinstance(result.detailed_scores, str):
                    try:
                        detailed_scores_list = json.loads(result.detailed_scores)
                    except json.JSONDecodeError:
                        print(
                            f'解析投标人 {result.bidder_name} 的 detailed_scores 失败'
                        )
                        continue
                elif isinstance(result.detailed_scores, list):
                    detailed_scores_list = result.detailed_scores

                # 计算除价格分外的其他分数总和
                other_scores_total = price_calculator._calculate_other_scores_total(
                    detailed_scores_list
                )

                # 更新总分
                new_total_score = other_scores_total + (result.price_score or 0)
                old_total_score = result.total_score or 0

                result.total_score = round(new_total_score, 2)

                print(
                    f'  {result.bidder_name}: 总分 {old_total_score} -> {new_total_score} (其他分: {other_scores_total}, 价格分: {result.price_score})'
                )

            except Exception as e:
                print(f'修复投标人 {result.bidder_name} 的分数时出错: {e}')
                continue

        # 提交更改
        db.commit()
        print('\n分数修复完成')
        return True

    except Exception as e:
        print(f'修复项目 {project_id} 时出错: {e}')
        db.rollback()
        return False
    finally:
        db.close()


def fix_all_projects():
    """修复所有项目的分数计算问题"""
    db = SessionLocal()
    try:
        projects = db.query(TenderProject).all()
        print(f'找到 {len(projects)} 个项目')

        success_count = 0
        for project in projects:
            print(f'\n{"=" * 50}')
            if fix_project_scores(project.id):
                success_count += 1

        print(f'\n修复完成: {success_count}/{len(projects)} 个项目成功')

    finally:
        db.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        try:
            project_id = int(sys.argv[1])
            fix_project_scores(project_id)
        except ValueError:
            print('项目ID必须是整数')
    else:
        fix_all_projects()
