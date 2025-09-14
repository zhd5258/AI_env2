#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试价格分计算逻辑的程序
根据日志中的数据模拟价格分计算过程
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from modules.local_ai_analyzer import LocalAIAnalyzer
import json
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def test_price_calculation():
    """
    测试价格分计算过程
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
    
    logger.info("开始测试价格分计算")
    logger.info(f"投标人报价信息: {bidder_prices}")
    logger.info(f"价格分满分: {max_score}")
    logger.info(f"价格评分规则: {price_formula}")
    
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

    # 记录发送给AI大模型的信息
    logger.info("=" * 50)
    logger.info("发送给AI大模型的价格分计算请求:")
    logger.info(f"价格评分规则: {price_formula}")
    logger.info(f"投标人报价: {bidder_prices}")
    logger.info(f"价格分满分: {max_score}")
    logger.info("完整prompt:")
    logger.info(prompt)
    logger.info("=" * 50)
    
    try:
        # 调用AI大模型计算价格分
        ai_analyzer = LocalAIAnalyzer()
        logger.info("正在调用AI大模型计算价格分...")
        ai_response = ai_analyzer.analyze_text(prompt)
        
        # 记录AI大模型的返回值
        logger.info("=" * 50)
        logger.info("AI大模型返回的完整响应:")
        logger.info(ai_response)
        logger.info("=" * 50)
        
        # 尝试解析AI响应
        if ai_response:
            try:
                price_scores = json.loads(ai_response)
                if isinstance(price_scores, dict):
                    logger.info(f"成功解析价格分计算结果: {price_scores}")
                    return price_scores
                else:
                    logger.error("AI响应不是有效的字典格式")
            except json.JSONDecodeError:
                logger.error(f"无法解析AI响应为JSON格式: {ai_response}")
        else:
            logger.error("AI大模型返回空响应")
            
    except Exception as e:
        logger.error(f"调用AI大模型计算价格分时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return {}

if __name__ == "__main__":
    logger.info("开始为项目 4 计算价格分")
    logger.info("开始计算项目 4 的价格分")
    logger.info("找到价格评分规则: 满分 40, 公式: None, 描述: 满足招标文件要求且投标价格最低的投标报价为评标基准价，其价格分为满分。其他投标人的价格分统一按照下列公式计算：投标报价得分＝（评标基准价/投标报价）*40%*100")
    
    result = test_price_calculation()
    logger.info(f"计算出价格分: {result}")