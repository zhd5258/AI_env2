#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
模拟AI分析过程，测试修改后的智能分析功能
"""

import sys
import os
import json
import re

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule
from modules.scoring_extractor.core import IntelligentScoringExtractor
from modules.scoring_extractor.db_handler import DBHandlerMixin
from modules.pdf_processor import PDFProcessor
from modules.price_manager import PriceManager
import logging

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestDBHandler(DBHandlerMixin):
    def __init__(self):
        self.logger = logger

def mock_ai_analysis(rule, context):
    """
    模拟AI分析过程
    """
    # 模拟AI返回的JSON格式结果
    mock_response = {
        "score": rule.Child_max_score * 0.8,  # 模拟得分为满分的80%
        "reason": f"根据投标文件内容分析，{rule.Child_Item_Name}条款满足度较好，给予{rule.Child_max_score * 0.8}分。"
    }
    return json.dumps(mock_response)

def parse_ai_score_response(response, max_score):
    """
    解析AI评分响应（从intelligent_bid_analyzer.py复制）
    """
    try:
        # 使用正则表达式从响应中提取JSON块，这能抵抗额外的解释性文本
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
        if not json_match:
            json_match = re.search(r'(\{.*?\})', response, re.DOTALL)

        if json_match:
            json_str = json_match.group(1)
            result = json.loads(json_str)
            score = result.get('score', 0)
            reason = result.get('reason', '未提供理由。')

            if not isinstance(score, (int, float)):
                score = 0
            score = max(0, min(float(score), float(max_score)))
            return score, reason
        else:
            # 如果无法找到JSON，作为备用方案，尝试从文本中提取分数
            score_match = re.search(r'(\d+(?:\.\d+)?)\s*分', response)
            if score_match:
                score = float(score_match.group(1))
                score = max(0, min(score, max_score))
                return score, f'无法解析JSON，但从文本中提取到分数。原始响应: {response[:200]}...'
            
            return 0, f'无法从AI响应中解析出有效的JSON或分数。响应: {response[:200]}...'

    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"解析AI响应时出错: {e}\n响应内容: {response}")
        return 0, f'解析AI响应失败。错误: {e}'

def find_relevant_context_for_child_rule(rule, pages, context_window=2):
    """
    为子项规则查找相关上下文（从intelligent_bid_analyzer.py简化）
    """
    keywords = set(re.split(r'\s|，|。', rule.Child_Item_Name + ' ' + (rule.description or '')))
    keywords = {k for k in keywords if k and len(k) > 1}
    relevant_pages_indices = set()
    for i, page_text in enumerate(pages):
        if any(keyword.lower() in page_text.lower() for keyword in keywords):
            for j in range(i, min(i + context_window + 1, len(pages))):
                relevant_pages_indices.add(j)
    if not relevant_pages_indices:
        return '\n'.join(pages[:3])
    sorted_indices = sorted(list(relevant_pages_indices))
    grouped_pages = []
    if not sorted_indices: return ''
    start = end = sorted_indices[0]
    for i in range(1, len(sorted_indices)):
        if sorted_indices[i] == end + 1:
            end = sorted_indices[i]
        else:
            grouped_pages.append((start, end))
            start = end = sorted_indices[i]
    grouped_pages.append((start, end))
    context_parts = [f'--- Pages {s+1}-{e+1} ---\n' + '\n'.join(pages[s:e+1]) for s, e in grouped_pages]
    return '\n\n'.join(context_parts)

def calculate_price_score(price_rule, best_price, project_prices):
    """
    计算价格分（从intelligent_bid_analyzer.py简化）
    """
    if not project_prices or best_price is None:
        return {
            'criteria_name': price_rule.Parent_Item_Name,
            'max_score': price_rule.Parent_max_score,
            'score': 0,
            'reason': f'根据价格评分规则计算得出。未能提取到有效报价。',
            'is_price_criteria': True,
            'extracted_price': best_price
        }
    
    # 找到最低价格作为评标基准价
    min_price = min(project_prices.values())
    
    # 价格分满分
    price_max_score = price_rule.Parent_max_score
    
    # 计算当前投标人的价格分
    if best_price == min_price:
        # 最低报价得满分
        current_bidder_score = price_max_score
    else:
        # 按照评标规则公式计算：投标报价得分＝（评标基准价/投标报价）*满分
        current_bidder_score = (min_price / best_price) * price_max_score
        current_bidder_score = round(current_bidder_score, 2)
    
    return {
        'criteria_name': price_rule.Parent_Item_Name,
        'max_score': price_rule.Parent_max_score,
        'score': current_bidder_score,
        'reason': f'根据价格评分规则计算得出。提取到的报价为: {best_price}，评标基准价为: {min_price}',
        'is_price_criteria': True,
        'extracted_price': best_price
    }

def test_mock_analysis():
    """
    测试模拟AI分析过程
    """
    tender_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\招标文件正文.pdf"
    bid_file_path = r"D:\user\设备管理\招标评标资料\2025\旧油漆线改造\集装箱\广东创智智能装备有限公司投标文件.pdf"
    
    if not os.path.exists(tender_file_path):
        print(f"错误：找不到招标文件 {tender_file_path}")
        return
        
    if not os.path.exists(bid_file_path):
        print(f"错误：找不到投标文件 {bid_file_path}")
        return
    
    print("开始测试模拟AI分析过程")
    print("=" * 80)
    
    try:
        # 1. 创建测试项目和投标文档
        session = SessionLocal()
        
        # 检查是否已存在测试项目
        existing_project = session.query(TenderProject).filter(TenderProject.project_code == "ZB2025-003").first()
        if existing_project:
            project_id = existing_project.id
            print(f"使用现有测试项目，项目ID: {project_id}")
        else:
            # 创建测试项目
            project = TenderProject(
                name="旧油漆线改造项目测试",
                project_code="ZB2025-003",  # 使用不同的项目代码
                tender_file_path=tender_file_path
            )
            session.add(project)
            session.commit()
            session.refresh(project)
            project_id = project.id
            
            print(f"创建测试项目，项目ID: {project_id}")
        
        # 检查是否已存在测试投标文档
        existing_bid_doc = session.query(BidDocument).filter(
            BidDocument.project_id == project_id,
            BidDocument.bidder_name == "广东创智智能装备有限公司"
        ).first()
        
        if existing_bid_doc:
            bid_document_id = existing_bid_doc.id
            print(f"使用现有测试投标文档，文档ID: {bid_document_id}")
        else:
            # 创建测试投标文档
            bid_doc = BidDocument(
                project_id=project_id,
                bidder_name="广东创智智能装备有限公司",
                file_path=bid_file_path
            )
            session.add(bid_doc)
            session.commit()
            session.refresh(bid_doc)
            bid_document_id = bid_doc.id
            
            print(f"创建测试投标文档，文档ID: {bid_document_id}")
        
        # 2. 提取并保存评分规则（如果尚未保存）
        scoring_rules_count = session.query(ScoringRule).filter(ScoringRule.project_id == project_id).count()
        if scoring_rules_count == 0:
            print("\n2. 提取评分规则...")
            extractor = IntelligentScoringExtractor()
            rules = extractor.extract(tender_file_path)
            
            if rules:
                print(f"   成功提取到 {len(rules)} 条评分规则")
                
                # 保存到数据库
                handler = TestDBHandler()
                success = handler.save_scoring_rules_to_db(project_id, rules)
                
                if success:
                    print("   ✓ 评分规则成功保存到数据库")
                else:
                    print("   ✗ 评分规则保存到数据库失败")
            else:
                print("   ✗ 未能提取到评分规则")
        else:
            print(f"\n2. 评分规则已存在，共 {scoring_rules_count} 条")
            
        # 3. 模拟执行智能分析 - 首先分析子项规则
        print("\n3. 模拟执行智能分析...")
        
        # 获取所有子项规则（非价格规则且有Child_Item_Name的规则）
        child_rules = session.query(ScoringRule).filter(
            ScoringRule.project_id == project_id,
            ScoringRule.is_price_criteria.is_(False),
            ScoringRule.Child_Item_Name.isnot(None)
        ).all()
        
        print(f"   子项规则数: {len(child_rules)}")
        
        # 提取投标文件内容
        print("\n4. 提取投标文件内容...")
        bid_processor = PDFProcessor(bid_file_path)
        bid_pages = bid_processor.process_pdf_per_page()
        
        if not bid_pages or not any(bid_pages):
            print("   ✗ 从投标文件中提取有效文本失败")
            session.close()
            return
        else:
            print("   ✓ 成功提取投标文件内容")
        
        # 提取价格
        print("\n5. 提取投标价格...")
        price_manager = PriceManager()
        prices = price_manager.extract_prices_from_content(bid_pages)
        best_price = price_manager.select_best_price(prices, bid_pages)
        print(f"   ✓ 提取到的价格: {best_price}")
        
        # 分析每个子项规则
        print("\n6. 分析子项规则...")
        analyzed_scores = []
        for i, rule in enumerate(child_rules):
            print(f"   分析规则 {i+1}/{len(child_rules)}: {rule.Child_Item_Name}")
            
            # 查找相关上下文
            relevant_context = find_relevant_context_for_child_rule(rule, bid_pages)
            
            # 模拟AI分析
            mock_response = mock_ai_analysis(rule, relevant_context)
            score, reason = parse_ai_score_response(mock_response, rule.Child_max_score)
            
            # 保存分析结果
            analyzed_rule = {
                'criteria_name': rule.Child_Item_Name,
                'max_score': rule.Child_max_score,
                'score': score,
                'reason': reason,
                'parent_name': rule.Parent_Item_Name
            }
            analyzed_scores.append(analyzed_rule)
            
            print(f"     得分: {score}/{rule.Child_max_score}")
        
        # 7. 计算价格分
        print("\n7. 计算价格分...")
        price_rule = session.query(ScoringRule).filter(
            ScoringRule.project_id == project_id,
            ScoringRule.is_price_criteria.is_(True)
        ).first()
        
        if price_rule:
            # 模拟项目中所有投标文件的价格（这里只模拟几个）
            project_prices = {
                "广东创智智能装备有限公司": best_price if best_price is not None else 1000000,
                "其他公司A": (best_price * 1.1) if best_price is not None else 1100000,  # 比当前报价高10%
                "其他公司B": (best_price * 0.95) if best_price is not None else 950000  # 比当前报价低5%
            }
            
            # 过滤掉None值
            project_prices = {k: v for k, v in project_prices.items() if v is not None}
            
            price_score_result = calculate_price_score(price_rule, best_price, project_prices)
            analyzed_scores.append(price_score_result)
            
            print(f"   价格分: {price_score_result['score']}/{price_score_result['max_score']}")
            print(f"   价格分计算理由: {price_score_result['reason']}")
        else:
            print("   未找到价格规则")
        
        # 8. 计算总分
        print("\n8. 计算总分...")
        total_score = sum(item.get('score', 0) for item in analyzed_scores)
        print(f"   总分: {total_score}")
        
        # 9. 显示详细评分
        print("\n9. 详细评分结果:")
        for score_item in analyzed_scores:
            print(f"   - {score_item['criteria_name']}: {score_item['score']}/{score_item['max_score']}")
            print(f"     理由: {score_item['reason']}")
        
        # 10. 保存分析结果到数据库
        print("\n10. 保存分析结果到数据库...")
        bid_doc = session.query(BidDocument).filter(BidDocument.id == bid_document_id).first()
        bid_doc.total_score = total_score
        bid_doc.detailed_scores = analyzed_scores
        bid_doc.extracted_price = best_price
        session.commit()
        
        print("   ✓ 分析结果已保存到数据库")
            
        session.close()
        
        print("\n" + "=" * 80)
        print("模拟AI分析测试完成!")
        
    except Exception as e:
        print(f"测试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        
        # 关闭数据库会话
        try:
            session.close()
        except:
            pass

if __name__ == "__main__":
    test_mock_analysis()