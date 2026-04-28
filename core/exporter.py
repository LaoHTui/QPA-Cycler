import os
from typing import Any, Dict

from openpyxl.styles.builtins import output

import save2docx


def _format_source_name(filename: str) -> str:
    """
    按你原来的逻辑把文件名整理得更美观一点。
    例如 10_xxx.csv -> 10_xxx
    """
    base = os.path.splitext(filename)[0]
    parts = base.split("_")
    if len(parts) >= 2:
        return f"{parts[0]}_{parts[1]}"
    return base


def export_docx_report(
    data_path: str,
    state_dict_filename: str,
    json_params_filename: str = "config",
    docx_output_path: str = None,
    output_filename: str = "report.docx"
):
    """
    导出 docx 报告
    """
    if docx_output_path is None:
        docx_output_path = data_path

    os.makedirs(docx_output_path, exist_ok=True)

    # 这里做一下文件名归一化，避免传入 config.json 导致重复后缀
    json_params_filename = os.path.splitext(os.path.basename(json_params_filename))[0]

    save2docx.save2docx(
        data_path=data_path,
        state_dict_filename=state_dict_filename,
        json_params_filename=json_params_filename,
        docx_output_path=docx_output_path,
        output_filename= output_filename,
    )