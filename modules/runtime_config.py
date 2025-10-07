import json
import os
from pathlib import Path
from typing import Dict, Any, Optional


CONFIG_PATH = Path('config/runtime_settings.json')
PROJECT_CONFIG_DIR = Path('project_configs')
PROJECT_CONFIG_DIR.mkdir(exist_ok=True)


def _default_config() -> Dict[str, Any]:
    """默认运行参数配置（中文注释）。"""
    return {
        'pdf_page_max_workers': 4,  # 单PDF并行页数上限
        'pdf_page_timeout_sec': 20,  # 单页超时
        'pdf_overall_min_timeout_sec': 60,  # 单文件最小总超时
        'max_content_length': 500 * 1024 * 1024,  # 文件上传大小限制，默认500MB
        'single_file_max_size': 100 * 1024 * 1024,  # 单个文件大小限制，默认100MB
        'auto_delete_md_files': False,  # 分析完成后是否自动删除MD文件，默认不删除
    }


def load_config() -> Dict[str, Any]:
    """读取运行参数配置（若不存在则创建默认配置）。"""
    try:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 合并默认值，保留已有
                cfg = _default_config()
                cfg.update(data or {})
                return cfg
    except Exception:
        pass
    cfg = _default_config()
    save_config(cfg)
    return cfg


def save_config(cfg: Dict[str, Any]) -> None:
    """保存运行参数配置到文件。"""
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_config_for_project(project_id: int) -> Optional[Dict[str, Any]]:
    """读取项目级运行参数配置（若不存在则返回None）。"""
    try:
        project_config_path = PROJECT_CONFIG_DIR / f'project_{project_id}.json'
        if project_config_path.exists():
            with open(project_config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return None


def save_config_for_project(project_id: int, cfg: Dict[str, Any]) -> bool:
    """保存项目级运行参数配置到文件。"""
    try:
        project_config_path = PROJECT_CONFIG_DIR / f'project_{project_id}.json'
        with open(project_config_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_int(cfg: Dict[str, Any], key: str, default_value: int) -> int:
    """安全获取整型配置。"""
    try:
        v = cfg.get(key, default_value)
        return int(v)
    except Exception:
        return default_value


def get_bool(cfg: Dict[str, Any], key: str, default_value: bool) -> bool:
    """安全获取布尔型配置。"""
    try:
        v = cfg.get(key, default_value)
        return bool(v)
    except Exception:
        return default_value
