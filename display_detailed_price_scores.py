#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
显示详细的价格分计算结果
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument

def display_detailed_price_scores():
    """
    显示详细的价格分计算结果
    """
    print("显示详细的价格分计算结果")
    print("=" * 60)
    
    try:
        session = SessionLocal()
        
        # 检查项目6
        project = session.query(TenderProject).filter(TenderProject.id == 6).first()
        if not project:
            print("错误：项目6不存在")
            return
            
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  状态: {project.status}")
        
        # 收集所有投标人的价格
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        prices = {}
        for doc in bid_docs:
            if doc.analysis_result and doc.analysis_result.extracted_price is not None:
                prices[doc.bidder_name] = doc.analysis_result.extracted_price
        
        print(f"\n所有投标人的报价:")
        sorted_prices = sorted(prices.items(), key=lambda x: x[1])
        for bidder, price in sorted_prices:
            print(f"  {bidder}: {price:,.2f}")
        
        # 找出最低价
        if prices:
            min_price = min(prices.values())
            min_bidder = [bidder for bidder, price in prices.items() if price == min_price][0]
            print(f"\n最低报价: {min_bidder} - {min_price:,.2f}")
            
            # 显示价格分计算详情
            print(f"\n价格分计算详情:")
            for bidder, price in sorted_prices:
                if price == min_price:
                    score = 40.0  # 满分
                    print(f"  {bidder}: 报价 {price:,.2f} (最低价) -> 价格分: {score}/40.0")
                else:
                    # 按公式计算: (最低价/当前价)*40
                    score = (min_price / price) * 40
                    print(f"  {bidder}: 报价 {price:,.2f} -> 价格分: {score:.2f}/40.0")
        
        # 显示最终结果
        print(f"\n最终结果:")
        for doc in bid_docs:
            if doc.analysis_result:
                print(f"  {doc.bidder_name}:")
                print(f"    总分: {doc.analysis_result.total_score}")
                print(f"    提取价格: {doc.analysis_result.extracted_price:,.2f}")
                print(f"    价格分: {doc.analysis_result.price_score}")
        
        session.close()
        print(f"\n显示完成!")
        
    except Exception as e:
        print(f"显示过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    display_detailed_price_scores()