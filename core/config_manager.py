import json
from typing import Any, Dict

from .state_manager import ensure_json_suffix


def load_config(config_map: str) -> Dict[str, Any]:
    """
    从 config_map 读取配置。
    例如 config_map='config' -> 读取 config.json
    """
    config_file = ensure_json_suffix(config_map)
    with open(config_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: Dict[str, Any], config_map: str) -> str:
    """
    保存配置到 config_map.json
    """
    config_file = ensure_json_suffix(config_map)
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
    return config_file