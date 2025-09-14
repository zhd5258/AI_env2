import json
from sqlalchemy.orm import Session
from modules.database import AnalysisResult, ScoringRule

def get_score_for_rule(detailed_scores, rule_name):
    """从详细评分中查找特定规则的分数"""
    if not detailed_scores:
        return None
    for item in detailed_scores:
        # 支持两种格式：旧格式使用criteria_name，新格式使用Child_Item_Name
        criteria_name = item.get('Child_Item_Name') or item.get('criteria_name')
        if criteria_name == rule_name:
            return item.get('score')
    return None

def generate_summary_data(project_id: int, db: Session):
    """为项目生成具有多层表头的动态汇总表数据"""
    
    # 1. 获取项目的所有评分规则
    rules = db.query(ScoringRule).filter(ScoringRule.project_id == project_id).all()
    if not rules:
        return {'error': '该项目没有找到评分规则。'}

    # 构建规则树 - 正确处理父子项关系
    parent_rules = {}  # 存储父项规则
    parent_groups = {}  # 存储父子项分组
    
    # 先找出所有父项规则
    for rule in rules:
        if rule.Parent_Item_Name and not rule.Child_Item_Name:
            parent_rules[rule.Parent_Item_Name] = rule
    
    # 处理子项规则，构建父子项关系
    for rule in rules:
        if rule.is_price_criteria:
            continue  # 价格规则单独处理
            
        if rule.Parent_Item_Name and rule.Child_Item_Name:
            # 这是子项规则
            if rule.Parent_Item_Name not in parent_groups:
                # 获取父项信息
                parent_rule = parent_rules.get(rule.Parent_Item_Name)
                parent_groups[rule.Parent_Item_Name] = {
                    'rule': parent_rule,
                    'children': []
                }
            parent_groups[rule.Parent_Item_Name]['children'].append({
                'rule': rule
            })
    
    # 构建规则树结构
    rules_tree = []
    for parent_name, group in parent_groups.items():
        parent_rule = group['rule']
        children = group['children']
        
        node = {
            'rule': parent_rule,
            'children': children
        }
        rules_tree.append(node)
    
    # 2. 构建多层表头
    header_row1 = [
        {'name': '排名', 'rowspan': 2},
        {'name': '投标人', 'rowspan': 2}
    ]
    header_row2 = []
    
    flat_child_rules = [] # 用于后续数据匹配

    # 构建表头
    for parent_node in rules_tree:
        parent_rule = parent_node['rule']
        children = parent_node['children']
        
        parent_name = parent_rule.Parent_Item_Name if parent_rule else "未知"
        parent_score = parent_rule.Parent_max_score if parent_rule else 0
        
        parent_header = f"{parent_name} ({parent_score}分)"
        
        if not children:
            # 没有子项的父项，自身占一列
            header_row1.append({'name': parent_header, 'rowspan': 2})
            # 添加一个虚拟的子项规则用于数据匹配
            if parent_rule:
                flat_child_rules.append(parent_rule)
        else:
            # 有子项的父项
            header_row1.append({'name': parent_header, 'colspan': len(children)})
            for child_node in children:
                child_rule = child_node['rule']
                child_name = f"{child_rule.Child_Item_Name} ({child_rule.Child_max_score}分)"
                header_row2.append({'name': child_name, 'full_name': child_rule.Child_Item_Name})
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
        # 只计算子项得分
        for rule in flat_child_rules:
            if hasattr(rule, 'Child_Item_Name') and rule.Child_Item_Name:
                score = get_score_for_rule(detailed_scores, rule.Child_Item_Name)
            else:
                # 兼容旧格式
                score = get_score_for_rule(detailed_scores, getattr(rule, 'criteria_name', None))
            scores.append(score)

        # 计算总分：只包括子项得分和价格分
        total_score = sum(s for s in scores if s is not None)
        if result.price_score is not None:
            total_score += result.price_score

        bidder_row = {
            'rank': rank,
            'bidder_name': result.bidder_name,
            'scores': scores,
            'price_score': result.price_score,
            'total_score': round(total_score, 2)
        }
        rows_data.append(bidder_row)
        rank += 1
        
    # 5. 组合最终结果
    final_summary = {
        'header_rows': [header_row1, header_row2],
        'rows': rows_data
    }
    
    return final_summary