#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查项目4的投标文档数据
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, BidDocument

def check_project_data():
    """
    检查项目4的投标文档数据
    """
    print("检查项目4的投标文档数据...")
    
    db = SessionLocal()
    try:
        docs = db.query(BidDocument).filter(BidDocument.project_id == 4).all()
        print(f'项目4的投标文档数量: {len(docs)}')
        for doc in docs:
            print(f'  投标人: {doc.bidder_name}, 文档ID: {doc.id}')
            if doc.analysis_result:
                print(f'    分析结果ID: {doc.analysis_result.id}, 价格分: {doc.analysis_result.price_score}, 总分: {doc.analysis_result.total_score}')
            else:
                print('    无分析结果')
    except Exception as e:
        print(f"查询过程中出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    check_project_data()