#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:07:27
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:07:30
# 文件相对于项目的路径   : \AI_env2\diagnose_full_issue.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
全面诊断AI_env2项目的问题
包括价格分析失败和流式分析无结果的问题
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.price_manager import PriceManager
from modules.pdf_processor import PDFProcessor


def diagnose_full_issue():
    """
    全面诊断问题
    """
    print('全面诊断AI_env2项目问题')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查项目6
        project = session.query(TenderProject).filter(TenderProject.id == 6).first()
        if not project:
            print('错误：项目6不存在')
            return

        print('项目信息:')
        print(f'  ID: {project.id}')
        print(f'  名称: {project.name}')
        print(f'  项目代码: {project.project_code}')
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 检查评分规则
        scoring_rules = (
            session.query(ScoringRule).filter(ScoringRule.project_id == 6).all()
        )
        print(f'\n评分规则数量: {len(scoring_rules)}')
        price_rules = [r for r in scoring_rules if r.is_price_criteria]
        print(f'  价格规则数量: {len(price_rules)}')
        for rule in price_rules:
            print(f'    规则ID: {rule.id}')
            print(f'      父项名称: {rule.Parent_Item_Name}')
            print(f'      父项分数: {rule.Parent_max_score}')
            print(f'      描述: {rule.description}')
            print(f'      公式: {rule.price_formula}')

        # 检查投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        print(f'\n投标文档数量: {len(bid_docs)}')
        for doc in bid_docs:
            print(f'  文档ID: {doc.id}')
            print(f'    投标方: {doc.bidder_name}')
            print(f'    文件路径: {doc.file_path}')
            print(f'    处理状态: {doc.processing_status}')

            # 检查分析结果
            analysis_result = doc.analysis_result
            if analysis_result:
                print(f'    分析结果ID: {analysis_result.id}')
                print(f'      总分: {analysis_result.total_score}')
                print(f'      价格分: {analysis_result.price_score}')
                print(f'      提取价格: {analysis_result.extracted_price}')
                if analysis_result.detailed_scores:
                    try:
                        scores = (
                            json.loads(analysis_result.detailed_scores)
                            if isinstance(analysis_result.detailed_scores, str)
                            else analysis_result.detailed_scores
                        )
                        price_scores = [
                            s for s in scores if s.get('is_price_criteria', False)
                        ]
                        print(f'      价格评分项数: {len(price_scores)}')
                        for ps in price_scores:
                            print(f'        价格评分项: {ps}')
                    except Exception as e:
                        print(f'      解析详细得分时出错: {e}')
            else:
                print('    无分析结果')

        # 尝试重新提取价格
        print('\n尝试重新提取价格:')
        price_manager = PriceManager()
        for doc in bid_docs:
            if not os.path.exists(doc.file_path):
                print(f'  错误：投标文件不存在 {doc.file_path}')
                continue

            print(f'  处理投标方: {doc.bidder_name}')
            processor = PDFProcessor(doc.file_path, file_type='bid')
            pages = processor.extract_text_with_ocr_when_needed()
            print(f'    提取到 {len(pages)} 页文本')

            if pages and any(pages):
                prices = price_manager.extract_prices_from_content(pages)
                print(f'    提取到 {len(prices)} 个价格')
                for i, price_info in enumerate(prices[:5]):  # 显示前5个
                    print(
                        f'      价格 {i + 1}: {price_info["value"]} (置信度: {price_info["confidence"]})'
                    )

                best_price = price_manager.select_best_price(prices, pages)
                print(f'    最佳价格: {best_price}')
            else:
                print('    未能提取到文本内容')

        session.close()

    except Exception as e:
        print(f'诊断过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    diagnose_full_issue()
