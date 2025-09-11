
import json
from sqlalchemy.orm import Session
from modules.database import TenderProject, AnalysisResult, ScoringRule

def get_rules_hierarchy(rules):
    """构建评分规则的层级结构"""
    rule_map = {rule.id: {
        'id': rule.id,
        'name': rule.criteria_name,
        'numbering': rule.numbering,
        'children': []
    } for rule in rules}
    
    nested_rules = []
    for rule in rules:
        if rule.parent_id:
            if rule.parent_id in rule_map:
                parent = rule_map[rule.parent_id]
                parent['children'].append(rule_map[rule.id])
        else:
            nested_rules.append(rule_map[rule.id])
            
    # 对规则进行排序
    def sort_key(r):
        # 尝试将编号转换为数字元组以便正确排序
        try:
            return tuple(map(int, r['numbering'].split('.')))
        except:
            return (999,) # 如果转换失败，放到最后

    for item in rule_map.values():
        item['children'].sort(key=sort_key)
    nested_rules.sort(key=sort_key)
    
    return nested_rules

def flatten_rules(nested_rules):
    """将层级规则展平为表头列表"""
    headers = []
    for rule in nested_rules:
        headers.append(rule['name'])
        if rule['children']:
            # 递归展平子规则
            child_headers = flatten_rules(rule['children'])
            headers.extend(child_headers)
    return headers

def get_score_for_rule(detailed_scores, rule_name):
    """从详细评分中递归查找特定规则的分数"""
    if not detailed_scores:
        return None
    for item in detailed_scores:
        if item.get('criteria_name') == rule_name:
            return item.get('score')
        if 'children' in item and item['children']:
            score = get_score_for_rule(item['children'], rule_name)
            if score is not None:
                return score
    return None

def generate_summary_data(project_id: int, db: Session):
    """为项目生成动态汇总表数据"""
    
    # 1. 获取项目的所有评分规则并构建动态表头
    rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).order_by(ScoringRule.numbering).all()
    if not rules:
        return {'error': '该项目没有找到评分规则。'}
        
    nested_rules = get_rules_hierarchy(rules)
    flat_headers = flatten_rules(nested_rules)
    
    # 2. 获取项目的所有分析结果
    results = db.query(AnalysisResult).filter(AnalysisResult.project_id == project_id).order_by(AnalysisResult.total_score.desc()).all()
    if not results:
        return {'error': '该项目没有找到分析结果。'}

    # 3. 构建表格行数据
    rows_data = []
    rank = 1
    for result in results:
        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': [],
            'price_score': result.price_score,
            'total_score': result.total_score
        }
        
        detailed_scores = json.loads(result.detailed_scores) if isinstance(result.detailed_scores, str) else result.detailed_scores
        
        for header in flat_headers:
            score = get_score_for_rule(detailed_scores, header)
            bidder_row['scores'].append(score)
            
        rows_data.append(bidder_row)
        rank += 1
        
    # 4. 组合最终结果
    final_summary = {
        'headers': ['排名', '投标人'] + flat_headers + ['价格分', '总分'],
        'rows': rows_data
    }
    
    return final_summary
