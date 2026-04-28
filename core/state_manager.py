import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np


def ensure_json_suffix(filename: str) -> str:
    """确保文件名以 .json 结尾"""
    filename = str(filename)
    return filename if filename.endswith(".json") else f"{filename}.json"


def json_default(obj: Any):
    """把 numpy 等非标准 JSON 类型转换为可序列化对象"""
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        value = float(obj)
        return None if (value != value) else value
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, set):
        return list(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def init_state() -> Dict[str, Any]:
    """初始化 state 结构"""
    return {
        "processed_files": [],
        "valid_sources": [],
        "skipped_sources": {},
        "results": {},
        # 兼容旧结构
        "lsp_expected_period": [],
        "jv_expected_period": [],
        "dcf_possible_period": [],
        "wwz_possibly_period": [],
        # auto 模式用
        "afm_dict": []
    }


def save_state(state: Dict[str, Any], state_path: str, filename: str = "state") -> str:
    """
    保存程序状态到指定文件。
    返回保存后的文件路径。
    """
    os.makedirs(state_path, exist_ok=True)
    file_path = os.path.join(state_path, ensure_json_suffix(filename))
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False, default=json_default)
    return file_path


def load_state(state_path: str, filename: str = "state") -> Optional[Dict[str, Any]]:
    """
    从指定路径加载程序状态。
    文件不存在、为空或 JSON 损坏时返回 None。
    """
    file_path = os.path.join(state_path, ensure_json_suffix(filename))
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return None
    except (json.JSONDecodeError, OSError):
        return None


def load_or_init_state(state_path: str, filename: str = "state") -> Dict[str, Any]:
    """
    读取 state；如果不存在则初始化一个新的 state。
    """
    state = load_state(state_path, filename)
    if state is None or not isinstance(state, dict):
        return init_state()

    defaults = init_state()
    for key, value in defaults.items():
        state.setdefault(key, value)

    return state


def backup_state(state: Dict[str, Any], backup_path: str) -> str:
    """
    备份 state 到 back_up 目录。
    返回备份文件路径。
    """
    os.makedirs(backup_path, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
    file_path = os.path.join(backup_path, f"state_{timestamp}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False, default=json_default)
    return file_path