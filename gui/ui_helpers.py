from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QLineEdit,
    QWidget,
)


def set_combo_text(combo: QComboBox, text: str, fallback_index: int = 0):
    text = "" if text is None else str(text)
    idx = combo.findText(text)
    if idx >= 0:
        combo.setCurrentIndex(idx)
    elif combo.count() > 0:
        combo.setCurrentIndex(fallback_index)


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