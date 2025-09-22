import json
from pathlib import Path
from typing import Dict, Any


CONFIG_PATH = Path('runtime_settings.json')


def _default_config() -> Dict[str, Any]:
    """默认运行参数配置（中文注释）。"""
    return {
        'pdf_page_max_workers': 4,  # 单PDF并行页数上限
        'pdf_page_timeout_sec': 20,  # 单页超时
        'pdf_overall_min_timeout_sec': 60,  # 单文件最小总超时
        'ai_analysis_page_limit': 5,  # 发送给AI大模型分析的页面数量限制（默认改为5）
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


def _project_dir(project_id: int) -> Path:
    """获取项目配置目录路径。"""
    base = Path('uploads') / f'project_{project_id}'
    try:
        base.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return base


def load_config_for_project(project_id: int) -> Dict[str, Any]:
    """读取指定项目的运行参数配置，若不存在则返回默认并创建文件。"""
    cfg_path = _project_dir(project_id) / 'runtime_settings.json'
    try:
        if cfg_path.exists():
            with open(cfg_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                cfg = _default_config()
                cfg.update(data or {})
                return cfg
    except Exception:
        pass
    cfg = _default_config()
    save_config_for_project(project_id, cfg)
    return cfg


def save_config_for_project(project_id: int, cfg: Dict[str, Any]) -> None:
    """保存指定项目的运行参数配置。"""
    cfg_path = _project_dir(project_id) / 'runtime_settings.json'
    try:
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def get_int(cfg: Dict[str, Any], key: str, default_value: int) -> int:
    """安全获取整型配置。"""
    try:
        v = cfg.get(key, default_value)
        return int(v)
    except Exception:
        return default_value
