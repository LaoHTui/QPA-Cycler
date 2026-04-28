from typing import Any, Dict, Optional, Tuple

from File_operations import get_csv_data as gcd, get_txt_data as gtd


def _parse_date_value(date_value):
    """
    把 JSON 里的日期字符串/列表转成 tuple(int, int, int)。
    支持：
    - None
    - "2024,1,1"
    - [2024, 1, 1]
    """
    if date_value is None:
        return None

    if isinstance(date_value, (list, tuple)):
        if len(date_value) != 3:
            return None
        try:
            return tuple(int(x) for x in date_value)
        except (TypeError, ValueError):
            return None

    if isinstance(date_value, str):
        parts = [p.strip() for p in date_value.split(",")]
        if len(parts) != 3:
            return None
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            return None

    return None


def extract_date_range(config: Dict[str, Any]):
    """
    从 config 里提取 start_date / end_date
    """
    global_cfg = config.get("global", {})
    start_date = _parse_date_value(global_cfg.get("start_date"))
    end_date = _parse_date_value(global_cfg.get("end_date"))
    return start_date, end_date


def load_csv_source(file_path: str, state: Dict[str, Any], config: Dict[str, Any]):
    """
    读取 CSV 数据
    返回：
    source_name, julian_dates, photon_fluxes, photon_fluxes_err, remove_upper_limit_mask
    """
    global_cfg = config.get("global", {})
    start_date, end_date = extract_date_range(config)

    return gcd.get_csv_data(
        file_path,
        state,
        remove_upper_limit=global_cfg.get("remove_upper_limit", True),
        start_date=start_date,
        end_date=end_date,
        remove_max_value_numbers=global_cfg.get("remove_max_value_numbers", 0)
    )


def load_txt_source(file_path: str, state: Dict[str, Any]):
    """
    读取 TXT 数据
    返回：
    source_name, julian_dates, photon_fluxes, photon_fluxes_err
    """
    return gtd.get_txt_data(file_path, state)


def load_source_data(file_path: str, file_type: str, state: Dict[str, Any], config: Dict[str, Any]):
    """
    通用读取入口
    """
    if file_type == "csv":
        return load_csv_source(file_path, state, config)
    if file_type == "txt":
        return load_txt_source(file_path, state)
    raise ValueError(f"不支持的 file_type: {file_type}")