#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
AI连接管理器
实现AI模型连接的复用和优化
"""

import requests
import logging
import time
import os
from typing import Optional, Dict, Any
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class AIConnectionManager:
    """AI连接管理器，实现连接复用和优化"""

    def __init__(
        self, model='qwen3:30b-a3b-instruct-2507-q4_K_M', host='http://localhost:11434'
    ):
        self.model = model
        self.host = host
        self.api_url = f'{host}/api/generate'
        self.context_length = int(os.environ.get('OLLAMA_CONTEXT_LENGTH', '8192'))

        # 创建持久化会话
        self.session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )

        # 配置适配器
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=1,  # 连接池大小
            pool_maxsize=1,  # 最大连接数
            pool_block=False,  # 不阻塞
        )

        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

        # 设置默认超时
        self.session.timeout = 600  # 10分钟超时

        logger.info(f'AI连接管理器初始化完成，模型: {model}, 主机: {host}')

    def analyze_text(self, prompt: str) -> str:
        """
        分析文本，使用持久化连接

        Args:
            prompt: 输入提示词

        Returns:
            AI分析结果
        """
        # 优化AI分析速度的参数设置
        options = {
            'temperature': 0.7,  # 降低随机性以提高一致性
            'top_p': 0.9,  # 限制词汇选择范围
            'stop': ['\n\n'],  # 设置停止条件
            'num_predict': 500,  # 限制生成长度
            'num_ctx': self.context_length,  # 设置上下文长度
        }

        payload = {
            'model': self.model,
            'prompt': prompt,
            'stream': False,
            'options': options,
        }

        # 使用持久化连接发送请求
        max_retries = 3
        retry_delay = 2  # 减少重试延迟

        for attempt in range(max_retries):
            try:
                logger.debug(
                    f'向AI模型发送请求，模型: {self.model} (尝试 {attempt + 1}/{max_retries})'
                )

                # 使用持久化会话发送请求
                response = self.session.post(self.api_url, json=payload, timeout=600)
                response.raise_for_status()

                # 解析响应
                result = response.json()
                logger.debug('成功接收AI模型响应')
                return self.parse_ai_response(result)

            except requests.exceptions.Timeout:
                logger.warning(f'AI模型请求超时 (尝试 {attempt + 1}/{max_retries})')
                if attempt + 1 < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error('AI模型请求在多次重试后仍然超时')
                    return 'Error: AI model request timeout. Please try again.'

            except requests.exceptions.ConnectionError:
                logger.error('无法连接到AI模型服务')
                return f"Error: Could not connect to the AI model service. Please ensure Ollama is running and the model '{self.model}' is available."

            except Exception as e:
                logger.error(f'AI模型请求失败: {e}')
                if attempt + 1 < max_retries:
                    time.sleep(retry_delay)
                else:
                    return f'Error: AI model request failed: {str(e)}'

        return 'Error: AI model request failed after all retries.'

    def parse_ai_response(self, result: Dict[str, Any]) -> str:
        """
        解析AI响应

        Args:
            result: AI模型返回的JSON结果

        Returns:
            解析后的文本
        """
        try:
            if 'response' in result:
                return result['response'].strip()
            else:
                logger.warning('AI响应格式异常，未找到response字段')
                return 'Error: Invalid AI response format.'
        except Exception as e:
            logger.error(f'解析AI响应时出错: {e}')
            return f'Error: Failed to parse AI response: {str(e)}'

    def close(self):
        """关闭连接"""
        if self.session:
            self.session.close()
            logger.info('AI连接管理器已关闭')

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# 全局连接管理器实例
_connection_manager = None


def get_ai_connection_manager() -> AIConnectionManager:
    """
    获取全局AI连接管理器实例（单例模式）

    Returns:
        AIConnectionManager: AI连接管理器实例
    """
    global _connection_manager

    if _connection_manager is None:
        _connection_manager = AIConnectionManager()

    return _connection_manager


def close_ai_connection_manager():
    """关闭全局AI连接管理器"""
    global _connection_manager

    if _connection_manager:
        _connection_manager.close()
        _connection_manager = None
        logger.info('全局AI连接管理器已关闭')
