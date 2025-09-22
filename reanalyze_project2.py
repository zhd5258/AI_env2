#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重新分析项目2
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, AnalysisResult
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer


def reanalyze_project2():
    """
    重新分析项目2
    """
    print('重新分析项目2')
    print('=' * 60)

    try:
        session = SessionLocal()

        # 检查项目2
        project = session.query(TenderProject).filter(TenderProject.id == 2).first()
        if not project:
            print('错误：项目2不存在')
            return

        print('项目信息:')
        print(f'  ID: {project.id}')
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 检查投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 2).all()
        print(f'\n投标文档数量: {len(bid_docs)}')

        # 重新分析每个投标文档
        for doc in bid_docs:
            print(f'\n重新分析投标文档 {doc.id}: {doc.bidder_name}')
            print(f'  文件路径: {doc.file_path}')

            if not os.path.exists(doc.file_path):
                print(f'  错误：文件不存在 {doc.file_path}')
                continue

            try:
                # 创建分析器
                analyzer = IntelligentBidAnalyzer(
                    tender_file_path=project.tender_file_path,
                    bid_file_path=doc.file_path,
                    db_session=session,
                    bid_document_id=doc.id,
                    project_id=project.id,
                )

                # 执行分析
                result = analyzer.analyze_bidding_document()
                print(f'  分析结果: {result}')

            except Exception as e:
                print(f'  分析过程中出错: {e}')
                import traceback

                traceback.print_exc()

        session.close()

    except Exception as e:
        print(f'重新分析过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    reanalyze_project2()
