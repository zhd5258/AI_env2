#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试价格分计算和存储过程
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, AnalysisResult, ScoringRule
from modules.price_score_calculator import PriceScoreCalculator
import logging

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

def test_price_update():
    """
    测试价格分计算和存储过程
    """
    print("开始测试价格分计算和存储过程...")
    
    # 创建价格分计算器
    calculator = PriceScoreCalculator()
    
    # 测试项目ID为4（根据日志中的信息）
    project_id = 4
    
    print(f"开始为项目 {project_id} 计算价格分...")
    
    # 调用价格分计算方法
    result = calculator.calculate_project_price_scores(project_id)
    
    print(f"价格分计算结果: {result}")
    
    # 检查数据库中的更新结果
    print("检查数据库中的更新结果...")
    db = SessionLocal()
    try:
        results = db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).all()
        print(f"项目 {project_id} 的分析结果:")
        for r in results:
            print(f'  投标人: {r.bidder_name}, 价格分: {r.price_score}, 总分: {r.total_score}')
    except Exception as e:
        print(f"查询数据库时出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_price_update()