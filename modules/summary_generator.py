
import json
from sqlalchemy.orm import Session
from modules.database import AnalysisResult, ScoringRule

def get_score_for_rule(detailed_scores, rule_name):
    """从详细评分中递归查找特定规则的分数"""
    if not detailed_scores:
        return None
    for item in detailed_scores:
        if item.get('criteria_name') == rule_name:
            return item.get('score')
        # 假设详细分数也是嵌套的
        if 'children' in item and item['children']:
            score = get_score_for_rule(item['children'], rule_name)
            if score is not None:
                return score
    return None

def generate_summary_data(project_id: int, db: Session):
    """为项目生成具有多层表头的动态汇总表数据"""
    
    # 1. 获取项目的所有评分规则
    rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.numbering).all()
    if not rules:
        return {'error': '该项目没有找到评分规则。'}

    # 构建规则树
    rules_tree = []
    rule_map = {r.id: {'rule': r, 'children': []} for r in rules}
    for r in rules:
        if r.parent_id and r.parent_id in rule_map:
            rule_map[r.parent_id]['children'].append(rule_map[r.id])
        elif not r.parent_id:
            rules_tree.append(rule_map[r.id])

    # 2. 构建多层表头
    header_row1 = [
        {'name': '排名', 'rowspan': 2},
        {'name': '投标人', 'rowspan': 2}
    ]
    header_row2 = []
    
    flat_child_rules = [] # 用于后续数据匹配

    for parent_node in rules_tree:
        parent_rule = parent_node['rule']
        children = parent_node['children']
        
        parent_name = f"{parent_rule.criteria_name} ({parent_rule.max_score}分)"
        
        if not children:
            # 没有子项的父项，自身占一列
            header_row1.append({'name': parent_name, 'rowspan': 2})
            flat_child_rules.append(parent_rule)
        else:
            # 有子项的父项
            header_row1.append({'name': parent_name, 'colspan': len(children)})
            for child_node in children:
                child_rule = child_node['rule']
                child_name = f"{child_rule.criteria_name} ({child_rule.max_score}分)"
                header_row2.append({'name': child_name, 'full_name': child_rule.criteria_name})
                flat_child_rules.append(child_rule)

    header_row1.extend([
        {'name': '价格分', 'rowspan': 2},
        {'name': '总分', 'rowspan': 2}
    ])

    # 3. 获取项目的所有分析结果
    results = db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).order_by(AnalysisResult.total_score.desc()).all()
    if not results:
        return {'error': '该项目没有找到分析结果。'}

    # 4. 构建表格行数据
    rows_data = []
    rank = 1
    for result in results:
        detailed_scores = json.loads(result.detailed_scores) if isinstance(result.detailed_scores, str) else result.detailed_scores
        
        scores = []
        for rule in flat_child_rules:
            score = get_score_for_rule(detailed_scores, rule.criteria_name)
            scores.append(score)

        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': scores,
            'price_score': result.price_score,
            'total_score': result.total_score
        }
        rows_data.append(bidder_row)
        rank += 1
        
    # 5. 组合最终结果
    final_summary = {
        'header_rows': [header_row1, header_row2],
        'rows': rows_data
    }
    
    return final_summary
