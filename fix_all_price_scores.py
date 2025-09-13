#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
重新计算并修复所有投标文档的价格分
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.price_manager import PriceManager

def fix_all_price_scores():
    """
    重新计算并修复所有投标文档的价格分
    """
    print("重新计算并修复所有投标文档的价格分")
    print("=" * 50)
    
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
        
        # 获取价格规则
        price_rule = session.query(ScoringRule).filter(
            ScoringRule.project_id == 6,
            ScoringRule.is_price_criteria == True
        ).first()
        
        if not price_rule:
            print("错误：未找到价格规则")
            return
            
        print(f"\n价格规则:")
        print(f"  名称: {price_rule.Parent_Item_Name}")
        print(f"  分数: {price_rule.Parent_max_score}")
        print(f"  描述: {price_rule.description}")
        
        # 收集所有投标人的价格
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        project_prices = {}
        
        for doc in bid_docs:
            if doc.analysis_result and doc.analysis_result.extracted_price is not None:
                project_prices[doc.bidder_name] = doc.analysis_result.extracted_price
                print(f"  {doc.bidder_name}: {doc.analysis_result.extracted_price}")
        
        if not project_prices:
            print("错误：未收集到任何投标人的价格")
            return
            
        # 计算价格分
        print(f"\n计算价格分:")
        price_manager = PriceManager()
        price_scores = price_manager.calculate_project_price_scores(project_prices, [price_rule])
        
        print(f"价格分计算结果:")
        for bidder, score in price_scores.items():
            print(f"  {bidder}: {score}")
        
        # 更新每个投标人的分析结果
        print(f"\n更新分析结果:")
        for doc in bid_docs:
            analysis_result = doc.analysis_result
            if analysis_result:
                # 更新价格分
                price_score = price_scores.get(doc.bidder_name, 0)
                analysis_result.price_score = price_score
                print(f"  {doc.bidder_name} 的价格分更新为: {price_score}")
                
                # 更新详细评分中的价格评分项
                if analysis_result.detailed_scores:
                    try:
                        scores = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                        
                        # 查找并更新价格评分项
                        for score_item in scores:
                            if score_item.get('is_price_criteria', False):
                                score_item['score'] = price_score
                                print(f"    详细评分中的价格项更新为: {price_score}")
                                break
                        
                        # 保存更新后的详细评分
                        analysis_result.detailed_scores = json.dumps(scores, ensure_ascii=False)
                    except Exception as e:
                        print(f"    更新详细评分时出错: {e}")
                
                # 重新计算总分（所有评分项的分数之和）
                try:
                    scores = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                    total_score = sum(item.get('score', 0) for item in scores)
                    analysis_result.total_score = total_score
                    print(f"    总分更新为: {total_score}")
                except Exception as e:
                    print(f"    重新计算总分时出错: {e}")
        
        # 提交所有更改
        session.commit()
        print(f"\n所有价格分更新完成!")
        
        session.close()
        
    except Exception as e:
        print(f"处理过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    fix_all_price_scores()