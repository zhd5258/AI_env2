#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
#作者           : KingFreeDom
#创建时间         : 2025-10-06 10:38:13
#最近一次编辑者      : KingFreeDom
#最近一次编辑时间     : 2025-10-06 10:38:17
#文件相对于项目的路径   : \AI_env2\modules\detailed_score_display.py
#
#Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved. 
#
#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
详细评分展示模块
实现评分详情表和价格展示表功能
"""

import json
from typing import List, Dict, Any
from modules.database import SessionLocal, TenderProject, BidDocument, ScoringRule, AnalysisResult
import logging

logger = logging.getLogger(__name__)


class DetailedScoreDisplay:
    def __init__(self, project_id: int):
        self.project_id = project_id
        self.session = SessionLocal()
        
    def generate_detailed_score_table(self) -> Dict[str, Any]:
        """
        生成详细的评分详情表
        展示每个投标人的每个评分规则的评价得分细节，即AI评价的结论
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
            
            # 获取分析结果
            analysis_results = []
            for doc in bid_documents:
                if doc.analysis_result:
                    analysis_results.append(doc.analysis_result)
            
            # 构建评分规则树
            rules_tree = self._build_rules_tree(scoring_rules)
            
            # 构建投标方详细得分数据
            detailed_scores_data = self._build_detailed_scores(analysis_results)
            
            # 生成表头和数据
            headers = self._generate_detailed_score_headers(rules_tree)
            data = self._generate_detailed_score_data(bid_documents, detailed_scores_data, rules_tree)
            
            return {
                'headers': headers,
                'data': data,
                'bidders': [doc.bidder_name for doc in bid_documents]
            }
            
        except Exception as e:
            logger.error(f"生成详细评分表时出错: {e}")
            raise
        finally:
            self.session.close()
    
    def generate_price_display_table(self) -> Dict[str, Any]:
        """
        生成价格展示表
        列出全部投标人的名称和价格即价格得分
        """
        try:
            # 获取投标文档
            bid_documents = self.session.query(BidDocument).filter(
                BidDocument.project_id == self.project_id
            ).all()
            
            # 构建价格展示数据
            price_data = []
            for doc in bid_documents:
                if doc.analysis_result:
                    price_data.append({
                        'bidder_name': doc.bidder_name,
                        'extracted_price': doc.analysis_result.extracted_price,
                        'price_score': doc.analysis_result.price_score
                    })
            
            # 按价格得分排序
            price_data.sort(key=lambda x: x['price_score'] or 0, reverse=True)
            
            # 生成表头和数据
            headers = [['排名', '投标人名称', '投标报价', '价格得分']]
            data = []
            for i, item in enumerate(price_data, 1):
                data.append([
                    i,
                    item['bidder_name'],
                    f"¥{item['extracted_price']:,.2f}" if item['extracted_price'] is not None else 'N/A',
                    round(item['price_score'], 2) if item['price_score'] is not None else 'N/A'
                ])
            
            return {
                'headers': headers,
                'data': data
            }
            
        except Exception as e:
            logger.error(f"生成价格展示表时出错: {e}")
            raise
        finally:
            self.session.close()
    
    def _build_rules_tree(self, scoring_rules: List[ScoringRule]) -> List[Dict[str, Any]]:
        """
        构建评分规则树结构
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
                'is_price_criteria': True
            })
            
        return rules_tree
    
    def _build_detailed_scores(self, analysis_results: List[AnalysisResult]) -> Dict[str, List[Dict[str, Any]]]:
        """
        构建投标方详细得分数据
        """
        detailed_scores = {}
        
        for result in analysis_results:
            bidder_name = result.bidder_name
            detailed_scores[bidder_name] = []
            
            # 解析详细得分
            try:
                if isinstance(result.detailed_scores, str):
                    detailed_scores_data = json.loads(result.detailed_scores)
                else:
                    detailed_scores_data = result.detailed_scores
                    
                # 根据数据结构处理detailed_scores
                if isinstance(detailed_scores_data, list):
                    for score_item in detailed_scores_data:
                        # 提取评分项的详细信息
                        child_item_name = score_item.get('Child_Item_Name') or score_item.get('criteria_name')
                        score = score_item.get('score', 0)
                        reason = score_item.get('reason', '')
                        
                        if child_item_name:
                            detailed_scores[bidder_name].append({
                                'criteria_name': child_item_name,
                                'score': score,
                                'reason': reason
                            })
            except Exception as e:
                logger.error(f"解析投标方 {bidder_name} 的详细得分数据时出错: {e}")
                
        return detailed_scores
    
    def _generate_detailed_score_headers(self, rules_tree: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """
        生成详细评分表的表头
        """
        # 第一行表头
        header_row1 = [
            {'name': '排名', 'rowspan': 2},
            {'name': '投标人', 'rowspan': 2}
        ]
        
        # 第二行表头
        header_row2 = ['', '']
        
        # 根据规则树生成分级表头
        for parent_item in rules_tree:
            # 跳过价格评分项
            if parent_item.get('is_price_criteria', False):
                continue
                
            children = parent_item['children']
            if children:
                # 有子项的父项
                parent_name = parent_item['name']
                header_row1.append({'name': parent_name, 'colspan': len(children) * 2})  # 每个子项有评分和理由两列
                
                # 在第二行添加对应的子项（评分和理由）
                for child_item in children:
                    header_row2.append({'name': f"{child_item['name']} (分)"})
                    header_row2.append({'name': f"{child_item['name']} (评语)"})
        
        # 添加总分列
        header_row1.append({'name': '总分', 'rowspan': 2})
        header_row2.append('')
        
        return [header_row1, header_row2]
    
    def _generate_detailed_score_data(self, bid_documents: List[BidDocument], 
                                    detailed_scores: Dict[str, List[Dict[str, Any]]], 
                                    rules_tree: List[Dict[str, Any]]) -> List[List[Any]]:
        """
        生成详细评分表的数据行
        """
        data_rows = []
        
        # 获取所有投标方的总分用于排序
        bidder_scores_with_total = []
        for doc in bid_documents:
            if doc.analysis_result:
                total_score = doc.analysis_result.total_score or 0
                bidder_scores_with_total.append((doc.bidder_name, total_score))
        
        # 按总分排序
        bidder_scores_with_total.sort(key=lambda x: x[1], reverse=True)
        
        # 生成排序后的数据行
        for rank, (bidder_name, total_score) in enumerate(bidder_scores_with_total, 1):
            row = [rank, bidder_name]
            
            # 获取该投标方的详细得分
            scores = detailed_scores.get(bidder_name, [])
            
            # 创建得分映射以便快速查找
            score_map = {score['criteria_name']: score for score in scores}
            
            # 按规则树顺序填充数据
            for parent_item in rules_tree:
                # 跳过价格评分项
                if parent_item.get('is_price_criteria', False):
                    continue
                    
                children = parent_item['children']
                if children:
                    # 有子项的父项 - 添加每个子项的得分和理由
                    for child_item in children:
                        criteria_name = child_item['name']
                        score_info = score_map.get(criteria_name, {})
                        
                        # 添加评分
                        score = score_info.get('score', 0)
                        row.append(round(score, 2) if score is not None else 'N/A')
                        
                        # 添加评语
                        reason = score_info.get('reason', '')
                        row.append(reason if reason else 'N/A')
            
            # 添加总分
            row.append(round(total_score, 2))
                
            data_rows.append(row)
            
        return data_rows


def get_detailed_score_data(project_id: int) -> Dict[str, Any]:
    """
    获取项目详细评分数据
    """
    display = DetailedScoreDisplay(project_id)
    return display.generate_detailed_score_table()


def get_price_display_data(project_id: int) -> Dict[str, Any]:
    """
    获取项目价格展示数据
    """
    display = DetailedScoreDisplay(project_id)
    return display.generate_price_display_table()
