#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
运行时配置管理模块
用于管理应用程序的各种运行时配置
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


CONFIG_PATH = Path('config/runtime_settings.json')
PROJECT_CONFIG_DIR = Path('project_configs')
PROJECT_CONFIG_DIR.mkdir(exist_ok=True)


class RuntimeConfig:
    """运行时配置管理类"""

    def __init__(self):
        """初始化运行时配置"""
        # 加载基础配置
        self.base_config = self._load_base_config()

        # Ollama服务配置
        self.ollama_host = os.environ.get('OLLAMA_HOST', 'http://localhost:11434')
        self.ollama_model = os.environ.get(
            'OLLAMA_MODEL', 'qwen3:30b-a3b-instruct-2507-q4_K_M'
        )

        # MinerU服务配置
        self.mineru_host = os.environ.get('MINERU_HOST', 'http://localhost:8000')

        # 其他配置
        self.debug_mode = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
        self.log_level = os.environ.get('LOG_LEVEL', 'INFO')

    def _default_config(self) -> Dict[str, Any]:
        """默认运行参数配置（中文注释）。"""
        return {
            'pdf_page_max_workers': 4,  # 单PDF并行页数上限
            'pdf_page_timeout_sec': 20,  # 单页超时
            'pdf_overall_min_timeout_sec': 60,  # 单文件最小总超时
            'max_content_length': 500 * 1024 * 1024,  # 文件上传大小限制，默认500MB
            'single_file_max_size': 100 * 1024 * 1024,  # 单个文件大小限制，默认100MB
            'auto_delete_md_files': False,  # 分析完成后是否自动删除MD文件，默认不删除
            'enable_retry_on_quality_issue': True,  # 当MD质量不达标时是否启用重新分析，默认启用
        }

    def _load_base_config(self) -> Dict[str, Any]:
        """读取运行参数配置（若不存在则创建默认配置）。"""
        try:
            if CONFIG_PATH.exists():
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 合并默认值，保留已有
                    cfg = self._default_config()
                    cfg.update(data or {})
                    return cfg
        except Exception:
            pass
        cfg = self._default_config()
        self._save_base_config(cfg)
        return cfg

    def _save_base_config(self, cfg: Dict[str, Any]) -> None:
        """保存运行参数配置到文件。"""
        try:
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def load_config_for_project(self, project_id: int) -> Optional[Dict[str, Any]]:
        """读取项目级运行参数配置（若不存在则返回None）。"""
        try:
            project_config_path = PROJECT_CONFIG_DIR / f'project_{project_id}.json'
            if project_config_path.exists():
                with open(project_config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def save_config_for_project(self, project_id: int, cfg: Dict[str, Any]) -> bool:
        """保存项目级运行参数配置到文件。"""
        try:
            project_config_path = PROJECT_CONFIG_DIR / f'project_{project_id}.json'
            with open(project_config_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
            return True
        except Exception:
            return False

    def get_int(self, key: str, default_value: int) -> int:
        """安全获取整型配置。"""
        try:
            v = self.base_config.get(key, default_value)
            return int(v)
        except Exception:
            return default_value

    def get_bool(self, key: str, default_value: bool) -> bool:
        """安全获取布尔型配置。"""
        try:
            v = self.base_config.get(key, default_value)
            return bool(v)
        except Exception:
            return default_value

    def get_ollama_api_url(self) -> str:
        """获取Ollama API URL"""
        return f'{self.ollama_host}/api/generate'

    def get_ollama_tags_url(self) -> str:
        """获取Ollama模型标签URL"""
        return f'{self.ollama_host}/api/tags'

    def update_ollama_config(
        self, host: Optional[str] = None, model: Optional[str] = None
    ):
        """
        更新Ollama配置

        Args:
            host: Ollama服务主机地址
            model: 使用的模型名称
        """
        if host is not None:
            self.ollama_host = host
        if model is not None:
            self.ollama_model = model

    def get_config_summary(self) -> dict:
        """
        获取配置摘要

        Returns:
            dict: 当前配置摘要
        """
        return {
            'ollama_host': self.ollama_host,
            'ollama_model': self.ollama_model,
            'mineru_host': self.mineru_host,
            'debug_mode': self.debug_mode,
            'log_level': self.log_level,
            'base_config': self.base_config,
        }


# 全局配置实例
runtime_config = RuntimeConfig()


def load_config() -> Dict[str, Any]:
    """加载全局运行时配置"""
    return runtime_config.base_config


def save_config(config: Dict[str, Any]) -> bool:
    """保存全局运行时配置"""
    try:
        runtime_config._save_base_config(config)
        runtime_config.base_config = config
        return True
    except Exception:
        return False


def load_config_for_project(project_id: int) -> Optional[Dict[str, Any]]:
    """加载项目级运行时配置"""
    return runtime_config.load_config_for_project(project_id)


def save_config_for_project(project_id: int, config: Dict[str, Any]) -> bool:
    """保存项目级运行时配置"""
    return runtime_config.save_config_for_project(project_id, config)


def get_int(key: str, default_value: int) -> int:
    """安全获取整型配置"""
    return runtime_config.get_int(key, default_value)


def get_bool(key: str, default_value: bool) -> bool:
    """安全获取布尔型配置"""
    return runtime_config.get_bool(key, default_value)
