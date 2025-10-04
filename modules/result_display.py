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
        构建评分规则树结构，确保正确处理Child_Item_Name字段
        """
        parent_groups = {}
        price_rules = []
        
        # 分组处理评分规则
        for rule in scoring_rules:
            # 收集价格评分规则
            if getattr(rule, 'is_price_criteria', False):
                price_rules.append(rule)
                continue
                
            # 获取Child_Item_Name，确保非空
            child_item_name = getattr(rule, 'Child_Item_Name', None)
            if not child_item_name:
                continue
                
            # 获取Parent_Item_Name
            Parent_Item_Name = getattr(rule, 'Parent_Item_Name', None)
            if not Parent_Item_Name:
                continue
                
            # 初始化父项组
            if Parent_Item_Name not in parent_groups:
                parent_groups[Parent_Item_Name] = {
                    'name': Parent_Item_Name,
                    'max_score': 0,
                    'children': []
                }
            
            # 获取子项分数和描述
            child_max_score = getattr(rule, 'Child_max_score', 0) or 0
            description = getattr(rule, 'description', '')
            
            # 添加子项
            child_item = {
                'name': child_item_name,
                'max_score': float(child_max_score),
                'description': description
            }
            parent_groups[Parent_Item_Name]['children'].append(child_item)
            
            # 累计父项满分（所有子项满分之和）
            parent_groups[Parent_Item_Name]['max_score'] += float(child_max_score)
        
        # 转换为列表形式
        rules_tree = list(parent_groups.values())
        
        # 处理价格评分规则
        for rule in price_rules:
            rules_tree.append({
                'name': getattr(rule, 'Parent_Item_Name', None) or "价格评分",
                'max_score': float(getattr(rule, 'Parent_max_score', 0) or 0),
                'children': [{
                    'name': '价格分',
                    'max_score': float(getattr(rule, 'Parent_max_score', 0) or 0),
                    'description': getattr(rule, 'description', '')
                }],
                'is_price_criteria': True  # 添加这个属性以正确识别价格评分规则
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
    
    def _generate_headers(self, rules_tree: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        生成双行表头（分级表头）
        第一行：排名、投标方、各Parent_Item_Name（合并单元格）、价格分、总分
        第二行：各Child_Item_Name、价格分、总分
        返回结构：
        [
            [{'name': '排名', 'rowspan': 2}, {'name': '投标人', 'rowspan': 2}, 
             {'name': '技术方案(60分)', 'colspan': 2}, 
             {'name': '价格分(40分)', 'rowspan': 2}, 
             {'name': '总分(100)', 'rowspan': 2}],
            ['', '', 
             {'name': '技术方案完整性(30分)'}, 
             {'name': '技术方案可行性(30分)'}, 
             '', '']
        ]
        """
        # 获取价格分满分值
        price_parent_name = '价格分'  # 默认名称
        for parent_item in rules_tree:
            if parent_item.get('is_price_criteria', False):
                # 使用价格评分规则的父项名称，但只取名称部分，不包含分值
                price_parent_name = parent_item['name']
                # 从父项名称中移除分值信息，使用字符串分割
                if '（' in price_parent_name:
                    price_parent_name = price_parent_name.split('（')[0].strip()
                if not price_parent_name:
                    price_parent_name = '价格分'  # 如果移除后为空，使用默认名称
                # 如果名称中包含"价格"，确保最终名称是"价格分"
                if '价格' in price_parent_name and '分' not in price_parent_name:
                    price_parent_name = '价格分'
                break
        
        # 第一行表头
        header_row1 = [
            {'name': '排名', 'rowspan': 2},
            {'name': '投标人', 'rowspan': 2}
        ]
        
        # 第二行表头
        header_row2 = ['', '']  # 对应固定列的占位符
        
        # 根据规则树生成分级表头
        for parent_item in rules_tree:
            # 跳过价格评分项，因为价格分会在最后由前端单独处理
            if parent_item.get('is_price_criteria', False):
                continue
                
            children = parent_item['children']
            if children:
                # 有子项的父项 - 在第一行添加父项名称并合并单元格
                parent_name = parent_item['name']
                # 只显示父项名称，不显示分值
                parent_header = parent_name
                
                # 分离价格分项和其他子项
                non_price_children = [child for child in children if child.get('name') != '价格分']
                
                if non_price_children:
                    # 如果有非价格分的子项，在第一行添加父项并设置colspan
                    header_row1.append({'name': parent_header, 'colspan': len(non_price_children)})
                    
                    # 在第二行添加对应的子项
                    for child_item in non_price_children:
                        # 只显示子项名称，不添加分值（因为名称中已经包含了分值）
                        child_header = child_item['name']
                        header_row2.append({'name': child_header})
                else:
                    # 如果没有非价格分的子项，在第一行添加父项并设置rowspan
                    header_row1.append({'name': parent_header, 'rowspan': 2})
                    # 第二行不需要添加占位符，因为父项跨越两行
        
        # 添加价格分和总分列（价格分需要跨越两行）
        header_row1.append({'name': price_parent_name, 'rowspan': 2})
        header_row1.append({'name': '总分', 'rowspan': 2})
        header_row2.append('')  # 价格分在第二行不需要子项
        header_row2.append('')  # 总分在第二行不需要子项
        
        return [header_row1, header_row2]  # 返回双行表头结构
    
    def _generate_data(self, bid_documents: List[BidDocument], 
                      bidder_scores: Dict[str, Dict[str, float]], 
                      rules_tree: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        生成数据行
        包含排名、投标方名称、各Child_Item_Name对应的得分、价格分、总分
        """
        data_rows = []
        
        # 创建投标文档和分析结果的映射
        bid_doc_map = {doc.bidder_name: doc for doc in bid_documents}
        
        # 获取所有投标方的总分用于排序
        bidder_scores_with_total = []
        for doc in bid_documents:
            # 确保分析结果存在且属于当前项目
            if (doc.analysis_result and 
                doc.analysis_result.project_id == self.project_id):
                total_score = doc.analysis_result.total_score or 0
                bidder_scores_with_total.append((doc.bidder_name, total_score))
        
        # 按总分排序
        bidder_scores_with_total.sort(key=lambda x: x[1], reverse=True)
        
        # 生成排序后的数据行
        for rank, (bidder_name, total_score) in enumerate(bidder_scores_with_total, 1):
            row = [rank, bidder_name]  # 添加排名和投标方名称
            
            # 获取该投标方的得分
            scores = bidder_scores.get(bidder_name, {})
            # 确保bid_doc存在且分析结果属于当前项目
            bid_doc = None
            for doc in bid_documents:
                if (doc.bidder_name == bidder_name and 
                    doc.analysis_result and 
                    doc.analysis_result.project_id == self.project_id):
                    bid_doc = doc
                    break
            
            # 按规则树顺序填充数据（只处理子项）
            for parent_item in rules_tree:
                children = parent_item['children']
                if children:
                    # 有子项的父项 - 添加每个子项的得分
                    for child_item in children:
                        # 特殊处理价格评分项，不从scores中获取
                        if child_item.get('name') != '价格分':
                            score = scores.get(child_item['name'], 0)
                            row.append(round(score, 2))
            
            # 添加价格分
            price_score = 0
            if bid_doc and bid_doc.analysis_result and bid_doc.analysis_result.price_score is not None:
                price_score = bid_doc.analysis_result.price_score
            row.append(round(price_score, 2))
            
            # 添加总分
            row.append(round(total_score, 2))
                
            data_rows.append(row)
            
        return data_rows
    
    def get_summary_data(self) -> List[Dict[str, Any]]:
        """
        获取汇总数据，包括各投标方的总分排名
        """
        try:
            # 获取投标文档，确保只获取当前项目的文档
            bid_documents = self.session.query(BidDocument).filter(
                BidDocument.project_id == self.project_id
            ).all()
            
            # 构建汇总数据
            summary_data = []
            for bid_doc in bid_documents:
                # 确保分析结果存在且属于当前项目
                if (bid_doc.analysis_result and 
                    bid_doc.analysis_result.project_id == self.project_id):
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
