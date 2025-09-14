#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
生成价格分计算prompt的程序
根据日志中的数据生成发送给AI大模型的prompt
"""

import json

def generate_price_calculation_prompt():
    """
    生成价格分计算的prompt
    """
    # 模拟日志中的数据
    bidder_prices = {
        '扬州琼花涂装工程技术有限公司': 2270000.0,
        '盐城大德涂装作业有限公司': 12144732.0,
        '武汉新国铁博达科技有限公司': 2876875.0,
        '山东创杰智慧装备科技有限公司': 86498326.0,
        '湖北三江博力智能装备有限公司': 22862800.0,
        '中车眉山车辆有限公司': 17247224171.0,
        '江苏鑫桥环保科技有限公司(': 1729800.0
    }
    
    max_score = 40
    price_formula = "满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分。其他投标人的价格分统一按照下列公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100"
    
    # 构造发送给AI大模型的prompt
    prompt = f"""
你是一个专业的评标专家，请根据以下价格评分规则和各投标人的投标报价，计算每个投标人的价格得分。

价格评分规则:
{price_formula}

各投标人报价信息:
{bidder_prices}

价格分满分: {max_score}

请严格按照以下JSON格式输出结果:
{{
    "投标人名称1": 得分1,
    "投标人名称2": 得分2,
    // ...更多投标人
}}

只输出JSON结果，不要包含其他解释性文字。
"""

    print("=" * 50)
    print("发送给AI大模型的价格分计算请求:")
    print(f"价格评分规则: {price_formula}")
    print(f"投标人报价: {bidder_prices}")
    print(f"价格分满分: {max_score}")
    print("完整prompt:")
    print(prompt)
    print("=" * 50)
    
    return prompt

if __name__ == "__main__":
    print("开始为项目 4 计算价格分")
    print("开始计算项目 4 的价格分")
    print("找到价格评分规则: 满分 40, 公式: None, 描述: 满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分。其他投标人的价格分统一按照下列公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100")
    
    prompt = generate_price_calculation_prompt()
    
    print("生成的prompt已显示在上方")