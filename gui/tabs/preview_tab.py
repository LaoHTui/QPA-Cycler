from typing import Any, Dict, List, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QAbstractItemView,
    QHeaderView,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
)

from ..ui_helpers import make_form_group, make_optional_date_row


def build_preview_tab(main) -> Tuple[QWidget, Dict[str, Any], List[QWidget], List[QWidget]]:
    """
    返回：
    - page
    - refs
    - source_editor_widgets：用于"单源编辑器禁用/启用"
    - run_block_widgets：用于"运行时禁用"
    """
    page = QWidget()
    layout = QVBoxLayout(page)

    preview_info_label = QLabel("预计处理数量：0")
    preview_info_label.setWordWrap(True)
    layout.addWidget(preview_info_label)

    # =========================
    # 工具栏：搜索 + 按钮
    # =========================
    toolbar = QWidget()
    toolbar_layout = QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(0, 0, 0, 0)

    btn_select_all_preview = QPushButton("全选")
    btn_clear_all_preview = QPushButton("清空所有选择")
    btn_clear_all_overrides = QPushButton("清除所有覆盖配置")
    btn_sort_preview = QPushButton("文件排序")
    btn_restore_preview = QPushButton("恢复命名")
    btn_export_raw = QPushButton("导出原始数据")

    preview_search_edit = QLineEdit()
    preview_search_edit.setPlaceholderText("搜索编号 / 文件名 / 路径")

    toolbar_layout.addWidget(btn_select_all_preview)
    toolbar_layout.addWidget(btn_clear_all_preview)
    toolbar_layout.addWidget(btn_clear_all_overrides)
    toolbar_layout.addWidget(btn_sort_preview)
    toolbar_layout.addWidget(btn_restore_preview)
    toolbar_layout.addWidget(btn_export_raw)
    toolbar_layout.addStretch(1)
    toolbar_layout.addWidget(QLabel("搜索："))
    toolbar_layout.addWidget(preview_search_edit, 1)

    layout.addWidget(toolbar)

    splitter = QSplitter(Qt.Horizontal)
    layout.addWidget(splitter, 1)

    # =========================
    # 左侧：文件预览表
    # =========================
    left = QWidget()
    left_layout = QVBoxLayout(left)

    source_table = QTableWidget(0, 6)
    source_table.setHorizontalHeaderLabels(["勾选", "编号", "文件名", "覆盖", "覆盖摘要", "路径"])
    source_table.itemChanged.connect(main.on_preview_table_item_changed)
    source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    source_table.setSelectionMode(QAbstractItemView.SingleSelection)
    source_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    source_table.setAlternatingRowColors(True)
    source_table.setWordWrap(False)
    source_table.verticalHeader().setVisible(False)

    header = source_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(4, QHeaderView.Stretch)
    header.setSectionResizeMode(5, QHeaderView.Stretch)

    left_layout.addWidget(source_table)

    splitter.addWidget(left)

    # =========================
    # 右侧：单源覆盖编辑器
    # =========================
    right_scroll, editor_refs, source_editor_widgets = build_source_editor_panel(main)

    splitter.addWidget(right_scroll)
    splitter.setStretchFactor(0, 3)
    splitter.setStretchFactor(1, 2)
    splitter.setSizes([1100, 700])

    refs: Dict[str, Any] = {
        "preview_info_label": preview_info_label,
        "btn_select_all_preview": btn_select_all_preview,
        "btn_clear_all_preview": btn_clear_all_preview,
        "btn_clear_all_overrides": btn_clear_all_overrides,
        "source_table": source_table,
        "btn_sort_preview": btn_sort_preview,
        "btn_restore_preview": btn_restore_preview,
        "btn_export_raw": btn_export_raw,
        "preview_search_edit": preview_search_edit,
    }
    refs.update(editor_refs)

    run_block_widgets: List[QWidget] = [
        btn_select_all_preview,
        btn_clear_all_preview,
        btn_clear_all_overrides,
        btn_sort_preview,
        btn_restore_preview,
        btn_export_raw,
    ]

    return page, refs, source_editor_widgets, run_block_widgets


