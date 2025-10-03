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
import json
import logging
import time

# 设置日志
logger = logging.getLogger(__name__)


class LocalAIAnalyzer:
    def __init__(
        self, model='qwen3:30b-a3b-instruct-2507-q4_K_M', host='http://localhost:11434'
    ):
        self.model = model
        self.api_url = f'{host}/api/generate'

    def analyze_text(self, prompt):
        # 优化AI分析速度的参数设置
        options = {
            'temperature': 0.7,  # 降低随机性以提高一致性
            'top_p': 0.9,  # 限制词汇选择范围
            'stop': ['\n\n'],  # 设置停止条件
            'num_predict': 500,  # 限制生成长度
        }

        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': options,
        }
        
        # 增加重试逻辑和更长的超时时间
        max_retries = 3
        retry_delay = 5  # seconds
        request_timeout = 600 # 10分钟超时

        for attempt in range(max_retries):
            try:
                # 添加超时设置，避免长时间等待
                response = requests.post(
                    self.api_url, json=payload, timeout=request_timeout
                )
                response.raise_for_status()

                # The response from Ollama is a JSON object
                result = response.json()
                return self.parse_ai_response(result)

            except requests.exceptions.Timeout:
                logger.warning(f'AI模型请求超时 (尝试 {attempt + 1}/{max_retries})')
                if attempt + 1 == max_retries:
                    logger.error('AI模型请求在多次重试后仍然超时')
                    return 'Error: AI model request timeout. Please try again.'
            except requests.exceptions.ConnectionError:
                logger.error('无法连接到AI模型服务')
                return f"Error: Could not connect to the AI model service. Please ensure Ollama is running and the model '{self.model}' is available."
            except requests.exceptions.RequestException as e:
                logger.error(f'AI模型请求失败: {e}')
                return f'Error: AI model request failed: {str(e)}'
            
            # 如果不是最后一次尝试，则等待后重试
            if attempt + 1 < max_retries:
                logger.info(f'将在 {retry_delay} 秒后重试...')
                time.sleep(retry_delay)
        
        return 'Error: AI model request failed after multiple retries.'


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
