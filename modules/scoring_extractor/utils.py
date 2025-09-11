import re
from typing import List, Dict, Any


def clean_criteria_name(name: str) -> str:
    """清理评分项名称"""
    # 移除多余的空白字符
    name = re.sub(r'\s+', ' ', name.strip())
    
    # 移除常见的前缀和后缀
    name = re.sub(r'^[（\(]*\d+[\.\-]?\d*[）\)]*\s*', '', name)
    name = re.sub(r'\s*[（\(]*\d+分?[）\)]*$', '', name)
    
    # 移除特殊字符
    name = re.sub(r'[※★▲●○◆■□△▽◇◆]', '', name)
    
    return name.strip()


def is_similar_criteria(name1: str, name2: str) -> bool:
    """判断两个评分项名称是否相似"""
    # 清理名称
    clean_name1 = clean_criteria_name(name1)
    clean_name2 = clean_criteria_name(name2)
    
    # 如果完全相等
    if clean_name1 == clean_name2:
        return True
        
    # 如果一个包含另一个
    if clean_name1 in clean_name2 or clean_name2 in clean_name1:
        return True
        
    # 计算相似度（简单实现）
    common_chars = set(clean_name1) & set(clean_name2)
    total_chars = set(clean_name1) | set(clean_name2)
    
    if len(total_chars) == 0:
        return False
        
    similarity = len(common_chars) / len(total_chars)
    return similarity > 0.8


def find_and_add_price_rule(text: str, structured_rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """从文本中查找价格分计算公式，并将其添加/更新到规则列表中"""
    # 查找价格分计算公式
    price_patterns = [
        r'(评标基准价.*?价格分.*?)',
        r'(价格分.*?评标基准价.*?)',
        r'(基准价.*?价格分.*?)',
        r'价格分计算[：:]\s*(.*?)(?=\n\n|\Z)',
        r'价格评分[：:]\s*(.*?)(?=\n\n|\Z)',
    ]

    price_description = ''
    for pattern in price_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            price_description = match.group(1).strip()
            break

    # 查找价格分值，限制分数范围避免错误识别
    score_patterns = [
        r'价格分\s*[:：]?\s*(\d{1,2}(?:\.\d)?)\s*分',
        r'(\d{1,2}(?:\.\d)?)\s*分\s*\(价格分\)',
        r'价格.*?(\d{1,2}(?:\.\d)?)\s*分',
    ]

    price_score = 0.0
    for pattern in score_patterns:
        match = re.search(pattern, text)
        if match:
            # 只有当分数合理时才接受（通常价格分较高）
            score = float(match.group(1))
            if score > 10:
                price_score = score
                break

    # 如果找到了价格分信息
    if price_score > 0:
        # 检查是否已存在价格分规则
        existing_price_rule = None
        for rule in structured_rules:
            if rule.get('is_price_criteria'):
                existing_price_rule = rule
                break

        price_rule = {
            'numbering': ('99',),  # 价格分通常放在最后
            'criteria_name': '价格分',
            'max_score': price_score,
            'weight': 1.0,
            'description': price_description if price_description else '价格分计算',
            'category': '评标办法',
            'is_price_criteria': True,
        }

        if existing_price_rule:
            # 更新现有价格规则
            existing_price_rule.update(price_rule)
        else:
            # 添加新的价格规则
            structured_rules.append(price_rule)

    return structured_rules


def is_valid_score(score: float) -> bool:
    """
    验证分数是否有效
    评分规则中通常分数为整数或一位小数，且在合理范围内
    """
    # 检查分数是否在合理范围内 (0-100)
    if score <= 0 or score > 100:
        return False
    
    # 检查是否为合理的分数格式（整数或一位小数）
    # 避免识别出像1.6这样不常见的分数
    if score != int(score) and round(score, 1) != score:
        return False
    
    return True