def build_source_editor_panel(main) -> Tuple[QScrollArea, Dict[str, Any], List[QWidget]]:
    content = QWidget()
    layout = QVBoxLayout(content)

    source_title_label = QLabel("当前源：未选择")
    source_title_label.setWordWrap(True)

    source_summary_label = QLabel("覆盖摘要：默认配置")
    source_summary_label.setWordWrap(True)

    source_hint_label = QLabel(
        "说明：单源覆盖只保存与主界面不同的全局字段。\n"
        "当前支持：开始日期、结束日期、移除上限值、移除最大值数量。\n"
        "方法开关统一由主界面控制，不会被单源覆盖。"
    )
    source_hint_label.setWordWrap(True)

    layout.addWidget(source_title_label)
    layout.addWidget(source_summary_label)
    layout.addWidget(source_hint_label)

    # =========================
    # 单源覆盖控件
    # =========================
    src_start_date_check = QCheckBox("启用开始日期")
    src_start_date_edit = QDateEdit()
    src_start_date_edit.setDisplayFormat("yyyy-MM-dd")
    src_start_date_edit.setCalendarPopup(True)
    src_start_date_edit.setDate(QDate.currentDate())

    src_end_date_check = QCheckBox("启用结束日期")
    src_end_date_edit = QDateEdit()
    src_end_date_edit.setDisplayFormat("yyyy-MM-dd")
    src_end_date_edit.setCalendarPopup(True)
    src_end_date_edit.setDate(QDate.currentDate())

    src_remove_upper_limit_check = QCheckBox("移除上限值（remove_upper_limit）")
    src_remove_max_value_spin = QSpinBox()
    src_remove_max_value_spin.setRange(0, 10_000_000)

    global_override_group = make_form_group("单源全局覆盖", [
        ("开始日期", make_optional_date_row(src_start_date_check, src_start_date_edit)),
        ("结束日期", make_optional_date_row(src_end_date_check, src_end_date_edit)),
        ("", src_remove_upper_limit_check),
        ("移除最大值数量", src_remove_max_value_spin),
    ])

    btn_save_source_override = QPushButton("保存覆盖")
    btn_clear_source_override = QPushButton("清除覆盖")
    btn_reload_source_override = QPushButton("重载当前")

    btn_row = QWidget()
    btn_layout = QHBoxLayout(btn_row)
    btn_layout.setContentsMargins(0, 0, 0, 0)
    btn_layout.addWidget(btn_save_source_override)
    btn_layout.addWidget(btn_clear_source_override)
    btn_layout.addWidget(btn_reload_source_override)
    btn_layout.addStretch(1)

    layout.addWidget(global_override_group)
    layout.addWidget(btn_row)
    layout.addStretch(1)

    refs: Dict[str, Any] = {
        "source_title_label": source_title_label,
        "source_summary_label": source_summary_label,
        "source_hint_label": source_hint_label,

        "src_start_date_check": src_start_date_check,
        "src_start_date_edit": src_start_date_edit,
        "src_end_date_check": src_end_date_check,
        "src_end_date_edit": src_end_date_edit,
        "src_remove_upper_limit_check": src_remove_upper_limit_check,
        "src_remove_max_value_spin": src_remove_max_value_spin,

        "btn_save_source_override": btn_save_source_override,
        "btn_clear_source_override": btn_clear_source_override,
        "btn_reload_source_override": btn_reload_source_override,
    }

    source_editor_widgets: List[QWidget] = [
        src_start_date_check,
        src_start_date_edit,
        src_end_date_check,
        src_end_date_edit,
        src_remove_upper_limit_check,
        src_remove_max_value_spin,
        btn_save_source_override,
        btn_clear_source_override,
        btn_reload_source_override,
    ]

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll, refs, source_editor_widgets