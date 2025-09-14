#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
结果展示模块
实现多层表头的表格展示功能
"""

import json
from typing import List, Dict, Any
from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
import logging

logger = logging.getLogger(__name__)


class ResultDisplay:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.session = SessionLocal()
        
    def generate_multi_level_table(self) -> Dict[str, Any]:
        """
        生成多层表头的表格数据
        表头第一行是父项名称及其分值
        表头第二行是子项名称及其分值
        数据区是各投标人的各子项得分
        """
        try:
            # 获取评分规则
            scoring_rules = self.session.query(ScoringRule).filter(
                ScoringRule.project_id == self.project_id
            ).all()
            
            # 获取投标文档
            bid_documents = self.session.query(BidDocument).filter(
                BidDocument.project_id == self.project_id
            ).all()
            
            # 获取分析结果 through BidDocument relationship
            analysis_results = []
            for doc in bid_documents:
                if doc.analysis_result:
                    analysis_results.append(doc.analysis_result)
            
            # 构建评分规则树
            rules_tree = self._build_rules_tree(scoring_rules)
            
            # 构建投标方得分数据
            bidder_scores = self._build_bidder_scores(analysis_results)
            
            # 生成表头和数据
            headers = self._generate_headers(rules_tree)
            data = self._generate_data(bid_documents, bidder_scores, rules_tree)
            
            return {
                'headers': headers,
                'data': data,
                'bidders': [doc.bidder_name for doc in bid_documents]
            }
            
        except Exception as e:
            logger.error(f"生成多层表头表格时出错: {e}")
            raise
        finally:
            self.session.close()
    
    def _build_rules_tree(self, scoring_rules: List[ScoringRule]) -> List[Dict[str, Any]]:
        """
        构建评分规则树结构
        """
        # 按父项分组规则
        parent_groups = {}
        price_rule = None
        
        for rule in scoring_rules:
            if rule.is_price_criteria:
                price_rule = rule
                continue
                
            if rule.Parent_Item_Name and rule.Child_Item_Name:
                if rule.Parent_Item_Name not in parent_groups:
                    parent_groups[rule.Parent_Item_Name] = {
                        'name': rule.Parent_Item_Name,
                        'max_score': rule.Parent_max_score,
                        'children': []
                    }
                parent_groups[rule.Parent_Item_Name]['children'].append({
                    'name': rule.Child_Item_Name,
                    'max_score': rule.Child_max_score,
                    'description': rule.description
                })
        
        # 转换为列表形式
        rules_tree = list(parent_groups.values())
        
        # 如果有价格规则，添加到末尾
        if price_rule:
            rules_tree.append({
                'name': price_rule.Parent_Item_Name or "价格评分",
                'max_score': price_rule.Parent_max_score,
                'children': [{
                    'name': '价格分',
                    'max_score': price_rule.Parent_max_score,
                    'description': price_rule.description
                }]
            })
            
        return rules_tree
    
    def _build_bidder_scores(self, analysis_results: List[AnalysisResult]) -> Dict[str, Dict[str, float]]:
        """
        构建投标方得分数据
        """
        bidder_scores = {}
        
        for result in analysis_results:
            if not result.detailed_scores:
                continue
                
            bidder_name = result.bidder_name
            bidder_scores[bidder_name] = {}
            
            # 解析详细得分
            try:
                if isinstance(result.detailed_scores, str):
                    detailed_scores = json.loads(result.detailed_scores)
                else:
                    detailed_scores = result.detailed_scores
                    
                # 根据新的数据结构处理detailed_scores
                # 每个元素是一个字典，包含：Child_Item_Name、score、reason、Parent_Item_Name
                if isinstance(detailed_scores, list):
                    for score_item in detailed_scores:
                        child_item_name = score_item.get('Child_Item_Name') or score_item.get('criteria_name')
                        score = score_item.get('score', 0)
                        if child_item_name:
                            bidder_scores[bidder_name][child_item_name] = score
            except Exception as e:
                logger.error(f"解析投标方 {bidder_name} 的得分数据时出错: {e}")
                
        return bidder_scores
    
    def _generate_headers(self, rules_tree: List[Dict[str, Any]]) -> List[List[str]]:
        """
        生成多层表头
        第一行：父项名称（合并单元格）
        第二行：子项名称
        """
        header_row1 = ['投标方']  # 第一行表头
        header_row2 = ['投标方']  # 第二行表头
        col_positions = [0]  # 记录每个父项开始的列位置
        current_col = 1
        
        for parent_item in rules_tree:
            children = parent_item['children']
            # 记录这个父项开始的列位置
            col_positions.append(current_col)
            
            # 在第一行添加父项名称
            header_row1.append(f"{parent_item['name']}({parent_item['max_score']}分)")
            
            # 在第二行添加子项名称
            for child_item in children:
                header_row2.append(f"{child_item['name']}({child_item['max_score']}分)")
                current_col += 1
                
        # 添加总分列
        header_row1.append("总分")
        header_row2.append("总分")
        
        return [header_row1, header_row2]
    
    def _generate_data(self, bid_documents: List[BidDocument], 
                      bidder_scores: Dict[str, Dict[str, float]], 
                      rules_tree: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        生成数据行
        """
        data_rows = []
        
        for bid_doc in bid_documents:
            bidder_name = bid_doc.bidder_name
            row = [bidder_name]
            
            # 获取该投标方的得分
            scores = bidder_scores.get(bidder_name, {})
            
            # 按规则树顺序填充数据，只计算子项得分
            total_score = 0
            for parent_item in rules_tree:
                children = parent_item['children']
                for child_item in children:
                    score = scores.get(child_item['name'], 0)
                    row.append(score)
                    total_score += score
            
            # 添加价格分（如果存在）
            price_score = 0
            if bid_doc.analysis_result and bid_doc.analysis_result.price_score is not None:
                price_score = bid_doc.analysis_result.price_score
            elif '价格分' in scores:
                price_score = scores['价格分']
            
            row.append(price_score)
            total_score += price_score
            
            # 添加总分（只计算子项和价格分）
            row.append(round(total_score, 2))
                
            data_rows.append(row)
            
        return data_rows
    
    def get_summary_data(self) -> List[Dict[str, Any]]:
        """
        获取汇总数据，包括各投标方的总分排名
        """
        try:
            # 获取投标文档
            bid_documents = self.session.query(BidDocument).filter(
                BidDocument.project_id == self.project_id
            ).all()
            
            # 构建汇总数据
            summary_data = []
            for bid_doc in bid_documents:
                if bid_doc.analysis_result:
                    summary_data.append({
                        'bidder_name': bid_doc.bidder_name,
                        'total_score': bid_doc.analysis_result.total_score or 0,
                        'price_score': bid_doc.analysis_result.price_score or 0,
                        'extracted_price': bid_doc.analysis_result.extracted_price
                    })
            
            # 按总分排序
            summary_data.sort(key=lambda x: x['total_score'], reverse=True)
            
            # 添加排名
            for i, item in enumerate(summary_data):
                item['rank'] = i + 1
                
            return summary_data
            
        except Exception as e:
            logger.error(f"获取汇总数据时出错: {e}")
            raise
        finally:
            self.session.close()


def print_multi_level_table(project_id: int):
    """
    打印多层表头的表格
    """
    display = ResultDisplay(project_id)
    table_data = display.generate_multi_level_table()
    
    headers = table_data['headers']
    data = table_data['data']
    
    # 计算每列的最大宽度
    col_widths = []
    max_cols = max(len(headers[0]), len(headers[1]))
    
    # 初始化列宽
    for i in range(max_cols):
        col_widths.append(0)
    
    # 计算表头列宽
    for i, header in enumerate(headers[0]):
        col_widths[i] = max(col_widths[i], len(str(header)))
    
    for i, header in enumerate(headers[1]):
        col_widths[i] = max(col_widths[i], len(str(header)))
    
    # 计算数据列宽
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # 打印表头
    for header_row in headers:
        line = ""
        for i, header in enumerate(header_row):
            line += f"{str(header):<{col_widths[i]}} "
        print(line)
        print("-" * (sum(col_widths) + len(col_widths) * 2))
    
    # 打印数据行
    for row in data:
        line = ""
        for i, cell in enumerate(row):
            if isinstance(cell, (int, float)):
                line += f"{cell:<{col_widths[i]}.2f} "
            else:
                line += f"{str(cell):<{col_widths[i]}} "
        print(line)