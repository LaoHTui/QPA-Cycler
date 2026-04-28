import copy
import ctypes
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional
import shutil
import csv
from datetime import datetime

from gui.tabs.run_tab import build_run_tab
from gui.tabs.preview_tab import build_preview_tab
from gui.tabs.results_tab import build_results_tab
from File_operations.data_numbering import sort_files, restore_files

from PySide6.QtCore import Qt, QDate, QProcess, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QDoubleSpinBox,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from core.archive_manager import get_archive_file_path
from core.file_manager import parse_target_numbers, scan_numbered_files

from .constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_RUNNER_PATH,
    PROJECT_ROOT,
    RESULT_IMAGE_SPECS,
    SOURCE_OVERRIDE_GLOBAL_KEYS,
)
from .config_utils import (
    bool_value,
    config_base_from_path,
    date_to_config_text,
    deep_merge,
    default_config,
    float_value,
    flatten_override_dict,
    get_optional_date_value,
    int_value,
    json_load,
    json_save,
    normalize_json_path,
    normalize_optional_date_value,
    parse_date_from_config,
    sanitize_source_override,
    sanitize_source_overrides,
    set_optional_date_widgets,
    summarize_override,
    ensure_json_suffix,
)
from .ui_helpers import (
    make_check_row,
    make_form_group,
    make_optional_date_row,
    make_path_row,
    set_combo_text,
)
from .dialogs.result_detail_dialog import ResultDetailDialog
# =========================================================
# 主窗口
# =========================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QPA-Cycler")
        self.resize(1800, 1050)

        icon = QIcon("assets/app_v2.ico")
        self.setWindowIcon(icon)

        # 尝试设置更大的窗口图标
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("astrolightcurve.viewer")
        except Exception:
            pass

        self.current_config: Dict[str, Any] = default_config()
        self.current_config_path: str = DEFAULT_CONFIG_PATH
        self.source_overrides: Dict[str, Dict[str, Any]] = {}
        self.current_selected_num: Optional[str] = None
        self.current_selected_file_path: str = ""

        self.selected_preview_numbers: set[str] = set()
        self._preview_item_guard = False
        self.preview_effective_count = 0

        self._results_state_path_cached: str = ""
        self._results_state_mtime: float = -1.0
        self._results_state_cache: Dict[str, Any] = {}

        self._results_all_rows: List[Dict[str, Any]] = []
        self._results_visible_rows: List[Dict[str, Any]] = []

        self._results_fill_queue: List[Dict[str, Any]] = []
        self._results_fill_token: int = 0
        self._results_fill_chunk: int = 80

        self.current_result_selected_source: Optional[str] = None

        self.use_manual_source_selection = False

        self._process_finalized = False

        self.current_file_map: Dict[int, str] = {}
        self.current_sorted_numbers: List[int] = []

        self.process: Optional[QProcess] = None
        self.stop_requested: bool = False
        self.is_running: bool = False

        self.estimated_total: int = 0
        self.processed_count: int = 0
        self._loading_config: bool = False

        self.run_block_widgets: List[QWidget] = []
        self.source_editor_widgets: List[QWidget] = []

        self._build_ui()
        self._bind_events()

        # =====================================================
        # 结果查看 / 归档模块
        # =====================================================
        self.current_result_selected_source: Optional[str] = None
        self._results_row_cache: List[Dict[str, Any]] = []
        self._results_row_map: Dict[str, Dict[str, Any]] = {}
        self._image_path_cache: Dict[str, Dict[str, str]] = {}
        self._archive_index_cache: List[Dict[str, Any]] = []
        self._state_file_path: str = ""
        self._archive_file_path: str = ""
        self._detail_dialog_ref = None

        # 搜索防抖 timer
        self.results_filter_timer = QTimer(self)
        self.results_filter_timer.setSingleShot(True)
        self.results_filter_timer.setInterval(250)
        self.results_filter_timer.timeout.connect(self.apply_results_filter)

        self.preview_filter_timer = QTimer(self)
        self.preview_filter_timer.setSingleShot(True)
        self.preview_filter_timer.setInterval(250)
        self.preview_filter_timer.timeout.connect(self.apply_preview_filter)

        # 预览页 archive 缓存
        self._archive_cache: Dict[str, Any] = {}
        self._archive_cache_path: str = ""
        self._archive_cache_mtime: float = -1.0

        self._preview_all_rows: List[Dict[str, Any]] = []
        self._preview_visible_rows: List[Dict[str, Any]] = []

        # 运行中定时刷新
        self.results_refresh_timer = QTimer(self)
        self.results_refresh_timer.setInterval(3000)
        self.results_refresh_timer.timeout.connect(self._on_results_refresh_timer)

        if os.path.exists(DEFAULT_CONFIG_PATH):
            try:
                self.load_config_from_disk(DEFAULT_CONFIG_PATH)
            except Exception as e:
                QMessageBox.warning(self, "加载配置失败", f"读取默认 config.json 失败：\n{e}")
                self.current_config = default_config()
                self.load_config_to_ui(self.current_config)
                self.refresh_source_preview()
        else:
            self.current_config = default_config()
            self.load_config_to_ui(self.current_config)
            self.refresh_source_preview()


        self._set_running_state(False)

    def _attach_refs(self, refs: Dict[str, Any]):
        for k, v in refs.items():
            setattr(self, k, v)

    # =====================================================
    # UI
    # =====================================================

    def _register_run_block_widget(self, widget: QWidget):
        if widget is not None:
            self.run_block_widgets.append(widget)

    def _register_source_editor_widget(self, widget: QWidget):
        if widget is not None:
            self.source_editor_widgets.append(widget)

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        control_group = QGroupBox("全局控制")
        control_layout = QVBoxLayout(control_group)

        self.config_path_edit = QLineEdit()
        self.config_path_edit.setPlaceholderText("配置文件，例如：config.json")
        self.config_path_edit.setText(self.current_config_path)

        self.btn_browse_config = QPushButton("选择")
        self.btn_load_config = QPushButton("加载")
        self.btn_save_config = QPushButton("保存")

        config_row = make_path_row(
            self.config_path_edit,
            self.btn_browse_config,
            [self.btn_load_config, self.btn_save_config],
        )
        control_layout.addWidget(config_row)

        action_row_widget = QWidget()
        action_row = QHBoxLayout(action_row_widget)
        action_row.setContentsMargins(0, 0, 0, 0)

        self.btn_run = QPushButton("开始运行")
        self.btn_stop = QPushButton("停止")
        self.btn_refresh_preview = QPushButton("刷新预览")
        self.btn_open_output = QPushButton("打开输出目录")
        self.btn_clear_log = QPushButton("清空日志")

        self.btn_stop.setEnabled(False)

        action_row.addWidget(self.btn_run)
        action_row.addWidget(self.btn_stop)
        action_row.addWidget(self.btn_refresh_preview)
        action_row.addWidget(self.btn_open_output)
        action_row.addWidget(self.btn_clear_log)
        action_row.addStretch(1)

        control_layout.addWidget(action_row_widget)
        root_layout.addWidget(control_group)

        self._register_run_block_widget(self.config_path_edit)
        self._register_run_block_widget(self.btn_browse_config)
        self._register_run_block_widget(self.btn_load_config)
        self._register_run_block_widget(self.btn_save_config)
        self._register_run_block_widget(self.btn_refresh_preview)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, 1)




        # =========================
        # 第二层：使用 tabs/*.py 的 builder
        # =========================
        run_page, run_refs, run_block_widgets = build_run_tab(self)
        self._attach_refs(run_refs)
        for w in run_block_widgets:
            self._register_run_block_widget(w)
        self.tabs.addTab(run_page, "运行参数 / 运行日志")

        preview_page, preview_refs, source_editor_widgets, preview_run_block_widgets = build_preview_tab(self)
        self._attach_refs(preview_refs)
        for w in source_editor_widgets:
            self._register_source_editor_widget(w)
        for w in preview_run_block_widgets:
            self._register_run_block_widget(w)
        self.tabs.addTab(preview_page, "文件预览 / 单源覆盖 / 归档")

        if hasattr(self, "source_table") and self.source_table is not None:
            self.source_table.setContextMenuPolicy(Qt.CustomContextMenu)
            self.source_table.customContextMenuRequested.connect(self.on_preview_table_context_menu)
            self.source_table.doubleClicked.connect(self.on_preview_table_double_clicked)

        results_page, results_refs = build_results_tab(self)
        self._attach_refs(results_refs)
        self.tabs.addTab(results_page, "结果查看")

        self.statusBar().showMessage("就绪")

        self._register_run_block_widget(self.btn_select_all_preview)
        self._register_run_block_widget(self.btn_clear_all_preview)

        # ... 添加完毕所有 Tab 后，在 _build_ui 的最后一行添加：
        self.tabs.currentChanged.connect(self._on_tab_changed)

    def _on_tab_changed(self, index: int):
        """
        当切换标签页时触发
        """
        # 获取当前 Tab 的文本来判断最稳妥
        tab_text = self.tabs.tabText(index)

        if "预览" in tab_text:
            if hasattr(self, 'refresh_source_preview'):
                # print("[UI] 切换到预览页，自动执行刷新...")
                self.refresh_source_preview()

    def on_restore_preview_clicked(self):
        folder = self.folder_path_edit.text().strip()
        file_type = self.file_type_combo.currentText().strip()

        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "提示", "请先选择有效的输入目录。")
            return

        try:
            restore_files(folder, file_type)
            self.refresh_source_preview()
            QMessageBox.information(self, "完成", "恢复命名完成。")
        except Exception as e:
            QMessageBox.critical(self, "恢复失败", str(e))

    def on_sort_preview_clicked(self):
        folder = self.folder_path_edit.text().strip()
        file_type = self.file_type_combo.currentText().strip()

        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "提示", "请先选择有效的输入目录。")
            return

        try:
            sort_files(folder, file_type, start_num=1)
            self.refresh_source_preview()
            QMessageBox.information(self, "完成", "文件排序完成。")
        except Exception as e:
            QMessageBox.critical(self, "排序失败", str(e))

    def export_selected_raw_data(self):
        selected_nums = self.get_preview_selected_numbers()
        if not selected_nums:
            QMessageBox.information(self, "提示", "请先勾选要导出的源。")
            return

        target_dir = QFileDialog.getExistingDirectory(
            self,
            "选择导出文件夹",
            self.folder_path_edit.text().strip() or PROJECT_ROOT
        )
        if not target_dir:
            return

        success_count = 0
        failed_items = []

        try:
            for num in selected_nums:
                src_path = self._get_source_path_by_num(num)
                if not src_path or not os.path.exists(src_path):
                    failed_items.append(f"#{num}：源文件不存在")
                    continue

                try:
                    self._copy_raw_source(src_path, target_dir, num)
                    success_count += 1
                except Exception as e:
                    failed_items.append(f"#{num}：{e}")

            msg = f"导出完成，成功导出 {success_count} 个源。"
            if failed_items:
                msg += "\n\n失败项：\n" + "\n".join(failed_items[:20])

            QMessageBox.information(self, "导出完成", msg)
            self.statusBar().showMessage(f"原始数据导出完成：{success_count} 个", 5000)

        except Exception as e:
            QMessageBox.critical(self, "导出失败", str(e))

    # =====================================================
    # 预览页：读取 archive / 右键 / 双击详情
    # =====================================================

    def _load_archive_cache(self, reload_disk: bool = False) -> Dict[str, Any]:
        """
        只读取程序主目录 Archive/archive.json。
        使用 mtime 缓存，避免反复读大文件。
        """
        from core.archive_manager import get_archive_file_path
        from .config_utils import json_load
        archive_path = get_archive_file_path("archive")
        if not archive_path or not os.path.exists(archive_path):
            self._archive_cache = {}
            self._archive_cache_path = ""
            self._archive_cache_mtime = -1.0
            return {}

        try:
            mtime = os.path.getmtime(archive_path)
        except Exception:
            mtime = -1.0

        if (
                not reload_disk
                and self._archive_cache
                and self._archive_cache_path == archive_path
                and self._archive_cache_mtime == mtime
        ):
            return self._archive_cache

        data = json_load(archive_path)
        if not isinstance(data, dict):
            data = {}

        self._archive_cache = data
        self._archive_cache_path = archive_path
        self._archive_cache_mtime = mtime
        return data

    def _resolve_source_name_by_filename(self, local_filename: str, archive_data: Dict[str, Any]) -> Optional[str]:
        """
        根据文件名查找 Archive 中对应的 Source Key。
        匹配逻辑：在 processed_files 列表中寻找 local_filename 的索引，
        然后返回 source_names 列表中相同位置的名称。
        """
        if not local_filename:
            return None

        processed_files = archive_data.get("processed_files", [])
        source_names = archive_data.get("source_names", [])

        # 1. 精确匹配文件名全称
        if local_filename in processed_files:
            idx = processed_files.index(local_filename)
            if idx < len(source_names):
                return source_names[idx]

        # 2. 兜底匹配：只对比文件名部分（忽略可能存在的路径差异）
        local_base = os.path.basename(local_filename)
        for i, pf in enumerate(processed_files):
            if os.path.basename(pf) == local_base:
                if i < len(source_names):
                    return source_names[i]

        return None

    def _build_preview_detail_payload(self, source_name: str, source_result: Dict[str, Any],
                                      archive_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        构建预览页详情窗口所需的 Payload：
        这里我们故意不进行图片查找，只保留文字结果。
        """
        if not isinstance(source_result, dict):
            source_result = {}

        source_idx = self._extract_source_index(source_name)
        processed_files = archive_data.get("processed_files", []) or []

        matched_file = self._find_processed_file_for_source(source_name, processed_files)
        status = str(source_result.get("status", "-"))

        # 日期处理逻辑保持不变...
        def _date_text(v):
            if v is None: return "-"
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                try:
                    return f"{int(v[0]):04d}-{int(v[1]):02d}-{int(v[2]):02d}"
                except:
                    return str(v)
            return str(v)

        start_val = source_result.get("applied_start_date") or source_result.get("start_date")
        end_val = source_result.get("applied_end_date") or source_result.get("end_date")
        date_range = f"{_date_text(start_val)} ~ {_date_text(end_val)}"

        try:
            best_method, best_conf = self._best_method_info(source_result)
        except:
            best_method, best_conf = "-", None

        # --- 核心修改部分：不加载图片 ---
        method_rows = []
        for method_key in ["LSP", "Jurkevich", "DCF", "WWZ", "Beta"]:
            method_result = source_result.get(method_key)
            summary = self._method_summary_text(method_key, method_result)
            conf = self._method_confidence_value(method_key, method_result)

            # 这里原本是调用 self._find_method_image_path(...)
            # 现在我们直接传 None，这样预览窗口就不会去搜图片，也不会显示图片了
            image_path = None

            method_rows.append(
                (
                    method_key,
                    summary,
                    self._format_confidence_text(conf),
                    image_path,
                )
            )

        # 组织 Payload 结构
        payload = {
            "source_name": source_name,
            "source_index": source_idx if source_idx is not None else "-",
            "status": status,
            "matched_file": matched_file or "-",
            "best_method": best_method,
            "best_confidence": self._format_confidence_text(best_conf),
            "date_range": date_range,
            "method_rows": method_rows,
            "raw_payload": {
                "source_name": source_name,
                "source_index": source_idx,
                "status": status,
                "matched_file": matched_file,
                "archive_file_path": self._archive_cache_path,
                "merged_result": source_result,
            },
            "output_path": self.output_path_edit.text().strip(),
        }
        return payload

    def open_preview_source_detail_dialog(self, row: int):
        """
        预览页：通过文件名锁定归档中的数据并弹出详细窗口
        """
        # 从预览表格获取当前行的文件名（第2列）
        file_item = self.source_table.item(row, 2)
        if not file_item:
            return
        local_filename = file_item.text().strip()

        # 加载 Archive 缓存
        archive_data = self._load_archive_cache(reload_disk=False)
        if not archive_data:
            QMessageBox.information(self, "提示", "未找到 Archive 归档文件数据。")
            return

        # 查找匹配的 Key (source_name)
        matched_key = self._resolve_source_name_by_filename(local_filename, archive_data)

        if not matched_key:
            QMessageBox.information(self, "未找到结果", f"归档中没有文件 '{local_filename}' 的计算记录。")
            return

        # 提取结果
        results = archive_data.get("results", {}) or {}
        source_result = results.get(matched_key)

        if not source_result:
            # 如果在 processed_files 里但 results 里没有，可能是被跳过了
            skipped_sources = archive_data.get("skipped_sources", {}) or {}
            skipped_info = skipped_sources.get(local_filename)

            if skipped_info:
                # 构建一个简易的 skipped 状态显示
                source_result = {"source_name": matched_key, "status": "skipped"}
            else:
                QMessageBox.information(self, "未找到结果", f"'{local_filename}' 虽然在处理列表中，但没有结果数据。")
                return
        else:
            skipped_info = None

        # 构建标准的详细信息 Payload（复用结果页的代码逻辑）
        payload = self._build_preview_detail_payload(matched_key, source_result, archive_data)

        # 确保关键信息准确
        payload["matched_file"] = local_filename
        if skipped_info:
            payload["raw_payload"]["skipped_info"] = skipped_info

        dialog = ResultDetailDialog(self, payload, show_images=False)
        self._detail_dialog_ref = dialog
        dialog.exec()

    def on_preview_table_context_menu(self, pos):
        """
        文件预览页右键菜单优化
        """
        item = self.source_table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        file_item = self.source_table.item(row, 2)
        local_filename = file_item.text().strip() if file_item else "未知文件名"

        menu = QMenu(self)
        act_detail = menu.addAction("查看归档详细信息")
        act_copy_file = menu.addAction("复制文件名")
        act_copy_source = menu.addAction("复制源名")

        chosen = menu.exec(self.source_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_detail:
            self.open_preview_source_detail_dialog(row)
        elif chosen == act_copy_file:
            QApplication.clipboard().setText(local_filename)
            self.statusBar().showMessage(f"已复制文件名: {local_filename}", 2000)
        elif chosen == act_copy_source:
            # 尝试获取源名（去掉后缀）
            pure_name = os.path.splitext(local_filename)[0]
            QApplication.clipboard().setText(pure_name)
            self.statusBar().showMessage(f"已复制源名: {pure_name}", 2000)

    def on_preview_table_double_clicked(self, index):
        if not index.isValid():
            return
        self.open_preview_source_detail_dialog(index.row())



    def _get_source_path_by_num(self, num: int) -> str:
        for row in range(self.source_table.rowCount()):
            num_item = self.source_table.item(row, 1)
            path_item = self.source_table.item(row, 5)
            if num_item is None or path_item is None:
                continue
            try:
                if int(num_item.text()) == int(num):
                    return path_item.text().strip()
            except Exception:
                continue
        return ""

    def _copy_raw_source(self, src_path: str, target_dir: str, num: int):
        base_name = os.path.basename(src_path.rstrip(os.sep))
        dst_path = os.path.join(target_dir, base_name)

        # 如果目标已存在，避免覆盖
        if os.path.exists(dst_path):
            name, ext = os.path.splitext(base_name)
            dst_path = os.path.join(target_dir, f"{num}_{name}{ext}")

            # 再次防重名
            dst_path = self._make_unique_path(dst_path)

        if os.path.isdir(src_path):
            shutil.copytree(src_path, dst_path)
        else:
            shutil.copy2(src_path, dst_path)

    def _make_unique_path(self, path: str) -> str:
        if not os.path.exists(path):
            return path

        base, ext = os.path.splitext(path)
        i = 1
        while True:
            new_path = f"{base}_{i}{ext}"
            if not os.path.exists(new_path):
                return new_path
            i += 1


    def _wrap_scroll(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_run_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter, 1)

        param_scroll = self._build_parameter_panel()
        log_panel = self._build_log_panel()

        splitter.addWidget(param_scroll)
        splitter.addWidget(log_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 1400])

        return page



    def _build_log_panel(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.status_label = QLabel("就绪")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setMaximumBlockCount(30000)
        layout.addWidget(self.log_edit, 1)

        return page

    def apply_results_filter(self):
        """
        只在内存缓存里做过滤和排序，不重新读磁盘。
        """
        rows = list(self._results_all_rows)

        query = self.results_search_edit.text().strip().lower()
        status_filter = self.results_status_filter_combo.currentText().strip()
        sort_mode = self.results_sort_combo.currentText().strip()

        if query:
            rows = [r for r in rows if query in r.get("search_text", "")]

        if status_filter != "全部":
            rows = [r for r in rows if r.get("status", "") == status_filter]

        if sort_mode == "按源号升序":
            rows.sort(key=lambda r: (
                r["source_index"] is None,
                r["source_index"] if r["source_index"] is not None else 10 ** 12,
                str(r["source_name"]).lower(),
            ))
        elif sort_mode == "按源名升序":
            rows.sort(key=lambda r: str(r["source_name"]).lower())
        elif sort_mode == "按LSP置信度降序":
            def lsp_conf_sort_key(r):
                conf = r.get("lsp_conf")
                if conf is None or conf == "-":
                    return (True, 0)
                try:
                    return (False, -float(conf))
                except (ValueError, TypeError):
                    return (True, 0)

            rows.sort(key=lsp_conf_sort_key)
        elif sort_mode == "按WWZ置信度降序":
            def wwz_conf_sort_key(r):
                conf = r.get("wwz_conf")
                if conf is None or conf == "-":
                    return (True, 0)
                try:
                    return (False, -float(conf))
                except (ValueError, TypeError):
                    return (True, 0)

            rows.sort(key=wwz_conf_sort_key)
        elif sort_mode == "按状态排序":
            status_order = {"done": 0, "processing": 1, "skipped": 2, "failed": 3}
            rows.sort(key=lambda r: (
                status_order.get(r.get("status", ""), 99),
                r["source_index"] is None,
                r["source_index"] if r["source_index"] is not None else 10 ** 12,
                str(r["source_name"]).lower(),
            ))

        self._results_visible_rows = rows

        self.results_info_label.setText(
            f"结果数：{len(rows)} / 缓存总数：{len(self._results_all_rows)}"
        )

        self._show_results_rows(rows)

    def apply_preview_filter(self):
        """
        预览页搜索过滤
        """
        rows = list(self._preview_all_rows)
        query = self.preview_search_edit.text().strip().lower()

        if query:
            rows = [r for r in rows if query in r.get("search_text", "")]

        self._preview_visible_rows = rows
        self._show_preview_rows(rows)

    def _build_preview_row_cache(self):
        """
        构建预览页的行缓存，用于搜索
        """
        rows = []
        for row_idx in range(self.source_table.rowCount()):
            num_item = self.source_table.item(row_idx, 1)
            file_item = self.source_table.item(row_idx, 2)
            path_item = self.source_table.item(row_idx, 5)
            check_item = self.source_table.item(row_idx, 0)

            if not num_item or not file_item:
                continue

            num_str = num_item.text()
            file_str = file_item.text()
            path_str = path_item.text() if path_item else ""
            is_checked = check_item.checkState() == Qt.Checked if check_item else False

            search_text = f"{num_str} {file_str} {path_str}".lower()

            rows.append({
                "row_index": row_idx,
                "number": num_str,
                "filename": file_str,
                "path": path_str,
                "is_checked": is_checked,
                "search_text": search_text,
            })

        self._preview_all_rows = rows
        self._preview_visible_rows = rows

    def _show_preview_rows(self, rows: List[Dict[str, Any]]):
        """
        显示过滤后的预览行（通过隐藏/显示行实现）
        """
        visible_row_indices = {r["row_index"] for r in rows}

        self.source_table.blockSignals(True)
        for row_idx in range(self.source_table.rowCount()):
            self.source_table.setRowHidden(row_idx, row_idx not in visible_row_indices)
        self.source_table.blockSignals(False)

        shown_count = len(rows)
        total_count = len(self._preview_all_rows)
        self.preview_info_label.setText(f"预计处理数量：{shown_count} / 总数：{total_count}")

    # ... existing code ...


    def _show_results_rows(self, rows: List[Dict[str, Any]]):
        self.results_table.blockSignals(True)
        self.results_table.setUpdatesEnabled(False)
        self.results_table.setSortingEnabled(False)

        self.results_table.clearContents()
        self.results_table.setRowCount(0)

        self._results_fill_queue = list(rows)
        self._results_fill_token += 1
        token = self._results_fill_token

        self._fill_results_table_batch(token)

    def _fill_results_table_batch(self, token: int):
        if token != self._results_fill_token:
            return

        batch = self._results_fill_queue[:self._results_fill_chunk]
        self._results_fill_queue = self._results_fill_queue[self._results_fill_chunk:]

        start_row = self.results_table.rowCount()
        self.results_table.setRowCount(start_row + len(batch))

        for i, rowdata in enumerate(batch):
            row = start_row + i

            values = [
                rowdata.get("source_index") if rowdata.get("source_index") is not None else "-",
                rowdata.get("source_name", "-"),
                rowdata.get("status", "-"),
                rowdata.get("lsp_result", "-"),
                rowdata.get("lsp_conf", "-"),
                rowdata.get("jv_result", "-"),
                rowdata.get("dcf_result", "-"),
                rowdata.get("wwz_result", "-"),
                rowdata.get("wwz_conf", "-"),
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, rowdata.get("source_name", ""))

                if col in (0, 2, 4, 8):
                    item.setTextAlignment(Qt.AlignCenter)

                self.results_table.setItem(row, col, item)

        if self._results_fill_queue:
            QTimer.singleShot(0, lambda tok=token: self._fill_results_table_batch(tok))
        else:
            self.results_table.blockSignals(False)
            self.results_table.setUpdatesEnabled(True)

    def _build_results_row_cache(self, state_dict: Dict[str, Any]):
        """
        从当前 state 构建缓存：
        - 搜索直接查这个缓存
        - 排序直接查这个缓存
        - 不在这里查图片，避免卡顿
        """
        state_dict = state_dict or {}
        results = state_dict.get("results", {}) or {}
        skipped_sources = state_dict.get("skipped_sources", {}) or {}
        processed_files = state_dict.get("processed_files", []) or []

        rows: List[Dict[str, Any]] = []
        row_map: Dict[str, Dict[str, Any]] = {}

        # 正常 results
        if isinstance(results, dict):
            for source_name, source_result in results.items():
                if not isinstance(source_result, dict):
                    source_result = {}

                best_method, best_conf = self._best_method_info(source_result)

                lsp_txt = self._method_summary_text("LSP", source_result.get("LSP"))
                jv_txt = self._method_summary_text("Jurkevich", source_result.get("Jurkevich"))
                dcf_txt = self._method_summary_text("DCF", source_result.get("DCF"))
                wwz_txt = self._method_summary_text("WWZ", source_result.get("WWZ"))
                beta_txt = self._method_summary_text("Beta", source_result.get("Beta"))

                lsp_conf = self._method_confidence_value("LSP", source_result.get("LSP"))
                jv_conf = self._method_confidence_value("Jurkevich", source_result.get("Jurkevich"))
                dcf_conf = self._method_confidence_value("DCF", source_result.get("DCF"))
                wwz_conf = self._method_confidence_value("WWZ", source_result.get("WWZ"))
                beta_conf = self._method_confidence_value("Beta", source_result.get("Beta"))

                matched_file = self._find_processed_file_for_source(source_name, processed_files)

                search_text = " ".join([
                    str(source_name),
                    str(source_result.get("status", "done")),
                    str(best_method),
                    str(matched_file or ""),
                    str(lsp_txt),
                    str(jv_txt),
                    str(dcf_txt),
                    str(wwz_txt),
                    str(beta_txt),
                ]).lower()

                row = {
                    "source_name": str(source_name),
                    "status": str(source_result.get("status", "done")),
                    "best_method": best_method,
                    "best_confidence": best_conf,
                    "lsp_result": lsp_txt,
                    "lsp_conf": lsp_conf,
                    "jv_result": jv_txt,
                    "jv_conf": jv_conf,
                    "dcf_result": dcf_txt,
                    "dcf_conf": dcf_conf,
                    "wwz_result": wwz_txt,
                    "wwz_conf": wwz_conf,
                    "beta_text": beta_txt,
                    "beta_conf": beta_conf,
                    "matched_file": matched_file or "-",
                    "payload": source_result,
                    "search_text": search_text,
                    "source_index": self._extract_source_index(str(source_name)),
                }

                rows.append(row)
                row_map[str(source_name)] = row

        # skipped 也可以补进去
        if isinstance(skipped_sources, dict):
            for file_name, info in skipped_sources.items():
                source_name = file_name
                reason = "-"

                if isinstance(info, dict):
                    source_name = info.get("source_name") or file_name
                    reason = info.get("reason", "-")

                source_name = str(source_name)
                search_text = f"{source_name} skipped {reason}".lower()

                row = {
                    "source_name": source_name,
                    "status": "skipped",
                    "best_method": "-",
                    "best_confidence": None,
                    "lsp_result": "-",
                    "lsp_conf": None,
                    "jv_result": "-",
                    "jv_conf": None,
                    "dcf_result": "-",
                    "dcf_conf": None,
                    "wwz_result": "-",
                    "wwz_conf": None,
                    "beta_text": "-",
                    "beta_conf": None,
                    "matched_file": file_name,
                    "payload": info if isinstance(info, dict) else {},
                    "search_text": search_text,
                    "source_index": self._extract_source_index(source_name),
                }

                rows.append(row)
                row_map[source_name] = row

        return rows, row_map

    def _sort_result_rows(self, rows: List[Dict[str, Any]], sort_mode: str):
        if sort_mode == "按LSP置信度降序":
            def lsp_conf_sort_key(r):
                conf = r.get("lsp_conf")
                if conf is None or conf == "-":
                    return (True, 99, 10 ** 9, "")
                try:
                    return (False, -float(conf),
                            self._status_rank(r.get("status", "-")),
                            r.get("source_index") if r.get("source_index") is not None else 10 ** 9,
                            r.get("source_name", ""))
                except (ValueError, TypeError):
                    return (True, 99, 10 ** 9, "")

            return sorted(rows, key=lsp_conf_sort_key)

        if sort_mode == "按WWZ置信度降序":
            def wwz_conf_sort_key(r):
                conf = r.get("wwz_conf")
                if conf is None or conf == "-":
                    return (True, 99, 10 ** 9, "")
                try:
                    return (False, -float(conf),
                            self._status_rank(r.get("status", "-")),
                            r.get("source_index") if r.get("source_index") is not None else 10 ** 9,
                            r.get("source_name", ""))
                except (ValueError, TypeError):
                    return (True, 99, 10 ** 9, "")

            return sorted(rows, key=wwz_conf_sort_key)

        if sort_mode == "按状态排序":
            return sorted(
                rows,
                key=lambda r: (
                    self._status_rank(r.get("status", "-")),
                    r.get("source_index") if r.get("source_index") is not None else 10 ** 9,
                    r.get("source_name", ""),
                )
            )

        if sort_mode == "按源名升序":
            return sorted(
                rows,
                key=lambda r: (
                    r.get("source_index") if r.get("source_index") is not None else 10 ** 9,
                    r.get("source_name", ""),
                )
            )

        # 默认按源号升序
        return sorted(
            rows,
            key=lambda r: (
                r.get("source_index") if r.get("source_index") is not None else 10 ** 9,
                r.get("source_name", ""),
            )
        )

    # =====================================================
    # 事件绑定
    # =====================================================
    def _schedule_results_filter(self, *args):
        if hasattr(self, "results_filter_timer") and self.results_filter_timer is not None:
            self.results_filter_timer.start()

    def _schedule_preview_filter(self, *args):
        if hasattr(self, "preview_filter_timer") and self.preview_filter_timer is not None:
            self.preview_filter_timer.start()

    def _bind_events(self):
        self.btn_browse_config.clicked.connect(self.browse_config_file)
        self.btn_load_config.clicked.connect(self.load_config_from_dialog)
        self.btn_save_config.clicked.connect(self.save_config_to_disk)

        self.btn_run.clicked.connect(self.start_process)
        self.btn_stop.clicked.connect(self.stop_process)
        self.btn_refresh_preview.clicked.connect(self.refresh_source_preview)
        self.btn_open_output.clicked.connect(self.open_output_folder)
        self.btn_clear_log.clicked.connect(self.clear_log)

        self.btn_select_all_preview.clicked.connect(self.select_all_preview_action)
        self.btn_clear_all_preview.clicked.connect(self.clear_all_preview_action)

        self.preview_search_edit.textChanged.connect(self._schedule_preview_filter)

        self.btn_browse_folder.clicked.connect(self.browse_folder)
        self.btn_browse_output.clicked.connect(self.browse_output_folder)
        self.btn_clear_all_overrides.clicked.connect(self.clear_all_overrides_action)

        self.btn_sort_preview.clicked.connect(self.on_sort_preview_clicked)
        self.btn_restore_preview.clicked.connect(self.on_restore_preview_clicked)
        self.btn_export_raw.clicked.connect(self.export_selected_raw_data)

        self.file_numbers_edit.editingFinished.connect(self._on_param_changed)
        self.folder_path_edit.editingFinished.connect(self._on_param_changed)
        self.file_type_combo.currentTextChanged.connect(self._on_param_changed)
        self.mode_combo.currentTextChanged.connect(self._on_param_changed)
        self.state_filename_edit.editingFinished.connect(self._on_param_changed)
        self.output_path_edit.editingFinished.connect(self._on_param_changed)

        self.export_docx_check.stateChanged.connect(self._on_param_changed)
        self.docx_name.editingFinished.connect(self._on_param_changed)

        self.rerun_check.stateChanged.connect(self._on_param_changed)
        self.gen_light_plot_check.stateChanged.connect(self._on_param_changed)
        self.global_remove_upper_limit_check.stateChanged.connect(self._on_param_changed)
        self.global_remove_max_value_spin.valueChanged.connect(self._on_param_changed)
        self.min_points_per_cycle.valueChanged.connect(self._on_param_changed)
        self.global_start_date_check.stateChanged.connect(self._on_param_changed)
        self.global_start_date_edit.dateChanged.connect(self._on_param_changed)
        self.global_end_date_check.stateChanged.connect(self._on_param_changed)
        self.global_end_date_edit.dateChanged.connect(self._on_param_changed)

        self.constant_flux.stateChanged.connect(self._on_param_changed)
        self.constant_flux_values.valueChanged.connect(self._on_param_changed)

        self.custom_lsp_check.stateChanged.connect(self._on_param_changed)
        self.custom_lsp_plot_check.stateChanged.connect(self._on_param_changed)
        self.custom_jv_check.stateChanged.connect(self._on_param_changed)
        self.custom_jv_plot_check.stateChanged.connect(self._on_param_changed)
        self.custom_dcf_check.stateChanged.connect(self._on_param_changed)
        self.custom_dcf_plot_check.stateChanged.connect(self._on_param_changed)
        self.custom_wwz_check.stateChanged.connect(self._on_param_changed)
        self.custom_wwz_plot_check.stateChanged.connect(self._on_param_changed)

        self.custom_jv_start.valueChanged.connect(self._on_param_changed)
        self.custom_jv_end.valueChanged.connect(self._on_param_changed)
        self.custom_jv_step.valueChanged.connect(self._on_param_changed)
        self.custom_jv_bins.valueChanged.connect(self._on_param_changed)
        self.custom_jv_plot_mode.currentTextChanged.connect(self._on_param_changed)

        self.custom_dcf_delta_tau.valueChanged.connect(self._on_param_changed)
        self.custom_dcf_c.valueChanged.connect(self._on_param_changed)
        self.custom_dcf_max_tau.valueChanged.connect(self._on_param_changed)
        self.custom_dcf_distance.valueChanged.connect(self._on_param_changed)
        self.custom_dcf_plot_mode.currentTextChanged.connect(self._on_param_changed)

        self.beta_calculate_check.stateChanged.connect(self._on_param_changed)
        self.beta_default_beta.valueChanged.connect(self._on_param_changed)
        self.beta_method_combo.currentTextChanged.connect(self._on_param_changed)
        self.beta_start.valueChanged.connect(self._on_param_changed)
        self.beta_end.valueChanged.connect(self._on_param_changed)
        self.beta_step.valueChanged.connect(self._on_param_changed)
        self.beta_M.valueChanged.connect(self._on_param_changed)
        self.beta_n_jobs.valueChanged.connect(self._on_param_changed)
        self.beta_plot_check.stateChanged.connect(self._on_param_changed)
        self.beta_n_bins.valueChanged.connect(self._on_param_changed)
        self.beta_plot_mode.currentTextChanged.connect(self._on_param_changed)

        self.lsp_divide_freq_step.valueChanged.connect(self._on_param_changed)
        self.lsp_sig_threshold.valueChanged.connect(self._on_param_changed)
        self.lsp_top_n.valueChanged.connect(self._on_param_changed)
        self.lsp_MC_check.stateChanged.connect(self._on_param_changed)
        self.lsp_M.valueChanged.connect(self._on_param_changed)
        self.lsp_n_jobs.valueChanged.connect(self._on_param_changed)
        self.lsp_plot_mode.currentTextChanged.connect(self._on_param_changed)
        self.lsp_time_axis_mode.currentTextChanged.connect(self._on_param_changed)
        self.lsp_time_input_format.currentTextChanged.connect(self._on_param_changed)
        self.lsp_method_combo.currentTextChanged.connect(self._on_param_changed)

        self.wwz_c.valueChanged.connect(self._on_param_changed)
        self.wwz_p_start.valueChanged.connect(self._on_param_changed)
        self.wwz_p_end.valueChanged.connect(self._on_param_changed)
        self.wwz_divide_freq_step.valueChanged.connect(self._on_param_changed)
        self.wwz_tau_number.valueChanged.connect(self._on_param_changed)
        self.wwz_z_height.valueChanged.connect(self._on_param_changed)
        self.wwz_MC_check.stateChanged.connect(self._on_param_changed)
        self.wwz_M.valueChanged.connect(self._on_param_changed)
        self.wwz_n_jobs.valueChanged.connect(self._on_param_changed)
        self.wwz_sig_threshold.valueChanged.connect(self._on_param_changed)
        self.wwz_top_n.valueChanged.connect(self._on_param_changed)
        self.wwz_plot_mode.currentTextChanged.connect(self._on_param_changed)
        self.wwz_time_scale.currentTextChanged.connect(self._on_param_changed)
        self.wwz_peak_prominence.valueChanged.connect(self._on_param_changed)
        self.wwz_use_log_scale_period.stateChanged.connect(self._on_param_changed)

        self.source_table.itemSelectionChanged.connect(self.on_source_table_selection_changed)

        self.btn_save_source_override.clicked.connect(self.save_current_source_override)
        self.btn_clear_source_override.clicked.connect(self.clear_current_source_override)
        self.btn_reload_source_override.clicked.connect(self.reload_current_source_override)

        # =====================================================
        # 结果查看 / 归档
        # =====================================================

        self.btn_refresh_results.clicked.connect(lambda: self.refresh_results_view(reload_disk=True))
        self.btn_export_csv.clicked.connect(self.export_results_to_csv)

        self.results_table.customContextMenuRequested.connect(self.on_results_table_context_menu)
        self.results_table.cellDoubleClicked.connect(self.on_results_table_cell_double_clicked)


        self.results_search_edit.textChanged.connect(self._schedule_results_filter)
        self.results_sort_combo.currentTextChanged.connect(self._schedule_results_filter)
        self.results_status_filter_combo.currentTextChanged.connect(self._schedule_results_filter)

        self.results_table.itemSelectionChanged.connect(self.on_results_table_selection_changed)

        self.output_path_edit.editingFinished.connect(lambda: self.refresh_results_view(reload_disk=True))
        self.state_filename_edit.editingFinished.connect(lambda: self.refresh_results_view(reload_disk=True))

    def export_results_to_csv(self):
        rows = self._results_visible_rows
        if not rows:
            QMessageBox.information(self, "提示", "没有可导出的结果数据。请先刷新结果。")
            return

        output_path = self.output_path_edit.text().strip() or PROJECT_ROOT
        default_filename = f"QPA-Cycler_Results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "导出CSV",
            os.path.join(output_path, default_filename),
            "CSV 文件 (*.csv)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)

                # 写入程序签名和时间
                writer.writerow(["# QPA-Cycler 结果导出"])
                writer.writerow(["# 程序版本: 1.0"])
                writer.writerow([f"# 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow(["# 数据来源:", self.state_filename_edit.text().strip() or "N/A"])
                writer.writerow([])

                # 写入表头
                headers = ["源号", "源名", "状态", "LSP方法结果", "LSP置信度",
                           "JV方法结果", "DCF方法结果", "WWZ方法结果", "WWZ置信度"]
                writer.writerow(headers)

                # 写入数据
                exported_count = 0
                for rowdata in rows:
                    writer.writerow([
                        rowdata.get("source_index") if rowdata.get("source_index") is not None else "-",
                        rowdata.get("source_name", "-"),
                        rowdata.get("status", "-"),
                        rowdata.get("lsp_result") or "-",
                        self._format_confidence_export(rowdata.get("lsp_conf")),
                        rowdata.get("jv_result") or "-",
                        rowdata.get("dcf_result") or "-",
                        rowdata.get("wwz_result") or "-",
                        self._format_confidence_export(rowdata.get("wwz_conf")),
                    ])
                    exported_count += 1

            QMessageBox.information(self, "导出成功",
                                    f"成功导出 {exported_count} 条结果到:\n{file_path}")
            self.statusBar().showMessage(f"CSV导出成功: {exported_count} 条记录", 5000)

        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"导出CSV失败:\n{e}")
            import traceback
            traceback.print_exc()

    def _format_confidence_export(self, conf_value):
        """格式化置信度用于导出"""
        if conf_value is None:
            return "-"
        try:
            return f"{float(conf_value):.4f}"
        except (ValueError, TypeError):
            return str(conf_value)

    def _format_confidence_export(self, conf_value):
        """格式化置信度用于导出"""
        if conf_value is None:
            return "-"
        try:
            return f"{float(conf_value):.4f}"
        except (ValueError, TypeError):
            return str(conf_value)

    def _on_param_changed(self):
        """参数改变时自动保存配置到磁盘"""
        # 只要不是正在加载配置（初始化），就允许存盘
        if self._loading_config:
            return

        try:
            self.commit_current_source_override(silent=True)
            cfg = self.collect_config_from_ui(include_source_overrides=True)
            # 强制获取当前的路径
            path = normalize_json_path(self.config_path_edit.text() or self.current_config_path or DEFAULT_CONFIG_PATH)

            # 即使在运行，也执行写入磁盘
            json_save(path, cfg)

            # 同步内存
            self.current_config = copy.deepcopy(cfg)
            self.statusBar().showMessage("配置已实时保存", 1000)
        except Exception as e:
            print(f"[自动保存失败] {e}")

    # =====================================================
    # 配置读写
    # =====================================================

    def load_config_from_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择配置文件",
            os.path.dirname(normalize_json_path(self.config_path_edit.text() or DEFAULT_CONFIG_PATH)),
            "JSON Files (*.json)"
        )
        if not path:
            return
        self.load_config_from_disk(path)

    def browse_config_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "浏览配置文件",
            os.path.dirname(normalize_json_path(self.config_path_edit.text() or DEFAULT_CONFIG_PATH)),
            "JSON Files (*.json)"
        )
        if not path:
            return
        path = normalize_json_path(path)
        self.config_path_edit.setText(path)
        self.current_config_path = path

    def load_config_from_disk(self, path: str):
        path = normalize_json_path(path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"配置文件不存在：{path}")

        self._loading_config = True
        try:
            cfg = json_load(path)
            if not isinstance(cfg, dict):
                raise ValueError("配置文件格式错误，必须是 JSON 对象。")

            self.current_config_path = path
            self.config_path_edit.setText(path)

            self.load_config_to_ui(cfg)
            self.refresh_source_preview()
            self.statusBar().showMessage(f"已加载配置：{path}", 5000)
        finally:
            self._loading_config = False

    def on_preview_table_item_changed(self, item):
        if self._preview_item_guard:
            return
        if item is None or item.column() != 0:
            return

        checked = self.get_preview_selected_numbers()
        self.selected_preview_numbers = {str(n) for n in checked}

        # 一旦用户手动点了复选框，就进入“手动选择模式”
        self.use_manual_source_selection = True

        self.preview_effective_count = len(checked)
        self.update_preview_info_label()

    def select_all_preview_action(self):
        if self.source_table.rowCount() == 0:
            return

        reply = QMessageBox.question(
            self, "确认全选",
            "确定要勾选当前列表中的所有文件吗？这会覆盖之前的选择状态。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._preview_item_guard = True  # 防止循环触发信号
            for row in range(self.source_table.rowCount()):
                item = self.source_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Checked)
            self._preview_item_guard = False

            # 手动调用一次更新逻辑
            self.sync_manual_selection_from_table()
            self._build_preview_row_cache()

    def clear_all_preview_action(self):
        if self.source_table.rowCount() == 0:
            return

        reply = QMessageBox.question(
            self, "确认清空",
            "确定要取消勾选所有已选文件吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._preview_item_guard = True
            for row in range(self.source_table.rowCount()):
                item = self.source_table.item(row, 0)
                if item:
                    item.setCheckState(Qt.Unchecked)
            self._preview_item_guard = False

            # 手动调用一次更新逻辑
            self.sync_manual_selection_from_table()
            self._build_preview_row_cache()

    def clear_all_overrides_action(self):
        # 如果当前根本没有覆盖配置，直接提示
        if not self.source_overrides:
            QMessageBox.information(self, "提示", "当前没有设置任何单源覆盖配置。")
            return

        # 确定按钮
        reply = QMessageBox.warning(
            self, "确认清除所有覆盖",
            f"确定要清除当前共 {len(self.source_overrides)} 个源的自定义覆盖配置吗？\n\n"
            "清除后，所有源都将使用主界面设置的【全局参数】进行计算。此操作不可撤销。",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # 1. 清空内存中的覆盖字典
            self.source_overrides.clear()
            if "source_overrides" in self.current_config:
                self.current_config["source_overrides"] = {}

            # 2. 如果当前右侧编辑器正开着某个源，立即重载它（使其恢复为全局配置的值）
            if self.current_selected_num:
                self.load_selected_source_into_editor(
                    self.current_selected_num,
                    self.current_selected_file_path
                )

            # 3. 刷新表格（这会把表格里的“是”变为“否”，并清空摘要列）
            self.refresh_source_preview()

            self.statusBar().showMessage("已成功清除所有单源覆盖配置", 3000)


    def sync_manual_selection_from_table(self):
        """辅助函数：将当前表格勾选状态同步到内存变量中"""
        checked = self.get_preview_selected_numbers()
        self.selected_preview_numbers = {str(n) for n in checked}
        self.use_manual_source_selection = True
        self.preview_effective_count = len(checked)
        self.update_preview_info_label()
        self.statusBar().showMessage(f"已更新勾选状态，当前选中 {len(checked)} 个源", 10000)


    def save_config_to_disk(self):
        try:
            self.commit_current_source_override(silent=True)
            cfg = self.collect_config_from_ui(include_source_overrides=True)
            path = normalize_json_path(self.config_path_edit.text() or self.current_config_path or DEFAULT_CONFIG_PATH)
            json_save(path, cfg)
            self.current_config = copy.deepcopy(cfg)
            self.current_config_path = path
            self.config_path_edit.setText(path)
            self.statusBar().showMessage(f"配置已保存：{path}", 5000)
            QMessageBox.information(self, "保存成功", f"配置已保存到：\n{path}")
            self.refresh_source_preview()
        except Exception as e:
            QMessageBox.critical(self, "保存失败", str(e))


    def save_config_to_disk_silent(self):
        self.commit_current_source_override(silent=True)
        cfg = self.collect_config_from_ui(include_source_overrides=True)
        path = normalize_json_path(self.config_path_edit.text() or self.current_config_path or DEFAULT_CONFIG_PATH)
        json_save(path, cfg)
        self.current_config = copy.deepcopy(cfg)
        self.current_config_path = path
        self.config_path_edit.setText(path)

    def load_config_to_ui(self, cfg: Dict[str, Any]):
        cfg = copy.deepcopy(cfg)

        raw_overrides = cfg.get("source_overrides", {}) or {}
        self.source_overrides = sanitize_source_overrides(raw_overrides)
        cfg["source_overrides"] = copy.deepcopy(self.source_overrides)
        self.current_config = copy.deepcopy(cfg)

        global_cfg = cfg.get("global", {})
        self.use_manual_source_selection = bool_value(
            global_cfg.get("use_selected_source_numbers", False),
            False
        )

        self.export_docx_check.setChecked(bool_value(global_cfg.get("export_docx", True), True))
        self.docx_name.setText(global_cfg.get("docx_name", "Running Results"))

        selected_source_numbers = global_cfg.get("selected_source_numbers", [])
        self.selected_preview_numbers = set()
        if isinstance(selected_source_numbers, list):
            for x in selected_source_numbers:
                try:
                    self.selected_preview_numbers.add(str(int(x)))
                except Exception:
                    pass

        self.folder_path_edit.setText(global_cfg.get("folder_path", ""))
        self.output_path_edit.setText(global_cfg.get("output_path", ""))
        set_combo_text(self.mode_combo, global_cfg.get("mode", "customize"))
        set_combo_text(self.file_type_combo, global_cfg.get("file_type", "csv"))


        file_numbers = global_cfg.get("file_numbers", -1)
        if isinstance(file_numbers, list):
            self.file_numbers_edit.setText(",".join(map(str, file_numbers)))
        else:
            self.file_numbers_edit.setText(str(file_numbers))

        self.min_points_per_cycle.setValue(int_value(global_cfg.get("min_points_per_cycle", 8), 8))

        self.state_filename_edit.setText(global_cfg.get("state_filename", "state"))
        self.rerun_check.setChecked(bool_value(global_cfg.get("rerun", False), False))

        set_optional_date_widgets(self.global_start_date_check, self.global_start_date_edit, global_cfg.get("start_date"))
        set_optional_date_widgets(self.global_end_date_check, self.global_end_date_edit, global_cfg.get("end_date"))
        self.global_remove_upper_limit_check.setChecked(bool_value(global_cfg.get("remove_upper_limit", True), True))
        self.global_remove_max_value_spin.setValue(int_value(global_cfg.get("remove_max_value_numbers", 0), 0))

        self.constant_flux.setChecked(bool_value(global_cfg.get("constant_flux", False), False))
        self.constant_flux_values.setValue(int_value(global_cfg.get("constant_flux_values", 5.0), 5.0))

        self.gen_light_plot_check.setChecked(bool_value(cfg.get("gen_light_plot", True), True))

        custom = cfg.get("customize", {})

        self.custom_lsp_check.setChecked(bool_value(custom.get("LSP", False), False))
        self.custom_lsp_plot_check.setChecked(bool_value(custom.get("LSP_Plot", False), False))
        self.custom_jv_check.setChecked(bool_value(custom.get("Jurkevich", False), False))
        self.custom_jv_plot_check.setChecked(bool_value(custom.get("JV_Plot", False), False))
        self.custom_dcf_check.setChecked(bool_value(custom.get("DCF", False), False))
        self.custom_dcf_plot_check.setChecked(bool_value(custom.get("DCF_Plot", False), False))
        self.custom_wwz_check.setChecked(bool_value(custom.get("WWZ", False), False))
        self.custom_wwz_plot_check.setChecked(bool_value(custom.get("WWZ_Plot", False), False))

        jvp = custom.get("jv_params", {})
        self.custom_jv_start.setValue(int_value(jvp.get("test_periods_start", 100), 100))
        self.custom_jv_end.setValue(int_value(jvp.get("test_periods_end", 3000), 3000))
        self.custom_jv_step.setValue(int_value(jvp.get("test_periods_step", 10), 10))
        self.custom_jv_bins.setValue(int_value(jvp.get("m_bins", 2), 2))
        set_combo_text(self.custom_jv_plot_mode, jvp.get("plot_mode", "save"))

        dcp = custom.get("dcf_params", {})
        self.custom_dcf_delta_tau.setValue(int_value(dcp.get("delta_tau", 3), 3))
        self.custom_dcf_c.setValue(int_value(dcp.get("c", 10), 10))
        self.custom_dcf_max_tau.setValue(int_value(dcp.get("max_tau", 2000), 2000))
        self.custom_dcf_distance.setValue(int_value(dcp.get("distance", 5), 5))
        set_combo_text(self.custom_dcf_plot_mode, dcp.get("plot_mode", "save"))

        bp = custom.get("beta_params", {})
        self.beta_calculate_check.setChecked(bool_value(bp.get("beta_calculate", True), True))
        self.beta_default_beta.setValue(float_value(bp.get("default_beta", 0.9), 0.9))
        set_combo_text(self.beta_method_combo, bp.get("method", "psresp"))
        self.beta_start.setValue(float_value(bp.get("beta_start", 0.1), 0.1))
        self.beta_end.setValue(float_value(bp.get("beta_end", 2.1), 2.1))
        self.beta_step.setValue(float_value(bp.get("beta_step", 0.1), 0.1))
        self.beta_M.setValue(int_value(bp.get("M", 1000), 1000))
        self.beta_n_jobs.setValue(int_value(bp.get("n_jobs", -1), -1))
        self.beta_plot_check.setChecked(bool_value(bp.get("plot", True), True))
        self.beta_n_bins.setValue(int_value(bp.get("n_bins", 6), 6))
        set_combo_text(self.beta_plot_mode, bp.get("plot_mode", "save"))

        lsp = custom.get("lsp_params", {})
        self.lsp_divide_freq_step.setValue(int_value(lsp.get("divide_freq_step", 10), 10))
        self.lsp_sig_threshold.setValue(float_value(lsp.get("sig_threshold", 0.997), 0.997))
        self.lsp_top_n.setValue(int_value(lsp.get("top_n", 3), 3))
        self.lsp_MC_check.setChecked(bool_value(lsp.get("MC", True), True))
        self.lsp_M.setValue(int_value(lsp.get("M", 10000), 10000))
        self.lsp_n_jobs.setValue(int_value(lsp.get("n_jobs", -1), -1))
        plot_params = lsp.get("plot_params", {})
        set_combo_text(self.lsp_plot_mode, plot_params.get("plot_mode", "save"))
        set_combo_text(self.lsp_time_axis_mode, plot_params.get("time_axis_mode", "ym"))
        set_combo_text(self.lsp_time_input_format, plot_params.get("time_input_format", "jd"))
        set_combo_text(self.lsp_method_combo, lsp.get("lsp_mode", "lsp"))

        wwz = custom.get("wwz_params", {})
        self.wwz_c.setValue(float_value(wwz.get("c", 0.0125), 0.0125))
        self.wwz_p_start.setValue(float_value(wwz.get("p_start",100), 100))
        self.wwz_p_end.setValue(float_value(wwz.get("p_end", 3000),2000))
        self.wwz_divide_freq_step.setValue(int_value(wwz.get("divide_freq_step", 10), 10))
        self.wwz_tau_number.setValue(int_value(wwz.get("tau_number", 1000), 1000))
        self.wwz_z_height.setValue(int_value(wwz.get("z_height", 20000), 20000))
        self.wwz_MC_check.setChecked(bool_value(wwz.get("MC", False), False))
        self.wwz_M.setValue(int_value(wwz.get("M", 10000), 10000))
        self.wwz_n_jobs.setValue(int_value(wwz.get("n_jobs", -1), -1))
        self.wwz_sig_threshold.setValue(float_value(wwz.get("sig_threshold", 0.997), 0.997))
        self.wwz_top_n.setValue(int_value(wwz.get("top_n", 3), 3))
        wwz_plot = wwz.get("plot_params", {})
        set_combo_text(self.wwz_plot_mode, wwz_plot.get("plot_mode", "save"))
        set_combo_text(self.wwz_time_scale, wwz_plot.get("time_scale", "JD"))
        self.wwz_peak_prominence.setValue(float_value(wwz_plot.get("peak_prominence", 3), 3))
        self.wwz_use_log_scale_period.setChecked(bool_value(wwz_plot.get("use_log_scale_period", True), True))

        self.refresh_results_view(reload_disk=True)

    def _drop_dead_process_object(self):
        if self.process is not None and self.process.state() == QProcess.NotRunning:
            try:
                self.process.deleteLater()
            except Exception:
                pass
            self.process = None

    def _force_kill_if_needed(self):
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            self.append_log("[GUI] terminate 超时，执行 kill()")
            try:
                self.process.kill()
            except Exception:
                pass

    def _maybe_finalize_if_still_not_running(self):
        if self._process_finalized:
            return
        if self.process is None:
            self._finalize_process(success=False, message="检测到任务进程已退出，已恢复界面状态。")
            return
        if self.process.state() == QProcess.NotRunning and self.is_running:
            self._finalize_process(success=False, message="检测到任务进程已退出，已恢复界面状态。")

    def _finalize_process(self, success: bool = False, message: str = ""):
        if self._process_finalized:
            return

        self._process_finalized = True

        proc = self.process
        if proc is not None:
            try:
                proc.readyReadStandardOutput.disconnect(self.on_stdout_ready)
            except Exception:
                pass
            try:
                proc.readyReadStandardError.disconnect(self.on_stderr_ready)
            except Exception:
                pass
            try:
                proc.finished.disconnect(self.on_process_finished)
            except Exception:
                pass
            try:
                proc.errorOccurred.disconnect(self.on_process_error)
            except Exception:
                pass
            try:
                proc.stateChanged.disconnect(self.on_process_state_changed)
            except Exception:
                pass

            try:
                proc.deleteLater()
            except Exception:
                pass

        self.process = None
        self.stop_requested = False
        self.is_running = False

        self._set_running_state(False)

        if success:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.status_label.setText("运行完成")
            self.statusBar().showMessage("运行完成", 5000)
        else:
            self.status_label.setText("就绪")
            if message:
                self.statusBar().showMessage(message, 5000)

        try:
            self.refresh_results_view(reload_disk=True)
        except Exception:
            pass

        if message:
            self.append_log(f"[GUI] {message}")





    def _create_result_image_card(self, key: str, title: str) -> Dict[str, Any]:
        box = QGroupBox(title)
        layout = QVBoxLayout(box)

        path_label = QLabel("图片路径：-")
        path_label.setWordWrap(True)

        image_label = QLabel("暂无图片")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setMinimumHeight(240)
        image_label.setStyleSheet("background: #111; color: #ddd; border: 1px solid #444;")
        image_label.setWordWrap(True)

        btn_row = QWidget()
        btn_layout = QHBoxLayout(btn_row)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        open_btn = QPushButton("打开图片")
        open_btn.setEnabled(False)
        open_btn.clicked.connect(lambda checked=False, method_key=key: self._open_result_image(method_key))

        btn_layout.addStretch(1)
        btn_layout.addWidget(open_btn)

        layout.addWidget(path_label)
        layout.addWidget(image_label, 1)
        layout.addWidget(btn_row)

        return {
            "widget": box,
            "path_label": path_label,
            "image_label": image_label,
            "open_btn": open_btn,
            "path": None,
            "title": title,
            "key": key,
        }

    def _load_json_file(self, path: str) -> Dict[str, Any]:
        if not path or not os.path.exists(path):
            return {}
        try:
            return json_load(path)
        except Exception:
            return {}

    def _find_state_file(self, output_path: str, state_filename: str) -> str:
        if not output_path or not os.path.isdir(output_path):
            return ""

        candidates = [
            os.path.join(output_path, "Running_Data", ensure_json_suffix(state_filename)),
            os.path.join(output_path, "Running_Data", "state.json"),
            os.path.join(output_path, ensure_json_suffix(state_filename)),
            os.path.join(output_path, "state.json"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p

        # 兜底：递归搜索一次
        try:
            target_names = {ensure_json_suffix(state_filename).lower(), "state.json"}
            for root, _, files in os.walk(output_path):
                for f in files:
                    if f.lower() in target_names:
                        return os.path.join(root, f)
        except Exception:
            pass

        return ""

    def _find_archive_file(self, output_path: str) -> str:
        if not output_path or not os.path.isdir(output_path):
            return ""

        # 先按常见命名找
        common_names = {
            "results_archive.json",
            "archive.json",
            "result_archive.json",
        }

        candidates = [
            os.path.join(output_path, "Archive", "results_archive.json"),
            os.path.join(output_path, "Archive", "archive.json"),
            os.path.join(output_path, "Running_Data", "results_archive.json"),
            os.path.join(output_path, "Running_Data", "archive.json"),
            os.path.join(output_path, "results_archive.json"),
            os.path.join(output_path, "archive.json"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p

        # 再递归搜名字里带 archive 的 json
        try:
            for root, _, files in os.walk(output_path):
                for f in files:
                    fn = f.lower()
                    if fn.endswith(".json") and "archive" in fn:
                        return os.path.join(root, f)
        except Exception:
            pass

        return ""

    def _normalize_archive_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        兼容不同 archive 结构：
        - 直接就是 state-like dict
        - {"runs":[...]}
        - {"archive": {...}}
        - {"state": {...}}
        """
        if not isinstance(data, dict):
            return {}

        if "results" in data or "processed_files" in data or "skipped_sources" in data:
            return data

        runs = data.get("runs")
        if isinstance(runs, list) and runs:
            for run in reversed(runs):
                if isinstance(run, dict) and ("results" in run or "processed_files" in run):
                    return run
            if isinstance(runs[-1], dict):
                return runs[-1]

        for k in ("archive", "state", "data", "payload"):
            nested = data.get(k)
            if isinstance(nested, dict):
                return nested

        return data

    def _unique_list(self, items: List[Any]) -> List[Any]:
        out = []
        seen = set()
        for x in items or []:
            key = json.dumps(x, ensure_ascii=False, sort_keys=True, default=str) if isinstance(x, (
                dict, list)) else str(x)
            if key not in seen:
                seen.add(key)
                out.append(x)
        return out

    def _merge_results_payloads(self, archive_data: Dict[str, Any], state_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        合并策略：
        - archive 作为底座
        - state 作为实时覆盖层
        - results/skipped_sources 按 key 覆盖
        - processed_files / valid_sources 走去重并集
        """
        archive_data = self._normalize_archive_payload(archive_data or {})
        state_data = state_data or {}

        merged = copy.deepcopy(archive_data) if isinstance(archive_data, dict) else {}
        if not isinstance(merged, dict):
            merged = {}

        # 顶层列表字段
        for key in ("processed_files", "valid_sources", "source_names"):
            a = merged.get(key, [])
            b = state_data.get(key, [])
            if isinstance(a, list) or isinstance(b, list):
                merged[key] = self._unique_list(
                    (a if isinstance(a, list) else []) + (b if isinstance(b, list) else []))

        # 顶层字典字段
        for key in ("skipped_sources",):
            a = merged.get(key, {})
            b = state_data.get(key, {})
            out = {}
            if isinstance(a, dict):
                out.update(copy.deepcopy(a))
            if isinstance(b, dict):
                out.update(copy.deepcopy(b))
            merged[key] = out

        # results：state 覆盖 archive
        archive_results = merged.get("results", {})
        if not isinstance(archive_results, dict):
            archive_results = {}
        state_results = state_data.get("results", {})
        if not isinstance(state_results, dict):
            state_results = {}

        results = copy.deepcopy(archive_results)
        for source_name, result in state_results.items():
            results[str(source_name)] = copy.deepcopy(result)
        merged["results"] = results

        # 其他常见列表也尽量保留 state 覆盖
        for key in ("lsp_expected_period", "jv_expected_period", "dcf_possible_period", "wwz_possibly_period"):
            if key in state_data:
                merged[key] = copy.deepcopy(state_data.get(key))
            elif key not in merged:
                merged[key] = []

        return merged

    def _extract_source_index(self, source_name: str) -> Optional[int]:
        if not source_name:
            return None
        m = re.match(r"^(\d+)_", str(source_name))
        if not m:
            return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def _get_source_variants(self, source_name: str) -> List[str]:
        if not source_name:
            return []
        variants = set()
        s = str(source_name)
        variants.add(s)
        short_name = re.sub(r"^\d+_", "", s)
        variants.add(short_name)
        if "_" in short_name:
            parts = short_name.split("_")
            if len(parts) >= 2:
                variants.add("_".join(parts[1:]))
                variants.add(parts[-1])
        return [v for v in variants if v]

    def _coerce_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return None
        if isinstance(value, str):
            s = value.strip()
            try:
                return float(s)
            except Exception:
                m = re.search(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
                if m:
                    try:
                        return float(m.group(0))
                    except Exception:
                        return None
        return None

    def _extract_beta_fields(self, container: Any):
        beta = None
        beta_err = None

        if isinstance(container, dict):
            sub = container.get("Beta")
            if isinstance(sub, dict):
                beta = sub.get("beta_best", sub.get("beta"))
                beta_err = sub.get("beta_err", sub.get("beta_error"))

            if beta is None:
                beta = container.get("beta_best", container.get("beta"))
            if beta_err is None:
                beta_err = container.get("beta_err", container.get("beta_error"))

        return self._coerce_float(beta), self._coerce_float(beta_err)

    def _format_number(self, value: Any, digits: int = 4) -> str:
        if value is None:
            return "-"
        if isinstance(value, bool):
            return "True" if value else "False"
        if isinstance(value, int) and not isinstance(value, bool):
            return str(value)
        try:
            v = float(value)
            if v != v:  # NaN
                return "-"
            return f"{v:.{digits}f}"
        except Exception:
            return str(value)

    def _format_confidence_text(self, value: Any) -> str:
        v = self._coerce_float(value)
        if v is None:
            return "-"
        if 0.0 <= v <= 1.0:
            return f"{v * 100:.2f}%"
        return self._format_number(v, 4)

    def _method_summary_text(self, method_name: str, method_result: Any) -> str:
        if method_result is None:
            return "-"

        if method_name == "Beta":
            beta, beta_err = self._extract_beta_fields(method_result)
            if beta is None and beta_err is None:
                return "-"
            if beta is not None and beta_err is not None:
                return f"β {self._format_number(beta, 4)} ± {self._format_number(beta_err, 4)}"
            if beta is not None:
                return f"β {self._format_number(beta, 4)}"
            return f"± {self._format_number(beta_err, 4)}"

        if method_name == "LSP":
            periods = []
            if isinstance(method_result, dict):
                periods = method_result.get("periods") or []
            if not periods:
                return "未检出显著周期"
            first = periods[0] if isinstance(periods[0], dict) else {}
            p = first.get("period")
            return f"{len(periods)} 个候选，首个周期 {self._format_number(p, 2)} d"

        if method_name == "Jurkevich":
            if not isinstance(method_result, dict):
                return "无结果"
            p = method_result.get("period")
            if p is None:
                return "无结果"
            return f"周期 {self._format_number(p, 2)} d"

        if method_name == "DCF":
            periods = []
            if isinstance(method_result, dict):
                periods = method_result.get("period") or []
            if not periods:
                return "未检出显著周期"
            first = periods[0] if isinstance(periods[0], dict) else {}
            p = first.get("period")
            return f"{len(periods)} 个候选，首个周期 {self._format_number(p, 2)} d"

        if method_name == "WWZ":
            peaks = []
            if isinstance(method_result, dict):
                peaks = method_result.get("result") or []
            if not peaks:
                return "未检出显著周期"
            first = peaks[0] if isinstance(peaks[0], dict) else {}
            p = first.get("period")
            return f"{len(peaks)} 个候选，首个周期 {self._format_number(p, 2)} d"

        return self._format_number(method_result, 4)

    def _method_confidence_value(self, method_name: str, method_result: Any) -> Optional[float]:
        if method_result is None:
            return None

        if method_name == "Beta":
            return None

        candidates = []

        if method_name == "LSP" and isinstance(method_result, dict):
            for item in method_result.get("periods", []) or []:
                if isinstance(item, dict):
                    for k in ("significance", "confidence", "score", "probability"):
                        v = self._coerce_float(item.get(k))
                        if v is not None:
                            candidates.append(v)
                    # sigma 不是概率，但可作为强度参考
                    v = self._coerce_float(item.get("sigma"))
                    if v is not None:
                        candidates.append(v)

        elif method_name == "WWZ" and isinstance(method_result, dict):
            for item in method_result.get("result", []) or []:
                if isinstance(item, dict):
                    for k in ("significance", "confidence", "score", "probability"):
                        v = self._coerce_float(item.get(k))
                        if v is not None:
                            candidates.append(v)

        elif method_name == "DCF" and isinstance(method_result, dict):
            for item in method_result.get("period", []) or []:
                if isinstance(item, dict):
                    for k in ("sigma", "significance"):
                        v = self._coerce_float(item.get(k))
                        if v is not None:
                            candidates.append(v)

        elif method_name == "Jurkevich" and isinstance(method_result, dict):
            for k in ("confidence", "significance", "score", "probability"):
                v = self._coerce_float(method_result.get(k))
                if v is not None:
                    candidates.append(v)

        if not candidates:
            return None
        return max(candidates)

    def _best_method_info(self, source_result: Dict[str, Any]):
        methods = ["LSP", "Jurkevich", "DCF", "WWZ", "Beta"]
        best_method = "-"
        best_value = None

        for m in methods:
            val = self._method_confidence_value(m, source_result.get(m))
            if val is not None:
                if best_value is None or val > best_value:
                    best_value = val
                    best_method = m

        # 如果没有任何“置信度”，但有结果，也给一个可读的最佳方法
        if best_value is None:
            for m in methods:
                if source_result.get(m) is not None:
                    best_method = m
                    break

        return best_method, best_value

    def _status_rank(self, status: str) -> int:
        s = (status or "").lower()
        order = {
            "done": 0,
            "processing": 1,
            "skipped": 2,
            "failed": 3,
        }
        return order.get(s, 99)

    def _find_processed_file_for_source(self, source_name: str, processed_files: List[str]) -> Optional[str]:
        if not processed_files:
            return None

        variants = self._get_source_variants(source_name)
        candidates = []

        for idx, file_name in enumerate(processed_files):
            stem = os.path.splitext(os.path.basename(file_name))[0].lower()
            score = 0
            if any(v.lower() in stem for v in variants):
                score += 80
            if source_name and str(source_name).lower() in stem:
                score += 40
            short_name = re.sub(r"^\d+_", "", str(source_name)) if source_name else ""
            if short_name and short_name.lower() in stem:
                score += 20

            if score > 0:
                candidates.append((score, -idx, file_name))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        return candidates[0][2]


    def collect_config_from_ui(self, include_source_overrides: bool = True) -> Dict[str, Any]:
        cfg = copy.deepcopy(self.current_config) if isinstance(self.current_config, dict) else default_config()

        cfg["gen_light_plot"] = self.gen_light_plot_check.isChecked()

        global_cfg = cfg.setdefault("global", {})

        global_cfg["use_selected_source_numbers"] = self.use_manual_source_selection

        global_cfg["export_docx"] = self.export_docx_check.isChecked()
        global_cfg["mode"] = self.mode_combo.currentText().strip()
        global_cfg["folder_path"] = self.folder_path_edit.text().strip()
        global_cfg["output_path"] = self.output_path_edit.text().strip()
        global_cfg["file_numbers"] = self._parse_file_numbers_input(self.file_numbers_edit.text())
        global_cfg["state_filename"] = self.state_filename_edit.text().strip() or "state"
        global_cfg["file_type"] = self.file_type_combo.currentText().strip()
        global_cfg["rerun"] = self.rerun_check.isChecked()
        global_cfg["remove_upper_limit"] = self.global_remove_upper_limit_check.isChecked()
        global_cfg["min_points_per_cycle"] = self.min_points_per_cycle.value()
        global_cfg["remove_max_value_numbers"] = self.global_remove_max_value_spin.value()
        global_cfg["start_date"] = get_optional_date_value(self.global_start_date_check, self.global_start_date_edit)
        global_cfg["end_date"] = get_optional_date_value(self.global_end_date_check, self.global_end_date_edit)
        global_cfg["docx_name"] = self.docx_name.text().strip()

        selected_nums = []
        for x in self.selected_preview_numbers:
            try:
                selected_nums.append(int(x))
            except Exception:
                pass

        if self.use_manual_source_selection:
            global_cfg["selected_source_numbers"] = sorted(set(selected_nums))
        else:
            # 没启用手动选择时，清空它，避免污染默认逻辑
            global_cfg["selected_source_numbers"] = []


        global_cfg["constant_flux"] = self.constant_flux.isChecked()
        global_cfg["constant_flux_values"] = self.constant_flux_values.value()

        custom = cfg.setdefault("customize", {})
        custom["DCF"] = self.custom_dcf_check.isChecked()
        custom["DCF_Plot"] = self.custom_dcf_plot_check.isChecked()
        custom["Jurkevich"] = self.custom_jv_check.isChecked()
        custom["JV_Plot"] = self.custom_jv_plot_check.isChecked()
        custom["LSP"] = self.custom_lsp_check.isChecked()
        custom["LSP_Plot"] = self.custom_lsp_plot_check.isChecked()
        custom["WWZ"] = self.custom_wwz_check.isChecked()
        custom["WWZ_Plot"] = self.custom_wwz_plot_check.isChecked()

        custom["jv_params"] = {
            "test_periods_start": self.custom_jv_start.value(),
            "test_periods_end": self.custom_jv_end.value(),
            "test_periods_step": self.custom_jv_step.value(),
            "m_bins": self.custom_jv_bins.value(),
            "plot_mode": self.custom_jv_plot_mode.currentText().strip(),
        }
        custom["dcf_params"] = {
            "delta_tau": self.custom_dcf_delta_tau.value(),
            "c": self.custom_dcf_c.value(),
            "max_tau": self.custom_dcf_max_tau.value(),
            "distance": self.custom_dcf_distance.value(),
            "plot_mode": self.custom_dcf_plot_mode.currentText().strip(),
        }
        custom["beta_params"] = {
            "beta_calculate": self.beta_calculate_check.isChecked(),
            "default_beta": self.beta_default_beta.value(),
            "method": self.beta_method_combo.currentText().strip(),
            "beta_start": self.beta_start.value(),
            "beta_end": self.beta_end.value(),
            "beta_step": self.beta_step.value(),
            "M": self.beta_M.value(),
            "n_jobs": self.beta_n_jobs.value(),
            "plot": self.beta_plot_check.isChecked(),
            "n_bins": self.beta_n_bins.value(),
            "plot_mode": self.beta_plot_mode.currentText().strip(),
        }
        custom["lsp_params"] = {
            "lsp_mode":self.lsp_method_combo.currentText().strip(),
            "divide_freq_step": self.lsp_divide_freq_step.value(),
            "sig_threshold": self.lsp_sig_threshold.value(),
            "top_n": self.lsp_top_n.value(),
            "MC": self.lsp_MC_check.isChecked(),
            "M": self.lsp_M.value(),
            "n_jobs": self.lsp_n_jobs.value(),
            "plot_params": {
                "plot_mode": self.lsp_plot_mode.currentText().strip(),
                "time_axis_mode": self.lsp_time_axis_mode.currentText().strip(),
                "time_input_format": self.lsp_time_input_format.currentText().strip(),
            },
        }
        custom["wwz_params"] = {
            "c": self.wwz_c.value(),
            "p_start": self.wwz_p_start.value(),
            "p_end": self.wwz_p_end.value(),
            "divide_freq_step": self.wwz_divide_freq_step.value(),
            "tau_number": self.wwz_tau_number.value(),
            "z_height": self.wwz_z_height.value(),
            "MC": self.wwz_MC_check.isChecked(),
            "M": self.wwz_M.value(),
            "n_jobs": self.wwz_n_jobs.value(),
            "sig_threshold": self.wwz_sig_threshold.value(),
            "top_n": self.wwz_top_n.value(),
            "plot_params": {
                "plot_mode": self.wwz_plot_mode.currentText().strip(),
                "time_scale": self.wwz_time_scale.currentText().strip(),
                "peak_prominence": self.wwz_peak_prominence.value(),
                "use_log_scale_period": self.wwz_use_log_scale_period.isChecked(),
            },
        }

        if include_source_overrides:
            cfg["source_overrides"] = sanitize_source_overrides(self.source_overrides)
        else:
            cfg.pop("source_overrides", None)

        return cfg

    def _parse_file_numbers_input(self, text: str):
        s = (text or "").strip()
        if not s:
            return -1
        if s.lower() in {"all", "全部", "-1"}:
            return -1
        try:
            if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
                return int(s)
        except Exception:
            pass
        return s.replace(" ", "")

    # =====================================================
    # 文件浏览
    # =====================================================

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输入目录", self.folder_path_edit.text().strip() or PROJECT_ROOT)
        if folder:
            self.folder_path_edit.setText(folder)
            self.refresh_source_preview()

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录", self.output_path_edit.text().strip() or PROJECT_ROOT)
        if folder:
            self.output_path_edit.setText(folder)
            self.refresh_results_view(reload_disk=True)

    def open_output_folder(self):
        path = self.output_path_edit.text().strip()
        if not path:
            QMessageBox.warning(self, "提示", "输出目录为空。")
            return
        if not os.path.exists(path):
            QMessageBox.warning(self, "提示", f"输出目录不存在：\n{path}")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # =====================================================
    # 结果查看 / 归档
    # =====================================================

    def _on_results_refresh_timer(self):
        if self.is_running:
            self.refresh_results_view(reload_disk=True)

    def _find_best_image_path(self, data_path: str, folder_name: str, source_name: str,
                              must_have: Optional[List[str]] = None,
                              must_not_have: Optional[List[str]] = None) -> Optional[str]:
        if not data_path or not os.path.isdir(data_path):
            return None

        search_dirs = []
        folder_path = os.path.join(data_path, folder_name)
        if os.path.isdir(folder_path):
            search_dirs.append(folder_path)
        else:
            search_dirs.append(data_path)

        variants = [v.lower() for v in self._get_source_variants(source_name)]
        must_have = [s.lower() for s in (must_have or [])]
        must_not_have = [s.lower() for s in (must_not_have or [])]

        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
        candidates = []

        seen = set()
        for sd in search_dirs:
            for root, _, files in os.walk(sd):
                for fn in files:
                    if os.path.splitext(fn)[1].lower() not in image_exts:
                        continue
                    path = os.path.join(root, fn)
                    if path in seen:
                        continue
                    seen.add(path)

                    stem = os.path.splitext(fn)[0].lower()

                    if not any(v in stem for v in variants):
                        continue
                    if must_not_have and any(term in stem for term in must_not_have):
                        continue
                    if must_have and not any(term in stem for term in must_have):
                        continue

                    score = 100
                    abs_path = os.path.abspath(path)
                    abs_folder = os.path.abspath(folder_path) if os.path.isdir(folder_path) else None
                    if abs_folder and abs_path.startswith(abs_folder + os.sep):
                        score += 20
                    if must_have:
                        score += 20

                    try:
                        mtime = os.path.getmtime(path)
                    except Exception:
                        mtime = 0

                    candidates.append((score, mtime, path))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], -x[1], len(os.path.basename(x[2]))))
        return candidates[0][2]

    def _set_card_image(self, card: Dict[str, Any], path: Optional[str]):
        card["path"] = path
        label: QLabel = card["path_label"]
        image_label: QLabel = card["image_label"]
        open_btn: QPushButton = card["open_btn"]

        if not path or not os.path.exists(path):
            label.setText("图片路径：-")
            image_label.setText("暂无图片")
            image_label.setPixmap(QPixmap())
            open_btn.setEnabled(False)
            return

        label.setText(f"图片路径：{path}")
        pixmap = QPixmap(path)
        if pixmap.isNull():
            image_label.setText("图片加载失败")
            image_label.setPixmap(QPixmap())
            open_btn.setEnabled(False)
            return

        # 固定一个比较稳的显示宽度，避免太窄
        scaled = pixmap.scaledToWidth(900, Qt.SmoothTransformation)
        image_label.setPixmap(scaled)
        image_label.setText("")
        open_btn.setEnabled(True)

    def _open_result_image(self, method_key: str):
        card = self.result_image_cards.get(method_key)
        if not card:
            return
        path = card.get("path")
        if not path or not os.path.exists(path):
            QMessageBox.information(self, "提示", f"没有找到 {method_key} 对应图片。")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _build_visible_source_list(self, merged: Dict[str, Any]) -> List[str]:
        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}
        valid_sources = merged.get("valid_sources", []) or []
        source_names = merged.get("source_names", []) or []

        names = []

        # 1) 优先 results
        for s in results.keys():
            if s not in names:
                names.append(str(s))

        # 2) 再加入 skipped 的 source_name
        if isinstance(skipped_sources, dict):
            for file_key, info in skipped_sources.items():
                if isinstance(info, dict):
                    sname = info.get("source_name") or file_key
                else:
                    sname = file_key
                if sname and str(sname) not in names:
                    names.append(str(sname))

        # 3) valid_sources / source_names 兜底
        for arr in (valid_sources, source_names):
            if isinstance(arr, list):
                for s in arr:
                    if s and str(s) not in names:
                        names.append(str(s))

        return names

    def _sort_visible_sources(self, sources: List[str], merged: Dict[str, Any]) -> List[str]:
        mode = self.results_sort_combo.currentText().strip()
        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}

        def get_status(src: str) -> str:
            if src in results and isinstance(results.get(src), dict):
                return str(results[src].get("status", "done"))
            # 看看是不是 skipped
            if isinstance(skipped_sources, dict):
                for file_key, info in skipped_sources.items():
                    if isinstance(info, dict) and str(info.get("source_name") or file_key) == src:
                        return "skipped"
            return "-"

        def get_best_conf(src: str) -> float:
            res = results.get(src, {}) if isinstance(results.get(src, {}), dict) else {}
            _, val = self._best_method_info(res)
            if val is None:
                return -1e9
            return float(val)

        if mode == "按最佳置信度降序":
            return sorted(
                sources,
                key=lambda s: (
                    -get_best_conf(s),
                    self._status_rank(get_status(s)),
                    self._extract_source_index(s) if self._extract_source_index(s) is not None else 10 ** 9,
                    s,
                )
            )

        if mode == "按状态排序":
            return sorted(
                sources,
                key=lambda s: (
                    self._status_rank(get_status(s)),
                    self._extract_source_index(s) if self._extract_source_index(s) is not None else 10 ** 9,
                    s,
                )
            )

        if mode == "按源名升序":
            return sorted(
                sources,
                key=lambda s: (
                    self._extract_source_index(s) if self._extract_source_index(s) is not None else 10 ** 9,
                    s,
                )
            )

        # 默认按源号升序
        return sorted(
            sources,
            key=lambda s: (
                self._extract_source_index(s) if self._extract_source_index(s) is not None else 10 ** 9,
                s,
            )
        )

    def _filter_visible_sources(self, sources: List[str], merged: Dict[str, Any]) -> List[str]:
        query = self.results_search_edit.text().strip().lower()
        status_filter = self.results_status_filter_combo.currentText().strip().lower()

        if not query and status_filter == "全部":
            return sources

        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}

        filtered = []
        for src in sources:
            res = results.get(src, {}) if isinstance(results.get(src, {}), dict) else {}
            status = str(res.get("status", "-")).lower()

            if src in results:
                pass
            else:
                # skipped
                status = "skipped"

            if status_filter != "全部" and status != status_filter:
                continue

            if query:
                hit = False
                if query in str(src).lower():
                    hit = True
                else:
                    # 也允许按结果摘要搜
                    for m in ("LSP", "Jurkevich", "DCF", "WWZ", "Beta"):
                        txt = self._method_summary_text(m, res.get(m))
                        if query in str(txt).lower():
                            hit = True
                            break
                if not hit:
                    continue

            filtered.append(src)

        return filtered

    def refresh_results_view(self, reload_disk: bool = True):
        """
        结果页刷新：
        - state 文件没变时，直接用缓存
        - 只刷新主表缓存，不再渲染任何右侧详情
        """
        try:
            output_path = self.output_path_edit.text().strip()
            state_filename = self.state_filename_edit.text().strip() or "state"

            if not output_path or not os.path.isdir(output_path):
                self._results_state_cache = {}
                self._results_state_path_cached = ""
                self._results_state_mtime = -1.0
                self._results_all_rows = []
                self._results_visible_rows = []
                self._clear_results_view("结果：输出目录无效")
                return

            state_file_path = self._find_state_file(output_path, state_filename)
            if not state_file_path or not os.path.exists(state_file_path):
                self._results_state_cache = {}
                self._results_state_path_cached = ""
                self._results_state_mtime = -1.0
                self._results_all_rows = []
                self._results_visible_rows = []
                self._clear_results_view("结果：未找到 state 文件")
                return

            need_reload = reload_disk

            try:
                current_mtime = os.path.getmtime(state_file_path)
            except Exception:
                current_mtime = -1.0

            # 如果文件没变，就不重新读盘
            if (
                    self._results_state_path_cached == state_file_path
                    and self._results_state_cache
                    and self._results_state_mtime == current_mtime
            ):
                need_reload = False

            if need_reload:
                raw_state = self._load_json_file(state_file_path)
                self._results_state_cache = raw_state if isinstance(raw_state, dict) else {}
                self._results_state_path_cached = state_file_path
                self._results_state_mtime = current_mtime

            merged = self._results_state_cache or {}
            self._results_all_rows = self._build_results_row_cache(merged)

            self.results_info_label.setText(
                f"结果数：{len(self._results_all_rows)} | "
                f"state：{os.path.basename(state_file_path)} | "
                f"缓存：{'是' if not need_reload else '已刷新'}"
            )

            # 刷新后只做筛选/排序，不重新读盘
            self.apply_results_filter()

        except Exception as e:
            self._clear_results_view(f"结果刷新失败：{e}")

    def _build_results_row_cache(self, merged: Dict[str, Any]) -> List[Dict[str, Any]]:
        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}
        processed_files = merged.get("processed_files", []) or []

        # 1) skipped_sources 建索引
        skipped_by_source: Dict[str, Dict[str, Any]] = {}
        if isinstance(skipped_sources, dict):
            for file_key, info in skipped_sources.items():
                if isinstance(info, dict):
                    src = str(info.get("source_name") or file_key).strip()
                    if src:
                        skipped_by_source[src] = info

        # 2) processed_files 建索引
        processed_by_source: Dict[str, Dict[str, Any]] = {}
        if isinstance(processed_files, list):
            for item in processed_files:
                if isinstance(item, dict):
                    src = str(item.get("source_name") or item.get("source") or item.get("name") or "").strip()
                    if src and src not in processed_by_source:
                        processed_by_source[src] = item

        rows: List[Dict[str, Any]] = []
        source_names = self._build_visible_source_list(merged) or []

        for src in source_names:
            source_result = results.get(src, {})
            if not isinstance(source_result, dict):
                source_result = {}

            skipped_info = skipped_by_source.get(src)

            status = str(source_result.get("status", "-"))
            if not source_result and skipped_info is not None:
                status = "skipped"

            source_index = self._extract_source_index(src)

            # 这里复用你已有的函数
            try:
                best_method, best_conf = self._best_method_info(source_result)
            except Exception:
                best_method, best_conf = "-", -1.0

            matched_file = self._find_processed_file_fast(src, processed_by_source, processed_files)

            lsp_result = self._method_summary_text("LSP", source_result.get("LSP"))
            lsp_conf = self._format_confidence_text(self._method_confidence_value("LSP", source_result.get("LSP")))
            jv_result = self._method_summary_text("Jurkevich", source_result.get("Jurkevich"))
            dcf_result = self._method_summary_text("DCF", source_result.get("DCF"))
            wwz_result = self._method_summary_text("WWZ", source_result.get("WWZ"))
            wwz_conf = self._format_confidence_text(self._method_confidence_value("WWZ", source_result.get("WWZ")))

            search_text = " ".join(map(str, [
                src, status, lsp_result, lsp_conf, jv_result, dcf_result, wwz_result, wwz_conf, matched_file
            ])).lower()

            rows.append({
                "source_name": src,
                "source_index": source_index,
                "status": status,
                "best_method": best_method,
                "best_confidence": best_conf if isinstance(best_conf, (int, float)) else -1.0,
                "matched_file": matched_file or "-",
                "lsp_result": lsp_result,
                "lsp_conf": lsp_conf,
                "jv_result": jv_result,
                "dcf_result": dcf_result,
                "wwz_result": wwz_result,
                "wwz_conf": wwz_conf,
                "search_text": search_text,
                "source_result": source_result,
                "skipped_info": skipped_info,
            })

        return rows

    def _find_processed_file_fast(
            self,
            source_name: str,
            processed_by_source: Dict[str, Dict[str, Any]],
            processed_files: List[Any],
    ) -> str:
        item = processed_by_source.get(source_name)
        if isinstance(item, dict):
            for key in ("matched_file", "file_name", "path", "source_file", "file"):
                value = item.get(key)
                if value:
                    return str(value)

        # 兜底：如果你原来的函数能找到，就用原来的
        try:
            return self._find_processed_file_for_source(source_name, processed_files)
        except Exception:
            return ""

    def _clear_results_view(self, message: str = "结果：-"):
        self.results_info_label.setText(message)
        self.results_table.blockSignals(True)
        self.results_table.setRowCount(0)
        self.results_table.blockSignals(False)
        self._results_visible_sources = []
        self.current_result_selected_source = None

    def _fill_results_table(self, sources: List[str], merged: Dict[str, Any]):
        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}

        self.results_table.setUpdatesEnabled(False)
        self.results_table.blockSignals(True)
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(len(sources))

        for row, src in enumerate(sources):
            source_result = results.get(src, {}) if isinstance(results.get(src, {}), dict) else {}
            status = str(source_result.get("status", "-"))

            skipped_info = None
            if not source_result and isinstance(skipped_sources, dict):
                for file_key, info in skipped_sources.items():
                    if isinstance(info, dict) and str(info.get("source_name") or file_key) == src:
                        skipped_info = info
                        break

            if skipped_info is not None and not source_result:
                status = "skipped"

            source_index = self._extract_source_index(src)
            source_index_text = str(source_index) if source_index is not None else "-"

            lsp_txt = self._method_summary_text("LSP", source_result.get("LSP"))
            lsp_conf = self._format_confidence_text(self._method_confidence_value("LSP", source_result.get("LSP")))

            jv_txt = self._method_summary_text("Jurkevich", source_result.get("Jurkevich"))
            dcf_txt = self._method_summary_text("DCF", source_result.get("DCF"))
            wwz_txt = self._method_summary_text("WWZ", source_result.get("WWZ"))
            wwz_conf = self._format_confidence_text(self._method_confidence_value("WWZ", source_result.get("WWZ")))

            values = [
                source_index_text,
                src,
                status,
                lsp_txt,
                lsp_conf,
                jv_txt,
                dcf_txt,
                wwz_txt,
                wwz_conf,
            ]

            for col, v in enumerate(values):
                item = QTableWidgetItem(str(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, src)

                if col in (0, 2, 4, 8):
                    item.setTextAlignment(Qt.AlignCenter)

                self.results_table.setItem(row, col, item)

        self.results_table.blockSignals(False)
        self.results_table.setSortingEnabled(False)
        self.results_table.setUpdatesEnabled(True)

    def _select_result_source(self, source_name: str):
        if not source_name:
            return

        self.current_result_selected_source = source_name

        row_idx = None
        for row, src in enumerate(self._results_visible_sources):
            if src == source_name:
                row_idx = row
                break

        if row_idx is not None:
            self.results_table.blockSignals(True)
            self.results_table.selectRow(row_idx)
            item = self.results_table.item(row_idx, 1)
            if item:
                self.results_table.scrollToItem(item, QAbstractItemView.PositionAtCenter)
            self.results_table.blockSignals(False)

    def on_results_table_selection_changed(self):
        selected = self.results_table.selectedItems()
        if not selected:
            return

        row = self.results_table.currentRow()
        if row < 0:
            return

        item = self.results_table.item(row, 1)  # 源名列
        if item is None:
            return

        source_name = item.text().strip()
        if source_name:
            self.current_result_selected_source = source_name

    def on_results_table_double_clicked(self, index):
        if not index.isValid():
            return

        row = index.row()
        item = self.results_table.item(row, 1)  # 源名列
        if item:
            self.open_result_detail_dialog(item.text().strip())

    def on_results_table_cell_double_clicked(self, row: int, column: int):
        item = self.results_table.item(row, 1)  # 源名列
        if item:
            self.open_result_detail_dialog(item.text().strip())

    def open_result_detail_dialog(self, source_name: str):
        if not source_name:
            return

        merged = self._results_state_cache or {}
        results = merged.get("results", {}) or {}
        skipped_sources = merged.get("skipped_sources", {}) or {}
        processed_files = merged.get("processed_files", []) or []

        source_result = results.get(source_name, {}) if isinstance(results.get(source_name, {}), dict) else {}
        skipped_info = None
        if not source_result and isinstance(skipped_sources, dict):
            for file_key, info in skipped_sources.items():
                if isinstance(info, dict) and str(info.get("source_name") or file_key) == source_name:
                    skipped_info = info
                    break

        source_idx = self._extract_source_index(source_name)
        matched_file = self._find_processed_file_for_source(source_name, processed_files)

        if source_result:
            status = str(source_result.get("status", "-"))
        elif skipped_info is not None:
            status = "skipped"
        else:
            status = "-"

        # 日期范围：尽量按你原来的逻辑算
        config = {}
        try:
            config = self.collect_config_from_ui(include_source_overrides=True)
        except Exception:
            config = self.current_config if isinstance(self.current_config, dict) else {}

        global_cfg = config.get("global", {}) if isinstance(config, dict) else {}
        src_override = {}
        if isinstance(config, dict):
            overrides = config.get("source_overrides", {}) or {}
            if source_idx is not None and str(source_idx) in overrides:
                src_override = overrides.get(str(source_idx), {}) or {}

        global_start = global_cfg.get("start_date")
        global_end = global_cfg.get("end_date")
        applied_start = source_result.get("applied_start_date")
        applied_end = source_result.get("applied_end_date")
        override_global = src_override.get("global", {}) if isinstance(src_override, dict) else {}
        override_start = override_global.get("start_date")
        override_end = override_global.get("end_date")

        effective_start = applied_start or override_start or global_start
        effective_end = applied_end or override_end or global_end

        def _date_text(v):
            if v is None:
                return "-"
            if isinstance(v, (list, tuple)) and len(v) >= 3:
                try:
                    return f"{int(v[0]):04d}-{int(v[1]):02d}-{int(v[2]):02d}"
                except Exception:
                    return str(v)
            return str(v)

        best_method, best_conf = self._best_method_info(source_result)

        method_rows = []
        for method_key in ["LSP", "Jurkevich", "DCF", "WWZ", "Beta"]:
            method_result = source_result.get(method_key)
            summary = self._method_summary_text(method_key, method_result)
            conf = self._method_confidence_value(method_key, method_result)
            image_path = self._find_method_image_path(source_name, method_key, merged)
            method_rows.append((method_key, summary, self._format_confidence_text(conf), image_path))

        raw_payload = {
            "source_name": source_name,
            "source_index": source_idx,
            "status": status,
            "matched_file": matched_file,
            "state_file_path": self._state_file_path,
            "merged_result": source_result,
            "skipped_info": skipped_info,
        }

        payload = {
            "source_name": source_name,
            "source_index": source_idx if source_idx is not None else "-",
            "status": status,
            "matched_file": matched_file or "-",
            "best_method": best_method,
            "best_confidence": self._format_confidence_text(best_conf),
            "date_range": f"{_date_text(effective_start)} ~ {_date_text(effective_end)}",
            "method_rows": method_rows,
            "raw_payload": raw_payload,
            "output_path": self.output_path_edit.text().strip(),
        }

        dialog = ResultDetailDialog(self, payload)
        self._detail_dialog_ref = dialog
        dialog.exec()

    def on_results_table_context_menu(self, pos):
        item = self.results_table.itemAt(pos)
        if item is None:
            return

        row = item.row()
        src_item = self.results_table.item(row, 1)  # 源名列
        if src_item is None:
            return

        source_name = src_item.text().strip()
        menu = QMenu(self)

        act_detail = menu.addAction("显示详细信息")
        act_copy = menu.addAction("复制源名")
        act_open_output = menu.addAction("打开输出目录")

        chosen = menu.exec(self.results_table.viewport().mapToGlobal(pos))
        if chosen is None:
            return

        if chosen == act_detail:
            self.open_result_detail_dialog(source_name)
        elif chosen == act_copy:
            QApplication.clipboard().setText(source_name)
            self.statusBar().showMessage(f"已复制：{source_name}", 3000)
        elif chosen == act_open_output:
            self.open_output_folder()


    def _find_method_image_path(self, source_name: str, method_key: str, merged: Dict[str, Any]) -> Optional[str]:
        spec = None
        for s in RESULT_IMAGE_SPECS:
            if s["key"] == method_key:
                spec = s
                break

        if spec is None:
            return None

        output_path = self.output_path_edit.text().strip()
        if not output_path or not os.path.isdir(output_path):
            return None

        return self._find_best_image_path(
            data_path=output_path,
            folder_name=spec["folder"],
            source_name=source_name,
            must_have=spec.get("must_have"),
            must_not_have=spec.get("must_not_have"),
        )

    # =====================================================
    # 文件预览 / 单源覆盖
    # =====================================================

    def update_preview_info_label(self):
        self.preview_info_label.setText(
            f"实际处理数量：{self.preview_effective_count} / "
            f"总文件数：{len(self.current_sorted_numbers)} / "
            f"保存的手动勾选：{len(self.selected_preview_numbers)} / "
            f"已保存覆盖：{len(self.source_overrides)} 个源"
        )

    def get_preview_selected_numbers(self) -> List[int]:
        nums = []
        for row in range(self.source_table.rowCount()):
            check_item = self.source_table.item(row, 0)
            num_item = self.source_table.item(row, 1)
            if check_item is not None and check_item.checkState() == Qt.Checked and num_item is not None:
                try:
                    nums.append(int(num_item.text()))
                except Exception:
                    pass
        return nums

    def _calc_default_selected_numbers(self) -> set[int]:
        try:
            file_numbers = self._parse_file_numbers_input(self.file_numbers_edit.text())
            return set(parse_target_numbers(file_numbers, available_numbers=self.current_file_map.keys()))
        except Exception:
            return set(self.current_sorted_numbers)

    def refresh_source_preview(self):
        if self._loading_config:
            return

        if self.current_selected_num is not None and not self.is_running:
            try:
                self.commit_current_source_override(silent=True)
            except Exception:
                pass

        folder = self.folder_path_edit.text().strip()
        file_type = self.file_type_combo.currentText().strip()

        self._preview_item_guard = True
        self.source_table.blockSignals(True)
        self.source_table.clearSelection()
        self.source_table.setRowCount(0)
        self.source_table.blockSignals(False)
        self._preview_item_guard = False

        self.current_file_map = {}
        self.current_sorted_numbers = []
        self.preview_effective_count = 0

        if not folder or not os.path.isdir(folder):
            self.estimated_total = 0
            self.update_preview_info_label()
            self.preview_info_label.setText("实际处理数量：0（输入目录无效）")
            self.clear_source_editor_view()
            return

        try:
            file_map = scan_numbered_files(folder, file_type=file_type)
        except Exception as e:
            self.estimated_total = 0
            self.preview_info_label.setText(f"实际处理数量：0（扫描失败：{e}）")
            self.clear_source_editor_view()
            return

        self.current_file_map = file_map
        self.current_sorted_numbers = sorted(file_map.keys())

        default_selected = set()
        try:
            file_numbers = self._parse_file_numbers_input(self.file_numbers_edit.text())
            default_selected = set(parse_target_numbers(file_numbers, available_numbers=file_map.keys()))
        except Exception:
            default_selected = set(self.current_sorted_numbers)

        manual_selected = set()
        for x in self.selected_preview_numbers:
            try:
                n = int(x)
            except Exception:
                continue
            if n in file_map:
                manual_selected.add(n)

        if self.use_manual_source_selection:
            checked_set = set()
            for x in self.selected_preview_numbers:
                try:
                    checked_set.add(int(x))
                except Exception:
                    pass
            effective_selected = checked_set
        else:
            checked_set = default_selected
            effective_selected = default_selected

        self.preview_effective_count = len(effective_selected)
        self.estimated_total = self.preview_effective_count

        self._preview_item_guard = True
        self.source_table.blockSignals(True)
        self.source_table.setRowCount(len(self.current_sorted_numbers))

        for row, num in enumerate(self.current_sorted_numbers):
            file_path = file_map[num]
            file_name = os.path.basename(file_path)

            override = self.source_overrides.get(str(num), {})
            override_flag = "是" if override else "否"
            override_summary = summarize_override(override, max_items=4)

            check_item = QTableWidgetItem("")
            check_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            check_item.setCheckState(Qt.Checked if num in checked_set else Qt.Unchecked)

            num_item = QTableWidgetItem(str(num))
            file_item = QTableWidgetItem(file_name)
            override_flag_item = QTableWidgetItem(override_flag)
            summary_item = QTableWidgetItem(override_summary)
            path_item = QTableWidgetItem(file_path)

            for item in [num_item, file_item, override_flag_item, summary_item, path_item]:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            num_item.setTextAlignment(Qt.AlignCenter)
            file_item.setTextAlignment(Qt.AlignCenter)
            override_flag_item.setTextAlignment(Qt.AlignCenter)

            self.source_table.setItem(row, 0, check_item)
            self.source_table.setItem(row, 1, num_item)
            self.source_table.setItem(row, 2, file_item)
            self.source_table.setItem(row, 3, override_flag_item)
            self.source_table.setItem(row, 4, summary_item)
            self.source_table.setItem(row, 5, path_item)

        self.source_table.blockSignals(False)
        self._preview_item_guard = False

        self.update_preview_info_label()

        target_num = None
        if self.current_selected_num is not None:
            try:
                if int(self.current_selected_num) in file_map:
                    target_num = int(self.current_selected_num)
            except Exception:
                pass

        if target_num is None and self.current_sorted_numbers:
            target_num = self.current_sorted_numbers[0]

        if target_num is not None:
            self.select_source_in_table(target_num)
        else:
            self.clear_source_editor_view()

        self._build_preview_row_cache()

    def select_source_in_table(self, num: int):
        row_idx = None
        for row in range(self.source_table.rowCount()):
            item = self.source_table.item(row, 1)
            if item is not None and int(item.text()) == num:
                row_idx = row
                break

        if row_idx is None:
            return

        self.source_table.blockSignals(True)
        self.source_table.selectRow(row_idx)
        self.source_table.scrollToItem(self.source_table.item(row_idx, 0), QAbstractItemView.PositionAtCenter)
        self.source_table.blockSignals(False)

        file_path = self.current_file_map.get(num, "")
        self.load_selected_source_into_editor(str(num), file_path)

    def on_source_table_selection_changed(self):
        selected = self.source_table.selectedItems()
        if not selected:
            self.clear_source_editor_view()
            return

        row = self.source_table.currentRow()
        if row < 0:
            self.clear_source_editor_view()
            return

        num_item = self.source_table.item(row, 1)
        path_item = self.source_table.item(row, 5)

        if num_item is None:
            self.clear_source_editor_view()
            return

        try:
            num = str(int(num_item.text()))
        except Exception:
            self.clear_source_editor_view()
            return

        if self.current_selected_num is not None and not self.is_running:
            prev_num = str(self.current_selected_num)
            if prev_num != num:
                self.commit_current_source_override(silent=True)
                self.update_preview_row_override(prev_num)

        self.load_selected_source_into_editor(num, path_item.text() if path_item else "")

    def update_preview_row_override(self, num: str):
        try:
            num_int = int(num)
        except Exception:
            return

        for row in range(self.source_table.rowCount()):
            item = self.source_table.item(row, 1)
            if item is not None and int(item.text()) == num_int:
                override = self.source_overrides.get(str(num_int), {})
                override_flag = "是" if override else "否"
                override_summary = summarize_override(override, max_items=4)
                self.source_table.item(row, 3).setText(override_flag)
                self.source_table.item(row, 4).setText(override_summary)
                break

        self.update_preview_info_label()

    def clear_source_editor_view(self):
        self.current_selected_num = None
        self.current_selected_file_path = ""
        self.source_title_label.setText("当前源：未选择")
        self.source_summary_label.setText("覆盖摘要：默认配置")
        self.update_source_editor_enable_state()

    def load_selected_source_into_editor(self, source_num: str, file_path: str = ""):
        self.current_selected_num = str(source_num)
        self.current_selected_file_path = file_path

        # 获取当前主界面的全局配置作为基准
        base_cfg = self.collect_config_from_ui(include_source_overrides=False)
        global_cfg_base = base_cfg.get("global", {})

        # 获取当前源的覆盖配置（如果刚才清除了，这里就是空字典 {}）
        override = self.source_overrides.get(str(source_num), {})

        # 将覆盖合并到基准配置上
        effective_cfg = deep_merge(base_cfg, override)
        global_cfg = effective_cfg.get("global", {})

        self.source_title_label.setText(f"当前源：#{source_num}    {os.path.basename(file_path) if file_path else ''}")
        self.source_summary_label.setText(f"覆盖摘要：{summarize_override(override, max_items=8)}")

        # ==========================================
        # 以下是重置 UI 控件，确保它们显示的是合并后的值
        # 如果 override 是空的，这里显示的就是全局 base 值
        # ==========================================

        # 设置日期
        set_optional_date_widgets(self.src_start_date_check, self.src_start_date_edit, global_cfg.get("start_date"))
        set_optional_date_widgets(self.src_end_date_check, self.src_end_date_edit, global_cfg.get("end_date"))

        # 设置移除上限
        self.src_remove_upper_limit_check.setChecked(
            bool_value(global_cfg.get("remove_upper_limit", True), True)
        )
        self.src_remove_max_value_spin.setValue(
            int_value(global_cfg.get("remove_max_value_numbers", 0), 0)
        )

        self.update_source_editor_enable_state()

    def build_source_override_from_editor(self, base_cfg: Dict[str, Any]) -> Dict[str, Any]:
        override: Dict[str, Any] = {}
        base_global = base_cfg.get("global", {})

        global_override: Dict[str, Any] = {}

        src_start = get_optional_date_value(self.src_start_date_check, self.src_start_date_edit)
        src_end = get_optional_date_value(self.src_end_date_check, self.src_end_date_edit)

        base_start = normalize_optional_date_value(base_global.get("start_date"))
        base_end = normalize_optional_date_value(base_global.get("end_date"))

        if src_start is None:
            if base_start is not None:
                global_override["start_date"] = None
        else:
            if base_start != src_start:
                global_override["start_date"] = src_start

        if src_end is None:
            if base_end is not None:
                global_override["end_date"] = None
        else:
            if base_end != src_end:
                global_override["end_date"] = src_end

        if bool_value(self.src_remove_upper_limit_check.isChecked()) != bool_value(base_global.get("remove_upper_limit", True), True):
            global_override["remove_upper_limit"] = self.src_remove_upper_limit_check.isChecked()

        if int_value(self.src_remove_max_value_spin.value(), 0) != int_value(base_global.get("remove_max_value_numbers", 0), 0):
            global_override["remove_max_value_numbers"] = self.src_remove_max_value_spin.value()

        if global_override:
            override["global"] = global_override

        return override

    def commit_current_source_override(self, silent: bool = False):
        """
        保存当前选中源的覆盖配置。
        这里只保存“与主界面不同的全局字段”，不保存方法开关。
        """
        if self.current_selected_num is None:
            return

        base_cfg = self.collect_config_from_ui(include_source_overrides=False)
        override_cfg = sanitize_source_override(self.build_source_override_from_editor(base_cfg))

        num_str = str(self.current_selected_num)
        if override_cfg:
            self.source_overrides[num_str] = override_cfg
        else:
            self.source_overrides.pop(num_str, None)

        self.current_config["source_overrides"] = copy.deepcopy(self.source_overrides)

        if not silent:
            self.append_log(f"[GUI] 已保存源 {num_str} 的单源覆盖（仅差异项）")

    def save_current_source_override(self):
        if self.current_selected_num is None:
            QMessageBox.information(self, "提示", "请先在左侧选择一个文件。")
            return
        self.commit_current_source_override(silent=False)
        self.refresh_source_preview()
        self.select_source_by_num_after_refresh(self.current_selected_num)

    def clear_current_source_override(self):
        if self.current_selected_num is None:
            QMessageBox.information(self, "提示", "请先在左侧选择一个文件。")
            return

        num = str(self.current_selected_num)

        # 1. 从内存字典中彻底删除
        self.source_overrides.pop(num, None)
        if "source_overrides" in self.current_config:
            self.current_config["source_overrides"].pop(num, None)

        # 2. 关键：立即重置当前的编辑器界面，加载“全局配置”的值
        # 我们调用 load_selected_source_into_editor，它内部会自动读取最新的 global 配置
        self.load_selected_source_into_editor(num, self.current_selected_file_path)

        # 3. 刷新表格状态（把“是”变成“否”，更新摘要）
        self.refresh_source_preview()

        # 4. 重新选中当前源，确保用户还在刚才的位置
        self.select_source_by_num_after_refresh(num)

        self.statusBar().showMessage(f"已清除源 #{num} 的单源覆盖配置", 3000)

    def reload_current_source_override(self):
        if self.current_selected_num is None:
            QMessageBox.information(self, "提示", "请先在左侧选择一个文件。")
            return
        self.load_selected_source_into_editor(self.current_selected_num, self.current_selected_file_path)

    def select_source_by_num_after_refresh(self, num: str):
        try:
            num_int = int(num)
        except Exception:
            return
        if num_int in self.current_file_map:
            self.select_source_in_table(num_int)

    # =====================================================
    # 运行 / 停止
    # =====================================================

    def start_process(self):
        if self.process is not None and self.process.state() == QProcess.Running:
            QMessageBox.warning(self, "提示", "任务正在运行中，请先停止。")
            return

        self._drop_dead_process_object()

        if not os.path.exists(DEFAULT_RUNNER_PATH):
            QMessageBox.critical(self, "错误", f"找不到运行入口：{DEFAULT_RUNNER_PATH}")
            return

        try:
            self.commit_current_source_override(silent=True)
            self.save_config_to_disk_silent()
        except Exception as e:
            QMessageBox.critical(self, "保存配置失败", str(e))
            return

        cfg = self.collect_config_from_ui(include_source_overrides=True)
        folder_path = cfg.get("global", {}).get("folder_path", "")
        output_path = cfg.get("global", {}).get("output_path", "")

        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "提示", "输入目录无效，请先设置正确的 folder_path。")
            return
        if not output_path:
            QMessageBox.warning(self, "提示", "输出目录不能为空。")
            return

        self.refresh_source_preview()

        self.clear_log()
        self.processed_count = 0
        self._process_finalized = False

        if self.estimated_total > 0:
            self.progress_bar.setRange(0, self.estimated_total)
            self.progress_bar.setValue(0)
        else:
            self.progress_bar.setRange(0, 0)

        self.status_label.setText("准备启动...")
        self.statusBar().showMessage("正在启动任务...")

        self.stop_requested = False
        self.process = QProcess(self)
        self.process.setWorkingDirectory(PROJECT_ROOT)

        self.process.readyReadStandardOutput.connect(self.on_stdout_ready)
        self.process.readyReadStandardError.connect(self.on_stderr_ready)
        self.process.finished.connect(self.on_process_finished)
        self.process.errorOccurred.connect(self.on_process_error)
        self.process.stateChanged.connect(self.on_process_state_changed)

        python_exec = sys.executable
        config_base = config_base_from_path(self.config_path_edit.text().strip() or self.current_config_path)

        args = [
            "-u",
            DEFAULT_RUNNER_PATH,
            "--config",
            config_base,
        ]

        self.append_log(f"[GUI] 启动命令：{python_exec} {' '.join(args)}")
        self.append_log(f"[GUI] 工作目录：{PROJECT_ROOT}")
        self.append_log(
            f"[GUI] 配置文件：{normalize_json_path(self.config_path_edit.text().strip() or self.current_config_path)}"
        )
        self.refresh_results_view(reload_disk=True)
        self._set_running_state(True)
        self.process.start(python_exec, args)

        if not self.process.waitForStarted(5000):
            err = self.process.errorString()
            self._finalize_process(success=False, message=f"任务启动失败：{err}")
            QMessageBox.critical(self, "启动失败", f"任务启动失败：\n{err}")

    def stop_process(self):
        if self.process is None or self.process.state() == QProcess.NotRunning:
            self._finalize_process(success=False, message="检测到任务已结束，界面已恢复为可再次运行状态。")
            return

        self.stop_requested = True
        self.append_log("[GUI] 正在请求停止任务...")
        self.status_label.setText("正在停止...")

        try:
            self.process.terminate()
        except Exception:
            pass

        QTimer.singleShot(3000, self._force_kill_if_needed)

    def on_process_state_changed(self, state):
        if state == QProcess.NotRunning and self.is_running and not self._process_finalized:
            QTimer.singleShot(0, self._maybe_finalize_if_still_not_running)

    def on_stdout_ready(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="ignore")
        if not data:
            return
        self.append_log(data)
        self._parse_progress_from_log(data)

    def on_stderr_ready(self):
        if self.process is None:
            return
        data = bytes(self.process.readAllStandardError()).decode("utf-8", errors="ignore")
        if not data:
            return
        self.append_log(data, is_error=True)

    def on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus):
        if self._process_finalized:
            return

        if self.stop_requested:
            self.append_log("[GUI] 任务已停止。")
            self._finalize_process(success=False, message="任务已停止。")
            return

        self.append_log(f"[GUI] 任务结束，exit_code={exit_code}, exit_status={exit_status.value}")

        if exit_status == QProcess.NormalExit and exit_code == 0:
            try:
                self.refresh_results_view(reload_disk=True)
            except Exception:
                pass
            self._finalize_process(success=True)
            try:
                self.refresh_results_view(reload_disk=True)
            except Exception:
                pass
        else:
            try:
                self.refresh_results_view(reload_disk=True)
            except Exception:
                pass
            self._finalize_process(success=False, message=f"任务未正常完成，exit_code={exit_code}")
            try:
                self.refresh_results_view(reload_disk=True)
            except Exception:
                pass

    def on_process_error(self, error):
        if self._process_finalized:
            return

        err_text = self.process.errorString() if self.process else str(error)
        self.append_log(f"[GUI] 进程错误：{err_text}", is_error=True)
        self._finalize_process(success=False, message=err_text)


    def _parse_progress_from_log(self, text: str):
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("读取文件:"):
                self.processed_count += 1
                if self.estimated_total > 0:
                    self.progress_bar.setRange(0, self.estimated_total)
                    self.progress_bar.setValue(min(self.processed_count, self.estimated_total))
                    self.status_label.setText(f"正在运行：{self.processed_count}/{self.estimated_total}")
            elif "全部源已经计算完毕" in line:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)
                self.status_label.setText("运行完成")

    # =====================================================
    # 日志 / 状态
    # =====================================================

    def append_log(self, text: str, is_error: bool = False):
        if not text:
            return

        text = text.replace("\r\n", "\n").replace("\r", "\n")
        for line in text.split("\n"):
            if not line:
                continue
            if is_error:
                self.log_edit.appendPlainText(f"[ERR] {line}")
            else:
                self.log_edit.appendPlainText(line)

        sb = self.log_edit.verticalScrollBar()
        sb.setValue(sb.maximum())

    def clear_log(self):
        self.log_edit.clear()

    def set_widgets_enabled(self, widgets: Iterable[QWidget], enabled: bool):
        for w in widgets:
            if w is not None:
                w.setEnabled(enabled)

    def update_source_editor_enable_state(self):
        enabled = (not self.is_running) and (self.current_selected_num is not None)
        self.set_widgets_enabled(self.source_editor_widgets, enabled)
        self.btn_save_source_override.setEnabled(enabled)
        self.btn_clear_source_override.setEnabled(enabled)
        self.btn_reload_source_override.setEnabled(enabled)

    def _set_running_state(self, running: bool):
        self.is_running = running

        self.btn_run.setEnabled(not running)
        self.btn_stop.setEnabled(running)

        self.set_widgets_enabled(self.run_block_widgets, not running)
        self.update_source_editor_enable_state()

        self.source_table.setEnabled(True)
        self.tabs.setEnabled(True)
        self.log_edit.setEnabled(True)
        self.btn_open_output.setEnabled(True)
        self.btn_clear_log.setEnabled(True)

        if not running and self.status_label.text() == "正在停止...":
            self.status_label.setText("就绪")

        if hasattr(self, "results_refresh_timer") and self.results_refresh_timer is not None:
            if running:
                self.results_refresh_timer.start()
            else:
                self.results_refresh_timer.stop()

    # =====================================================
    # 关闭事件
    # =====================================================

    def closeEvent(self, event):
        if self.process is not None and self.process.state() != QProcess.NotRunning:
            reply = QMessageBox.question(
                self,
                "确认退出",
                "任务正在运行，确定要退出吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                event.ignore()
                return
            self.process.kill()
        event.accept()


# =========================================================
# 启动
# =========================================================

def run_app():
    # 这一行一定要加在 QApplication 创建之前
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
    os.environ["QT_AUTOSCREENSCALEFACTOR"] = "1"

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("astrolightcurve.viewer")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon("assets/app_v2.ico"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
