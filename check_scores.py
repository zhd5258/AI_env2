#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查数据库中AnalysisResult表的价格分和总分数据
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, AnalysisResult
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_scores():
    """
    检查数据库中的价格分和总分数据
    """
    print("开始检查数据库中的价格分和总分数据...")
    
    db = SessionLocal()
    try:
        print("正在查询AnalysisResult表...")
        results = db.query(AnalysisResult).all()
        print(f"查询到 {len(results)} 条记录")
        
        if not results:
            print("数据库中没有AnalysisResult记录")
            return
            
        print("=" * 80)
        print("数据库中AnalysisResult表的价格分和总分数据:")
        print("=" * 80)
        print(f'{"投标人":>30} | {"价格分":>6} | {"总分":>6}')
        print("-" * 80)
        for r in results:
            bidder_name = r.bidder_name if r.bidder_name else "N/A"
            price_score = r.price_score if r.price_score is not None else "None"
            total_score = r.total_score if r.total_score is not None else "None"
            print(f'{bidder_name:>30} | {price_score:>6} | {total_score:>6}')
        print("=" * 80)
        
    except Exception as e:
        print(f"查询数据库时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        print("数据库连接已关闭")

if __name__ == "__main__":
    check_scores()