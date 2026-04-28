import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from .state_manager import json_default


# =========================================================
# archive 的默认结构：尽量和 state 保持一致
# =========================================================
DEFAULT_ARCHIVE: Dict[str, Any] = {
    "processed_files": [],
    "skipped_sources": {},
    "valid_sources": [],
    "source_names": [],
    "results": {},
    "lsp_expected_period": [],
    "jv_expected_period": [],
    "dcf_possible_period": [],
    "wwz_possibly_period": [],
}


def ensure_json_suffix(filename: str) -> str:
    filename = str(filename).strip() or "archive"
    return filename if filename.endswith(".json") else f"{filename}.json"


def get_project_root() -> str:
    """
    core/archive_manager.py -> parents[1] = 项目根目录
    """
    return str(Path(__file__).resolve().parents[1])


def get_archive_root() -> str:
    root = get_project_root()
    archive_dir = os.path.join(root, "Archive")
    os.makedirs(archive_dir, exist_ok=True)
    return archive_dir


def get_archive_file_path(archive_filename: str = "archive") -> str:
    """
    固定生成到：程序主目录/Archive/archive.json
    """
    return os.path.join(get_archive_root(), ensure_json_suffix(archive_filename))


def _load_json_file(path: str, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return deepcopy(default)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return deepcopy(default)

    return data if isinstance(data, dict) else deepcopy(default)


def _unique_list(items: List[Any]) -> List[Any]:
    out = []
    seen = set()
    for x in items or []:
        if isinstance(x, (dict, list)):
            key = json.dumps(x, ensure_ascii=False, sort_keys=True, default=str)
        else:
            key = str(x)
        if key not in seen:
            seen.add(key)
            out.append(x)
    return out


def merge_archive_with_state(archive: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """
    把 state 合并到 archive 里：

    - results：按 source_name 合并，state 覆盖 archive 中同名项
    - skipped_sources：按 key 合并，state 覆盖
    - 列表字段：去重合并
    - 其他字段：state 有值就覆盖 archive
    """
    merged = deepcopy(archive) if isinstance(archive, dict) else {}
    if not isinstance(merged, dict):
        merged = {}

    state = state if isinstance(state, dict) else {}

    # 先确保基础结构存在
    for k, v in deepcopy(DEFAULT_ARCHIVE).items():
        merged.setdefault(k, deepcopy(v))

    for key, value in state.items():
        if key == "results" and isinstance(value, dict):
            base = merged.get("results", {})
            if not isinstance(base, dict):
                base = {}
            base.update(deepcopy(value))
            merged["results"] = base

        elif key == "skipped_sources" and isinstance(value, dict):
            base = merged.get("skipped_sources", {})
            if not isinstance(base, dict):
                base = {}
            base.update(deepcopy(value))
            merged["skipped_sources"] = base

        elif isinstance(value, list):
            base = merged.get(key, [])
            if not isinstance(base, list):
                base = []
            merged[key] = _unique_list(base + deepcopy(value))

        else:
            # 其他字段：直接用 state 的值覆盖
            merged[key] = deepcopy(value)

    return merged


def save_archive_from_state(state_data: Dict[str, Any], archive_filename: str = "archive") -> str:
    """
    将当前 state 合并保存到程序主目录的 Archive/archive.json
    """
    archive_path = get_archive_file_path(archive_filename)
    os.makedirs(os.path.dirname(archive_path), exist_ok=True)

    old_archive = _load_json_file(archive_path, DEFAULT_ARCHIVE)
    merged = merge_archive_with_state(old_archive, state_data)

    tmp_path = archive_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, default=json_default)
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp_path, archive_path)
    return archive_path


def sync_state_file_to_archive(state_file_path: str, archive_filename: str = "archive") -> str:
    """
    如果你手里只有 state.json 文件路径，就用这个同步到 archive.json
    """
    if not state_file_path or not os.path.exists(state_file_path):
        return ""

    try:
        with open(state_file_path, "r", encoding="utf-8") as f:
            state_data = json.load(f)
    except Exception:
        return ""

    if not isinstance(state_data, dict):
        return ""

    return save_archive_from_state(state_data, archive_filename)


def load_archive(archive_filename: str = "archive") -> Dict[str, Any]:
    """
    读取 Archive/archive.json
    """
    path = get_archive_file_path(archive_filename)
    return _load_json_file(path, DEFAULT_ARCHIVE)