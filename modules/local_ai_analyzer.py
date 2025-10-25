#!/usr/bin/env python
# -*- coding:utf-8 -*-
#
# 作者           : KingFreeDom
# 创建时间         : 2025-08-31 15:23:42
# 最近一次编辑者      : KingFreeDom
# 最近一次编辑时间     : 2025-09-06 21:27:45
# 文件相对于项目的路径   : \AI_env2\modules\local_ai_analyzer.py
#
# Copyright (c) 2025 by 中车眉山车辆有限公司/KingFreeDom, All Rights Reserved.
#
import requests
import logging
import time
import os
from typing import List, Optional
from .ai_connection_manager import get_ai_connection_manager
from modules.logging_config import get_logger

# 设置日志
logger = get_logger(__name__)


class LocalAIAnalyzer:
    def __init__(
        self, model='qwen3:30b-a3b-instruct-2507-q4_K_M', host='http://localhost:11434'
    ):
        self.model = model
        self.host = host
        # 从环境变量获取上下文长度，默认为8192
        self.context_length = int(os.environ.get('OLLAMA_CONTEXT_LENGTH', '8192'))

        # 使用连接管理器
        self.connection_manager = get_ai_connection_manager()

    def analyze_text(self, prompt):
        """
        分析文本，使用连接管理器进行优化

        Args:
            prompt: 输入提示词

        Returns:
            AI分析结果
        """
        # 使用连接管理器进行分析
        return self.connection_manager.analyze_text(prompt)

    def analyze_bid_document(
        self, rule_description: str, document_text: str, max_score: float
    ) -> Optional[float]:
        """
        分析投标文件并根据评分规则给出分数

        Args:
            rule_description: 评分规则描述
            document_text: 投标文件文本
            max_score: 最高分数

        Returns:
            Optional[float]: 分数，如果失败则返回None
        """
        try:
            # 构造分析提示
            prompt = f"""
            根据以下评分规则对投标文件进行评分：
            
            评分规则：{rule_description}
            满分：{max_score}
            
            投标文件内容：
            {document_text[:2000]}  # 限制文本长度
            
            请根据评分规则对投标文件进行评分，只返回一个0到{max_score}之间的数字，不要包含其他文字。
            """

            logger.info(f'分析投标文件，规则: {rule_description[:50]}...')

            # 发送请求到AI模型
            response = self.analyze_text(prompt)

            # 尝试提取分数
            score = self._extract_score_from_response(response, max_score)

            if score is not None:
                logger.info(f'成功分析投标文件，得分为: {score}')
            else:
                logger.warning(f'无法从AI响应中提取分数，响应内容: {response}')

            return score
        except Exception as e:
            logger.error(f'分析投标文件时出错: {e}', exc_info=True)
            return None

    def _extract_score_from_response(
        self, response: str, max_score: float
    ) -> Optional[float]:
        """
        从AI响应中提取分数

        Args:
            response: AI响应文本
            max_score: 最大分数

        Returns:
            Optional[float]: 提取的分数，如果无法提取则返回None
        """
        try:
            # 尝试直接转换为浮点数
            score = float(response.strip())
            if 0 <= score <= max_score:
                return score
            else:
                logger.warning(f'提取的分数 {score} 超出有效范围 [0, {max_score}]')
                return None
        except ValueError:
            # 如果直接转换失败，尝试从文本中提取数字
            import re

            numbers = re.findall(r'\d+\.?\d*', response)
            if numbers:
                score = float(numbers[0])
                if 0 <= score <= max_score:
                    return score
            logger.warning(f"无法从响应 '{response}' 中提取有效分数")
            return None

    def get_embeddings(
        self, texts: List[str], embedding_model: str = 'qwen3-embedding:latest'
    ):
        """
        获取文本嵌入向量

        Args:
            texts: 文本列表
            embedding_model: 嵌入模型名称

        Returns:
            嵌入向量列表
        """
        try:
            embeddings = []
            embedding_api_url = f'{self.host}/api/embeddings'

            for text in texts:
                payload = {'model': embedding_model, 'prompt': text}

                response = requests.post(embedding_api_url, json=payload, timeout=300)
                response.raise_for_status()

                result = response.json()
                embeddings.append(result.get('embedding', []))

            return embeddings
        except Exception as e:
            logger.error(f'获取嵌入向量时出错: {e}')
            return []

    def check_model_availability(self):
        try:
            response = requests.get(
                f'{self.api_url.replace("/api/generate", "/api/tags")}'
            )
            response.raise_for_status()
            models = response.json().get('models', [])
            for model in models:
                if model['name'] == self.model:
                    return True
            return False
        except requests.exceptions.RequestException:
            return False

    def parse_ai_response(self, response):
        # Extract the content from the 'response' key
        return response.get('response', '').strip()
