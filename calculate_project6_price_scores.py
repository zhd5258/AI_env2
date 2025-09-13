#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
手动计算项目6的价格分
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
from modules.price_manager import PriceManager

def calculate_project6_price_scores():
    """
    手动计算项目6的价格分
    """
    print("手动计算项目6的价格分")
    print("=" * 50)
    
    try:
        session = SessionLocal()
        
        # 检查项目6是否存在
        project = session.query(TenderProject).filter(TenderProject.id == 6).first()
        if not project:
            print("错误：项目6不存在")
            return
            
        print(f"项目信息:")
        print(f"  ID: {project.id}")
        print(f"  名称: {project.name}")
        print(f"  项目代码: {project.project_code}")
        print(f"  状态: {project.status}")
        
        # 检查评分规则
        scoring_rules = session.query(ScoringRule).filter(ScoringRule.project_id == 6).all()
        print(f"\n评分规则数量: {len(scoring_rules)}")
        price_rules = [r for r in scoring_rules if r.is_price_criteria]
        print(f"  价格规则数量: {len(price_rules)}")
        
        if not price_rules:
            print("错误：未找到价格规则")
            return
            
        price_rule = price_rules[0]
        print(f"  价格规则:")
        print(f"    父项名称: {price_rule.Parent_Item_Name}")
        print(f"    父项分数: {price_rule.Parent_max_score}")
        print(f"    描述: {price_rule.description}")
        
        # 检查投标文档和分析结果
        bid_docs = session.query(BidDocument).filter(BidDocument.project_id == 6).all()
        print(f"\n投标文档数量: {len(bid_docs)}")
        
        # 收集所有投标人的价格
        project_prices = {}
        for doc in bid_docs:
            print(f"  投标方: {doc.bidder_name}")
            analysis_result = doc.analysis_result
            if analysis_result and analysis_result.extracted_price is not None:
                project_prices[doc.bidder_name] = analysis_result.extracted_price
                print(f"    提取价格: {analysis_result.extracted_price}")
            else:
                print(f"    无提取价格")
        
        print(f"\n收集到的价格: {project_prices}")
        
        if not project_prices:
            print("警告：未收集到任何投标人的价格")
            # 使用我们在诊断脚本中提取的价格
            project_prices = {
                "武汉新国铁博达科技有限公司": 2876875.0,
                "扬州琼花涂装工程技术有限公司": 2270000.0,
                "江西中霖环境科技集团有限公司": 23.0
            }
            print(f"使用诊断脚本中提取的价格: {project_prices}")
        
        # 计算价格分
        print(f"\n计算价格分:")
        price_manager = PriceManager()
        price_scores = price_manager.calculate_project_price_scores(project_prices, [price_rule])
        
        print(f"价格分计算结果: {price_scores}")
        
        # 更新分析结果中的价格分
        print(f"\n更新分析结果:")
        for doc in bid_docs:
            analysis_result = doc.analysis_result
            if analysis_result:
                price_score = price_scores.get(doc.bidder_name, 0)
                print(f"  投标方 {doc.bidder_name} 的价格分: {price_score}")
                
                # 查找价格评分项并更新
                if analysis_result.detailed_scores:
                    try:
                        scores = json.loads(analysis_result.detailed_scores) if isinstance(analysis_result.detailed_scores, str) else analysis_result.detailed_scores
                        
                        # 查找价格评分项并更新
                        for score_item in scores:
                            if score_item.get('is_price_criteria', False):
                                score_item['score'] = price_score
                                print(f"    更新价格评分项: {score_item}")
                                break
                        else:
                            # 如果没有找到价格评分项，则添加一个
                            price_score_item = {
                                'criteria_name': price_rule.Parent_Item_Name,
                                'max_score': price_rule.Parent_max_score,
                                'score': price_score,
                                'reason': f'根据价格评分规则计算得出。评标基准价为: {min(project_prices.values()) if project_prices else "N/A"}',
                                'is_price_criteria': True
                            }
                            scores.append(price_score_item)
                            print(f"    添加价格评分项: {price_score_item}")
                        
                        # 重新计算总分
                        total_score = sum(item.get('score', 0) for item in scores)
                        analysis_result.total_score = total_score
                        print(f"    更新总分: {total_score}")
                        
                        # 保存更新
                        analysis_result.detailed_scores = json.dumps(scores, ensure_ascii=False)
                        session.commit()
                        print(f"    分析结果更新成功")
                        
                    except Exception as e:
                        print(f"    更新分析结果时出错: {e}")
            else:
                print(f"  投标方 {doc.bidder_name} 无分析结果")
        
        session.close()
        print(f"\n价格分计算完成!")
        
    except Exception as e:
        print(f"计算过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    calculate_project6_price_scores()