from typing import Any, Dict, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


def build_results_tab(main) -> Tuple[QWidget, Dict[str, Any]]:
    """
    结果页：只保留主表 + 工具栏
    详细信息改为右键弹窗，不在主界面中渲染
    """
    page = QWidget()
    layout = QVBoxLayout(page)

    results_info_label = QLabel("结果：0")
    results_info_label.setWordWrap(True)
    layout.addWidget(results_info_label)

    # =========================
    # 工具栏
    # =========================
    toolbar = QWidget()
    toolbar_layout = QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(0, 0, 0, 0)

    btn_refresh_results = QPushButton("刷新结果")
    btn_export_csv = QPushButton("导出CSV")


    results_search_edit = QLineEdit()
    results_search_edit.setPlaceholderText("搜索源名 / 文件名 / 结果摘要")

    results_sort_combo = QComboBox()
    results_sort_combo.addItems([
        "按源号升序",
        "按源名升序",
        "按LSP置信度降序",
        "按WWZ置信度降序",
        "按状态排序",
    ])

    results_status_filter_combo = QComboBox()
    results_status_filter_combo.addItems([
        "全部",
        "processing",
        "done",
        "skipped",
        "failed",
    ])

    toolbar_layout.addWidget(btn_refresh_results)
    toolbar_layout.addWidget(btn_export_csv)
    toolbar_layout.addWidget(QLabel("排序："))
    toolbar_layout.addWidget(results_sort_combo)
    toolbar_layout.addWidget(QLabel("状态："))
    toolbar_layout.addWidget(results_status_filter_combo)
    toolbar_layout.addWidget(QLabel("搜索："))
    toolbar_layout.addWidget(results_search_edit, 1)

    layout.addWidget(toolbar)

    # =========================
    # 主结果表
    # =========================
    results_table = QTableWidget(0, 9)
    results_table.setHorizontalHeaderLabels([
        "源号",
        "源名",
        "状态",
        "LSP方法结果",
        "LSP置信度",
        "JV方法结果",
        "DCF方法结果",
        "WWZ方法结果",
        "WWZ置信度",
    ])
    results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
    results_table.setSelectionMode(QAbstractItemView.SingleSelection)
    results_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    results_table.setAlternatingRowColors(True)
    results_table.setWordWrap(False)
    results_table.verticalHeader().setVisible(False)
    results_table.setContextMenuPolicy(Qt.CustomContextMenu)

    header = results_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(3, QHeaderView.Stretch)
    header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
    header.setSectionResizeMode(5, QHeaderView.Stretch)
    header.setSectionResizeMode(6, QHeaderView.Stretch)
    header.setSectionResizeMode(7, QHeaderView.Stretch)
    header.setSectionResizeMode(8, QHeaderView.ResizeToContents)

    # 先禁用系统排序，避免插入时频繁重排
    results_table.setSortingEnabled(False)

    layout.addWidget(results_table, 1)

    refs: Dict[str, Any] = {
        "results_info_label": results_info_label,
        "btn_refresh_results": btn_refresh_results,
        "btn_export_csv": btn_export_csv,
        "results_search_edit": results_search_edit,
        "results_sort_combo": results_sort_combo,
        "results_status_filter_combo": results_status_filter_combo,
        "results_table": results_table,
    }

    return page, refs