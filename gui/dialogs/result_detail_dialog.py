import json
import os
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView
)



class ResultDetailDialog(QDialog):
    def __init__(self, parent=None, payload: Optional[Dict[str, Any]] = None, show_images: bool = True):
        super().__init__(parent)
        self.payload = payload or {}
        self.show_images = show_images  # 新增：控制是否显示图片相关的栏目
        self.setWindowTitle(f"结果详情 - {self.payload.get('source_name', '-')}")
        self.resize(1400, 920)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self.image_cards: Dict[str, Dict[str, Any]] = {}

        self._build_ui()
        self._fill_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        self.title_label = QLabel("当前结果：-")
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.meta_label = QLabel("元信息：-")
        self.meta_label.setWordWrap(True)
        root.addWidget(self.title_label)
        root.addWidget(self.meta_label)

        self.form_group = QGroupBox("关键摘要")
        form_layout = QFormLayout(self.form_group)
        
        self.lbl_source_name = QLabel("-")
        self.lbl_source_index = QLabel("-")
        self.lbl_status = QLabel("-")
        self.lbl_matched_file = QLabel("-")
        self.lbl_best_method = QLabel("-")
        self.lbl_best_conf = QLabel("-")
        self.lbl_date_range = QLabel("-")
        
        form_layout.addRow("源名称:", self.lbl_source_name)
        form_layout.addRow("源编号:", self.lbl_source_index)
        form_layout.addRow("状态:", self.lbl_status)
        form_layout.addRow("匹配文件:", self.lbl_matched_file)
        form_layout.addRow("最佳方法:", self.lbl_best_method)
        form_layout.addRow("置信度:", self.lbl_best_conf)
        form_layout.addRow("日期范围:", self.lbl_date_range)
        
        root.addWidget(self.form_group)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        # ==============
        # 概览页
        # ==============
        overview_page = QWidget()
        overview_layout = QVBoxLayout(overview_page)

        self.method_table = QTableWidget(0, 4)
        self.method_table.setHorizontalHeaderLabels([
            "方法", "结果摘要", "置信度/评分", "图片路径",
        ])

        # 【关键修改 1】：如果是预览模式，隐藏“图片路径”这一整列
        if not self.show_images:
            self.method_table.setColumnHidden(3, True)

        self.method_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.method_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.method_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.method_table.setAlternatingRowColors(True)
        self.method_table.verticalHeader().setVisible(False)

        mh = self.method_table.horizontalHeader()
        mh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(1, QHeaderView.Stretch)
        mh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        mh.setSectionResizeMode(3, QHeaderView.Stretch)

        overview_layout.addWidget(self.method_table)
        self.tabs.addTab(overview_page, "概览")

        # ==============
        # 图片页 (【关键修改 2】：条件添加)
        # ==============
        if self.show_images:
            image_page = QWidget()
            image_layout = QVBoxLayout(image_page)
            self.image_scroll = QScrollArea()
            self.image_scroll.setWidgetResizable(True)
            self.image_container = QWidget()
            self.image_container_layout = QVBoxLayout(self.image_container)
            self.image_container_layout.setAlignment(Qt.AlignTop)
            self.image_scroll.setWidget(self.image_container)
            image_layout.addWidget(self.image_scroll)
            self.tabs.addTab(image_page, "图片")
        else:
            # 即使不添加 Tab，我们也给 layout 赋个空值，防止 _fill_ui 报错
            self.image_container_layout = QVBoxLayout()

            # ==============
        # 原始数据页
        # ==============
        raw_page = QWidget()
        raw_layout = QVBoxLayout(raw_page)
        self.raw_edit = QPlainTextEdit()
        self.raw_edit.setReadOnly(True)
        raw_layout.addWidget(self.raw_edit)
        self.tabs.addTab(raw_page, "原始数据")

        # ==============
        # 底部按钮
        # ==============
        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_open_output = QPushButton("打开输出目录")
        self.btn_copy_source = QPushButton("复制源名")
        self.btn_close = QPushButton("关闭")

        self.btn_open_output.clicked.connect(self._open_output_folder)
        self.btn_copy_source.clicked.connect(self._copy_source_name)
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_open_output)
        btn_layout.addWidget(self.btn_copy_source)
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_close)

        root.addWidget(btn_row)

        self.button_box = QDialogButtonBox()
        self.button_box.addButton(self.btn_close, QDialogButtonBox.RejectRole)

    def _fill_ui(self):
        source_name = self.payload.get("source_name", "-")
        source_index = self.payload.get("source_index", "-")
        status = self.payload.get("status", "-")
        matched_file = self.payload.get("matched_file", "-")
        best_method = self.payload.get("best_method", "-")
        best_conf = self.payload.get("best_confidence", "-")
        date_range = self.payload.get("date_range", "-")
        method_rows: List[Tuple[str, str, str, str]] = self.payload.get("method_rows", []) or []
        raw_payload = self.payload.get("raw_payload", {}) or {}

        self.title_label.setText(f"当前结果：{source_name}")
        self.meta_label.setText(
            f"状态：{status} | 源号：{source_index} | 匹配文件：{matched_file}"
        )

        self.lbl_source_name.setText(str(source_name))
        self.lbl_source_index.setText(str(source_index))
        self.lbl_status.setText(str(status))
        self.lbl_matched_file.setText(str(matched_file))
        self.lbl_best_method.setText(str(best_method))
        self.lbl_best_conf.setText(str(best_conf))
        self.lbl_date_range.setText(str(date_range))

        # 方法表
        self.method_table.setRowCount(len(method_rows))
        for row, (m, summary, conf_text, image_path) in enumerate(method_rows):
            vals = [m, summary, conf_text, image_path or "-"]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if col in (0, 2):
                    item.setTextAlignment(Qt.AlignCenter)
                self.method_table.setItem(row, col, item)

        # 图片区
        self.image_cards.clear()
        while self.image_container_layout.count():
            item = self.image_container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        for m, summary, conf_text, image_path in method_rows:
            card = self._create_image_card(m, image_path)
            self.image_cards[m] = card
            self.image_container_layout.addWidget(card["widget"])

        self.image_container_layout.addStretch(1)

        # 原始 JSON
        self.raw_edit.setPlainText(json.dumps(raw_payload, ensure_ascii=False, indent=4, default=str))

        # output_path
        output_path = self.payload.get("output_path", "")
        self.btn_open_output.setEnabled(bool(output_path))

    def _create_image_card(self, title: str, image_path: Optional[str]):
        box = QGroupBox(title)
        box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #444;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                background: #1e1e1e;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
        """)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(10, 12, 10, 10)
        layout.setSpacing(8)

        path_label = QLabel("图片路径：-")
        path_label.setWordWrap(True)
        path_label.setStyleSheet("color: #cfcfcf;")

        info_label = QLabel("分辨率：-")
        info_label.setStyleSheet("color: #9aa0a6;")

        # 图像显示区：用 QScrollArea 保证完整可见
        image_scroll = QScrollArea()
        image_scroll.setWidgetResizable(True)
        image_scroll.setMinimumHeight(280)
        image_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #555;
                background: #111;
                border-radius: 6px;
            }
        """)

        image_label = QLabel("暂无图片")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("color: #ddd; background: #111;")
        image_label.setScaledContents(False)
        image_label.setWordWrap(True)
        image_label.setMinimumSize(1, 1)

        image_scroll.setWidget(image_label)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        open_btn = QPushButton("打开原图")
        open_btn.setEnabled(False)

        fit_btn = QPushButton("适应宽度")
        fit_btn.setEnabled(False)

        btn_layout.addWidget(fit_btn)
        btn_layout.addWidget(open_btn)
        btn_layout.addStretch(1)

        layout.addWidget(path_label)
        layout.addWidget(info_label)
        layout.addWidget(image_scroll, 1)
        layout.addWidget(btn_row)

        card = {
            "widget": box,
            "path_label": path_label,
            "info_label": info_label,
            "image_scroll": image_scroll,
            "image_label": image_label,
            "open_btn": open_btn,
            "fit_btn": fit_btn,
            "path": None,
            "pixmap": None,
            "title": title,
        }

        def _open():
            if image_path and os.path.exists(image_path):
                QDesktopServices.openUrl(QUrl.fromLocalFile(image_path))

        open_btn.clicked.connect(_open)

        def _fit_width():
            pixmap = card.get("pixmap")
            if pixmap is None or pixmap.isNull():
                return
            viewport_width = max(300, image_scroll.viewport().width() - 20)
            scaled = pixmap.scaledToWidth(viewport_width, Qt.SmoothTransformation)
            image_label.setPixmap(scaled)
            image_label.adjustSize()

        fit_btn.clicked.connect(_fit_width)

        self._set_card_image(card, image_path)

        return card

    def _set_card_image(self, card: Dict[str, Any], path: Optional[str]):
        path_label: QLabel = card["path_label"]
        info_label: QLabel = card["info_label"]
        image_label: QLabel = card["image_label"]
        open_btn: QPushButton = card["open_btn"]
        fit_btn: QPushButton = card["fit_btn"]

        card["path"] = path
        card["pixmap"] = None

        if not path or not os.path.exists(path):
            path_label.setText("图片路径：-")
            info_label.setText("分辨率：-")
            image_label.setText("暂无图片")
            image_label.setPixmap(QPixmap())
            open_btn.setEnabled(False)
            fit_btn.setEnabled(False)
            return

        path_label.setText(f"图片路径：{path}")

        pixmap = QPixmap(path)
        if pixmap.isNull():
            info_label.setText("分辨率：-")
            image_label.setText("图片加载失败")
            image_label.setPixmap(QPixmap())
            open_btn.setEnabled(False)
            fit_btn.setEnabled(False)
            return

        card["pixmap"] = pixmap
        info_label.setText(f"分辨率：{pixmap.width()} × {pixmap.height()}")
        open_btn.setEnabled(True)
        fit_btn.setEnabled(True)

        # 默认：按宽度自适应，但保持完整比例
        viewport = card["image_scroll"].viewport()
        target_width = max(300, viewport.width() - 20)
        scaled = pixmap.scaledToWidth(target_width, Qt.SmoothTransformation)
        image_label.setPixmap(scaled)
        image_label.adjustSize()

    def _open_output_folder(self):
        output_path = self.payload.get("output_path", "")
        if output_path and os.path.exists(output_path):
            QDesktopServices.openUrl(QUrl.fromLocalFile(output_path))

    def _copy_source_name(self):
        source_name = self.payload.get("source_name", "")
        if source_name:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(str(source_name))