#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
全流程测试脚本
自动测试从项目创建到分析完成的整个流程
"""

import sys
import os
import json
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from models.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.correct_scoring_extractor import CorrectScoringExtractor
from modules.analysis_manager import AnalysisManager
from modules.price_calculation_workflow import PriceCalculationWorkflow
from modules.summary_generator import generate_summary_data


def test_full_workflow():
    """测试完整的工作流程"""
    print('=== 开始全流程测试 ===')

    db = SessionLocal()
    try:
        # 1. 创建测试项目
        print('\n1. 创建测试项目...')
        import datetime

        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        project = TenderProject(
            project_code=f'TEST-{timestamp}',
            name='全流程测试项目',
            description='自动测试全流程',
            tender_file_path='uploads/招标文件.pdf',
            scoring_rules_summary={},
            status='new',
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        project_id = project.id
        print(f'项目创建成功，ID: {project_id}')

        # 2. 提取评分规则
        print('\n2. 提取评分规则...')
        extractor = CorrectScoringExtractor('uploads/招标文件.pdf')
        rules_data = extractor.extract_scoring_rules()
        print(f'提取到 {len(rules_data)} 条评分规则')

        # 保存评分规则到数据库
        for rule_data in rules_data:
            rule = ScoringRule(
                project_id=project_id,
                Parent_Item_Name=rule_data.get('Parent_Item_Name'),
                Parent_max_score=rule_data.get('Parent_max_score'),
                Child_Item_Name=rule_data.get('Child_Item_Name'),
                Child_max_score=rule_data.get('Child_max_score'),
                description=rule_data.get('description'),
                is_veto=rule_data.get('is_veto', False),
                is_price_criteria=rule_data.get('is_price_criteria', False),
                price_formula=rule_data.get('price_formula'),
                is_qualitative=rule_data.get('is_qualitative', False),
                is_quantitative=rule_data.get('is_quantitative', False),
            )
            db.add(rule)
        db.commit()
        print('评分规则已保存到数据库')

        # 3. 上传投标文件
        print('\n3. 上传投标文件...')
        bid_files = [
            'uploads/昆明苏净工贸有限公司出口项目投标文件.pdf',
            'uploads/盐城大德涂装环保设备有限公司出口项目投标文件.pdf',
        ]

        bid_documents = []
        for bid_file in bid_files:
            if os.path.exists(bid_file):
                bidder_name = Path(bid_file).stem.replace('出口项目投标文件', '')
                bid_doc = BidDocument(
                    project_id=project_id,
                    bidder_name=bidder_name,
                    file_path=bid_file,
                    original_filename=Path(bid_file).name,
                    processing_status='pending',
                )
                db.add(bid_doc)
                bid_documents.append(bid_doc)
                print(f'添加投标文件: {bidder_name}')

        db.commit()
        for doc in bid_documents:
            db.refresh(doc)
        print(f'上传了 {len(bid_documents)} 个投标文件')

        # 4. 开始分析
        print('\n4. 开始分析...')
        analysis_manager = AnalysisManager(db_session=db)
        success = analysis_manager.initialize_project_analysis(project_id)
        if success:
            print('分析初始化成功')

            # 启动分析任务
            print('启动分析任务...')
            for bid_doc in bid_documents:
                try:
                    analysis_manager.analysis_task(
                        project_id=project_id,
                        bid_document_id=bid_doc.id,
                        tender_file_path='uploads/招标文件.pdf',
                        bid_file_path=bid_doc.file_path,
                    )
                    print(f'已启动投标人 {bid_doc.bidder_name} 的分析任务')
                except Exception as e:
                    print(f'启动投标人 {bid_doc.bidder_name} 分析任务失败: {e}')
        else:
            print('分析初始化失败')
            return False

        # 等待分析完成
        print('\n5. 等待分析完成...')
        max_wait_time = 300  # 5分钟
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            # 检查分析状态
            results = (
                db.query(AnalysisResult)
                .filter(AnalysisResult.project_id == project_id)
                .all()
            )
            if len(results) == len(bid_documents):
                # 检查是否所有分析都完成
                all_completed = True
                for result in results:
                    if not result.detailed_scores:
                        all_completed = False
                        break

                if all_completed:
                    print('分析完成！')
                    break

            print(f'等待中... 已分析 {len(results)}/{len(bid_documents)} 个投标人')
            time.sleep(10)

        # 6. 运行价格计算工作流
        print('\n6. 运行价格计算工作流...')
        price_workflow = PriceCalculationWorkflow(db_session=db)
        price_success = price_workflow.execute_workflow(project_id)
        if price_success:
            print('价格计算完成')
        else:
            print('价格计算失败')

        # 7. 生成汇总数据
        print('\n7. 生成汇总数据...')
        summary_data = generate_summary_data(project_id, db)
        if 'error' not in summary_data:
            print('汇总数据生成成功')
            print(f'汇总表包含 {len(summary_data.get("rows", []))} 行数据')

            # 显示汇总结果
            for row in summary_data.get('rows', []):
                bidder_name = row.get('bidder_name', '未知')
                total_score = row.get('total_score', 0)
                price_score = row.get('price_score', 0)
                scores = row.get('scores', [])
                other_scores = sum(scores) - price_score if scores else 0

                print(
                    f'  {bidder_name}: 总分={total_score}, 价格分={price_score}, 其他分={other_scores}'
                )
        else:
            print(f'汇总数据生成失败: {summary_data["error"]}')

        # 8. 验证结果
        print('\n8. 验证结果...')
        results = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.project_id == project_id)
            .all()
        )
        for result in results:
            print(f'投标人: {result.bidder_name}')
            print(f'  总分: {result.total_score}')
            print(f'  价格分: {result.price_score}')
            print(f'  提取价格: {result.extracted_price}')
            print(f'  detailed_scores类型: {type(result.detailed_scores)}')

            if result.detailed_scores:
                if isinstance(result.detailed_scores, dict):
                    if 'detailed_scores' in result.detailed_scores:
                        inner_scores = result.detailed_scores['detailed_scores']
                        if isinstance(inner_scores, list):
                            print(f'  评分项数量: {len(inner_scores)}')
                            for item in inner_scores[:3]:  # 显示前3个
                                if isinstance(item, dict):
                                    name = item.get('Child_Item_Name', '未知')
                                    score = item.get('score', 0)
                                    print(f'    {name}: {score}')

        print('\n=== 全流程测试完成 ===')
        return True

    except Exception as e:
        print(f'测试过程中出错: {e}')
        import traceback

        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == '__main__':
    success = test_full_workflow()
    if success:
        print('测试成功完成！')
    else:
        print('测试失败！')
