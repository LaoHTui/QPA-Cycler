import copy
import json
import os
import re
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QDate,Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)
from .constants import DEFAULT_CONFIG_PATH, SOURCE_OVERRIDE_GLOBAL_KEYS


def default_config() -> Dict[str, Any]:
    return {
        "gen_light_plot": True,
        "global": {
            "mode": "customize",
            "file_numbers": -1,
            "rerun": True,
            "folder_path": "",
            "output_path": "",
            "state_filename": "state",
            "file_type": "csv",
            "export_docx": True,
            "docx_name":"Running Results",
            "selected_source_numbers": [],
            "use_selected_source_numbers": False,
            "min_points_per_cycle":8,
            "constant_flux": False,
            "constant_flux_values" : 2.0
        },
        "customize": {
            "DCF": False,
            "DCF_Plot": False,
            "Jurkevich": False,
            "JV_Plot": False,
            "LSP": True,
            "LSP_Plot": True,
            "WWZ": False,
            "WWZ_Plot": False,
            "jv_params": {
                "test_periods_start": 100,
                "test_periods_end": 3000,
                "test_periods_step": 10,
                "m_bins": 2,
                "plot_mode": "save",
            },
            "dcf_params": {
                "delta_tau": 3,
                "c": 10,
                "max_tau": 2000,
                "distance": 5,
                "plot_mode": "save",
            },
            "beta_params": {
                "beta_calculate": True,
                "default_beta": 0.9,
                "method": "psresp",
                "beta_start": 0.1,
                "beta_end": 2.1,
                "beta_step": 0.1,
                "M": 1000,
                "n_jobs": -1,
                "plot": True,
                "n_bins": 6,
                "plot_mode": "save",
            },
            "lsp_params": {
                "lsp_mode":"lsp",
                "divide_freq_step": 10,
                "sig_threshold": 0.997,
                "top_n": 3,
                "MC": True,
                "M": 10000,
                "n_jobs": -1,
                "plot_params": {
                    "plot_mode": "save",
                    "time_axis_mode": "ym",
                    "time_input_format": "jd",
                },
            },
            "wwz_params": {
                "c": 0.0125,
                "p_start": 100,
                "p_end": 2000,
                "divide_freq_step": 10,
                "tau_number": 1000,
                "z_height": 20000,
                "MC": False,
                "M": 10000,
                "n_jobs": -1,
                "sig_threshold": 0.997,
                "top_n": 3,
                "plot_params": {
                    "plot_mode": "save",
                    "time_scale": "JD",
                    "peak_prominence": 3,
                    "use_log_scale_period": True,
                },
            },
        },
        "source_overrides": {},
    }


def sanitize_source_override(override: Dict[str, Any]) -> Dict[str, Any]:
    """
    只保留单源覆盖里允许的字段。
    现在只允许 global 里的日期/清洗字段。
    """
    if not isinstance(override, dict):
        return {}

    out: Dict[str, Any] = {}

    global_part = override.get("global", {})
    if isinstance(global_part, dict):
        clean_global = {}
        for k in SOURCE_OVERRIDE_GLOBAL_KEYS:
            if k in global_part:
                clean_global[k] = copy.deepcopy(global_part[k])
        if clean_global:
            out["global"] = clean_global

    return out


def sanitize_source_overrides(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    if not isinstance(data, dict):
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for k, v in data.items():
        clean = sanitize_source_override(v)
        if clean:
            out[str(k)] = clean
    return out


def json_load(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def json_save(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def normalize_json_path(path_text: str) -> str:
    path_text = (path_text or "").strip()
    if not path_text:
        return DEFAULT_CONFIG_PATH
    return path_text if path_text.lower().endswith(".json") else f"{path_text}.json"


def config_base_from_path(path_text: str) -> str:
    return os.path.splitext(normalize_json_path(path_text))[0]


def bool_value(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(v, (int, float)):
        return bool(v)
    return default


def int_value(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def float_value(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except Exception:
        return default


def parse_date_from_config(v: Any) -> Optional[QDate]:
    if v is None:
        return None
    try:
        if isinstance(v, str):
            parts = [x.strip() for x in v.split(",")]
            if len(parts) != 3:
                return None
            y, m, d = map(int, parts)
            return QDate(y, m, d)

        if isinstance(v, (list, tuple)) and len(v) == 3:
            y, m, d = map(int, v)
            return QDate(y, m, d)
    except Exception:
        return None
    return None


def normalize_optional_date_value(v: Any) -> Optional[str]:
    qdate = parse_date_from_config(v)
    if qdate is None:
        return None
    return f"{qdate.year()},{qdate.month()},{qdate.day()}"


def date_to_config_text(date_edit: QDateEdit) -> str:
    d = date_edit.date()
    return f"{d.year()},{d.month()},{d.day()}"


def set_optional_date_widgets(check_box: QCheckBox, date_edit: QDateEdit, value: Any):
    qdate = parse_date_from_config(value)
    if qdate is not None:
        check_box.setChecked(True)
        date_edit.setEnabled(True)
        date_edit.setDate(qdate)
    else:
        check_box.setChecked(False)
        date_edit.setEnabled(False)
        date_edit.setDate(QDate.currentDate())


def get_optional_date_value(check_box: QCheckBox, date_edit: QDateEdit) -> Optional[str]:
    if not check_box.isChecked():
        return None
    return date_to_config_text(date_edit)


def make_path_row(edit: QLineEdit, browse_btn: QPushButton, extra_buttons: Optional[List[QPushButton]] = None) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    layout.addWidget(browse_btn)
    if extra_buttons:
        for b in extra_buttons:
            layout.addWidget(b)
    return w


def make_check_row(*checks: QCheckBox) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    for c in checks:
        layout.addWidget(c)
    layout.addStretch(1)
    return w


def make_optional_date_row(check_box: QCheckBox, date_edit: QDateEdit) -> QWidget:
    w = QWidget()
    layout = QHBoxLayout(w)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(check_box)
    layout.addWidget(date_edit)
    layout.addStretch(1)
    check_box.toggled.connect(date_edit.setEnabled)
    date_edit.setEnabled(check_box.isChecked())
    return w


def make_form_group(title: str, rows: List[tuple]) -> QGroupBox:
    box = QGroupBox(title)
    form = QFormLayout(box)
    form.setLabelAlignment(Qt.AlignRight)
    for label, widget in rows:
        form.addRow(label, widget)
    return box


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def flatten_override_dict(data: Dict[str, Any], prefix: str = "") -> List[str]:
    out = []
    for k, v in data.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            out.extend(flatten_override_dict(v, key))
        else:
            out.append(f"{key}={v}")
    return out


def summarize_override(override: Dict[str, Any], max_items: int = 6) -> str:
    if not override:
        return "默认配置"
    items = flatten_override_dict(override)
    if not items:
        return "默认配置"
    if len(items) > max_items:
        return "；".join(items[:max_items]) + "；..."
    return "；".join(items)


def set_combo_text(combo: QComboBox, text: str, fallback_index: int = 0):
    text = "" if text is None else str(text)
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    elif combo.count() > 0:
        combo.setCurrentIndex(fallback_index)


def ensure_json_suffix(filename: str) -> str:
    filename = str(filename)
    return filename if filename.endswith(".json") else f"{filename}.json"

