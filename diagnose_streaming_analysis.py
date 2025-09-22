#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:21:16
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:21:18
# 文件相对于项目的路径   : \AI_env2\diagnose_streaming_analysis.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-09-22 22:07:27
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-22 22:07:30
# 文件相对于项目的路径   : \AI_env2\diagnose_streaming_analysis.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
诊断流式分析问题
"""

import sys
import os
import json
import logging

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import (
    SessionLocal,
    TenderProject,
    BidDocument,
    AnalysisResult,
    ScoringRule,
)
from modules.pdf_processor import PDFProcessor
from modules.intelligent_bid_analyzer import IntelligentBidAnalyzer


def diagnose_streaming_analysis():
    """
    诊断流式分析问题
    """
    print('诊断流式分析问题')
    print('=' * 60)

    # 设置日志级别
    logging.basicConfig(level=logging.INFO)

    try:
        session = SessionLocal()

        # 检查项目2（有评分规则但没有投标文档）
        project = session.query(TenderProject).filter(TenderProject.id == 2).first()
        if not project:
            print('错误：项目2不存在')
            return

        print('项目信息:')
        print(f'  ID: {project.id}')
        print(f'  名称: {project.name}')
        print(f'  项目代码: {project.project_code}')
        print(f'  状态: {project.status}')
        print(f'  招标文件: {project.tender_file_path}')

        # 检查评分规则
        scoring_rules = (
            session.query(ScoringRule).filter(ScoringRule.project_id == 2).all()
        )
        print(f'\n评分规则数量: {len(scoring_rules)}')

        if not scoring_rules:
            print('错误：项目2没有评分规则')
            return

        # 检查项目1（有投标文档但没有评分规则）
        project1 = session.query(TenderProject).filter(TenderProject.id == 1).first()
        if not project1:
            print('错误：项目1不存在')
            return

        print('\n项目1信息:')
        print(f'  ID: {project1.id}')
        print(f'  名称: {project1.name}')
        print(f'  状态: {project1.status}')

        # 检查项目1的投标文档
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 1).all()
        print(f'\n项目1投标文档数量: {len(bid_docs)}')

        if not bid_docs:
            print('错误：项目1没有投标文档')
            return

        # 选择第一个投标文档进行测试
        bid_doc = bid_docs[0]
        print('\n测试投标文档:')
        print(f'  文档ID: {bid_doc.id}')
        print(f'  投标方: {bid_doc.bidder_name}')
        print(f'  文件路径: {bid_doc.file_path}')
        print(f'  处理状态: {bid_doc.processing_status}')
        print(f'  错误信息: {bid_doc.error_message}')

        # 检查文件是否存在
        if not os.path.exists(bid_doc.file_path):
            print(f'错误：投标文件不存在 {bid_doc.file_path}')
            return

        print('\n开始测试流式PDF处理...')

        # 测试PDF处理器的流式处理
        processor = PDFProcessor(bid_doc.file_path, file_type='bid')

        # 设置流式处理回调
        def stream_callback(processed_pages: int, pages_text: list):
            print(f'  流式处理回调：已处理 {processed_pages} 页')
            if pages_text:
                print(
                    f'    最后一页文本长度: {len(pages_text[-1]) if pages_text else 0}'
                )

        processor.set_stream_callback(stream_callback)

        # 执行流式处理
        pages_text = processor.stream_process_pdf(chunk_size=3)
        print(f'\n流式处理完成，共处理 {len(pages_text)} 页')

        # 显示前几页的内容
        for i, page_text in enumerate(pages_text[:3]):
            print(f'  第{i + 1}页文本长度: {len(page_text)}')
            if page_text:
                print(f'    前100字符: {page_text[:100]}')

        print('\n开始测试智能分析器...')

        # 测试智能分析器
        analyzer = IntelligentBidAnalyzer(
            project.tender_file_path,  # 使用项目2的招标文件（有评分规则）
            bid_doc.file_path,
            db_session=session,
            bid_document_id=bid_doc.id,
            project_id=2,  # 使用项目2的ID（有评分规则）
            extracted_text=pages_text,
        )

        # 执行分析
        analysis_result = analyzer.analyze_bidding_document()
        print(f'\n分析结果: {analysis_result}')

        if analysis_result['status'] == 'success':
            print('分析成功完成')
            if 'details' in analysis_result:
                details = analysis_result['details']
                print(f'  投标人名称: {details.get("投标人名称", "未提取")}')
                print(f'  投标总价: {details.get("投标总价", "未提取")}')
                print(f'  评分结果数量: {len(details.get("评分结果", []))}')
        else:
            print(f'分析失败: {analysis_result["message"]}')

        session.close()

    except Exception as e:
        print(f'诊断过程中出错: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    diagnose_streaming_analysis()
