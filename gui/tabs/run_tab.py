from typing import Any, Dict, List, Tuple

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..ui_helpers import make_check_row, make_form_group, make_optional_date_row, make_path_row


def build_run_tab(main) -> Tuple[QWidget, Dict[str, Any], List[QWidget]]:
    """
    返回：
    - page
    - refs：需要回填到 MainWindow 上的控件
    - run_block_widgets：运行中需要禁用的控件列表
    """
    page = QWidget()
    layout = QVBoxLayout(page)

    splitter = QSplitter(Qt.Horizontal)
    layout.addWidget(splitter, 1)

    param_scroll, param_refs, run_block_widgets = build_parameter_panel(main)
    log_panel, log_refs = build_log_panel(main)

    splitter.addWidget(param_scroll)
    splitter.addWidget(log_panel)
    splitter.setStretchFactor(0, 1)
    splitter.setStretchFactor(1, 2)
    splitter.setSizes([700, 1400])

    refs: Dict[str, Any] = {}
    refs.update(param_refs)
    refs.update(log_refs)

    return page, refs, run_block_widgets


def build_parameter_panel(main) -> Tuple[QScrollArea, Dict[str, Any], List[QWidget]]:
    content = QWidget()
    layout = QVBoxLayout(content)

    # =========================
    # 任务基础设置
    # =========================
    folder_path_edit = QLineEdit()
    folder_path_edit.setPlaceholderText("输入目录 folder_path")
    btn_browse_folder = QPushButton("选择")

    output_path_edit = QLineEdit()
    output_path_edit.setPlaceholderText("输出目录 output_path")
    btn_browse_output = QPushButton("选择")

    mode_combo = QComboBox()
    mode_combo.addItems(["customize"])

    file_type_combo = QComboBox()
    file_type_combo.addItems(["csv", "txt"])

    file_numbers_edit = QLineEdit()
    file_numbers_edit.setPlaceholderText("例如：-1 / 10-15 / 1,3,7 / 5")

    min_points_per_cycle = QSpinBox()
    min_points_per_cycle.setRange(1, 100)

    state_filename_edit = QLineEdit()
    state_filename_edit.setPlaceholderText("state")

    rerun_check = QCheckBox("重新计算（rerun）")

    task_group = make_form_group("任务基础设置", [
        ("输入目录", make_path_row(folder_path_edit, btn_browse_folder)),
        ("输出目录", make_path_row(output_path_edit, btn_browse_output)),
        ("运行模式", mode_combo),
        ("文件类型", file_type_combo),
        ("文件编号范围", file_numbers_edit),
        ("状态文件名", state_filename_edit),
        ("周期中最小点数", min_points_per_cycle),
        ("重新计算", rerun_check),
    ])

    # =========================
    # 日期与清洗
    # =========================
    global_start_date_check = QCheckBox("启用开始日期")
    global_start_date_edit = QDateEdit()
    global_start_date_edit.setDisplayFormat("yyyy-MM-dd")
    global_start_date_edit.setCalendarPopup(True)
    global_start_date_edit.setDate(QDate.currentDate())

    global_end_date_check = QCheckBox("启用结束日期")
    global_end_date_edit = QDateEdit()
    global_end_date_edit.setDisplayFormat("yyyy-MM-dd")
    global_end_date_edit.setCalendarPopup(True)
    global_end_date_edit.setDate(QDate.currentDate())

    global_remove_upper_limit_check = QCheckBox("移除上限值（remove_upper_limit）")
    global_remove_max_value_spin = QSpinBox()
    global_remove_max_value_spin.setRange(0, 10_000_000)

    constant_flux = QCheckBox()

    constant_flux_values = QSpinBox()
    constant_flux_values.setRange(0, 10_000)

    date_group = make_form_group("日期与清洗", [
        ("开始日期", make_optional_date_row(global_start_date_check, global_start_date_edit)),
        ("结束日期", make_optional_date_row(global_end_date_check, global_end_date_edit)),
        ("", global_remove_upper_limit_check),
        ("移除最大值数量", global_remove_max_value_spin),
        ("常数化流值", constant_flux),
        ("常数流值", constant_flux_values),
    ])

    # =========================
    # 输出设置
    # =========================
    gen_light_plot_check = QCheckBox("生成光变图（gen_light_plot）")
    export_docx_check = QCheckBox("运行完成后导出 DOCX 报告")
    export_docx_check.setChecked(True)

    docx_name = QLineEdit()
    state_filename_edit.setPlaceholderText("设置输出文件名称")

    output_group = make_form_group("输出设置", [
        ("", gen_light_plot_check),
        ("", export_docx_check),
        ("DOCX 名称", docx_name),
    ])

    # =========================
    # customize 方法开关
    # =========================
    custom_lsp_check = QCheckBox("LSP")
    custom_lsp_plot_check = QCheckBox("LSP_Plot")
    custom_jv_check = QCheckBox("Jurkevich")
    custom_jv_plot_check = QCheckBox("JV_Plot")
    custom_dcf_check = QCheckBox("DCF")
    custom_dcf_plot_check = QCheckBox("DCF_Plot")
    custom_wwz_check = QCheckBox("WWZ")
    custom_wwz_plot_check = QCheckBox("WWZ_Plot")

    method_row1 = make_check_row(
        custom_lsp_check, custom_lsp_plot_check, custom_jv_check, custom_jv_plot_check
    )
    method_row2 = make_check_row(
        custom_dcf_check, custom_dcf_plot_check, custom_wwz_check, custom_wwz_plot_check
    )

    method_group = QWidget()
    method_group_layout = QVBoxLayout(method_group)
    method_group_layout.setContentsMargins(0, 0, 0, 0)
    method_group_layout.addWidget(QLabel("customize 方法开关"))
    method_group_layout.addWidget(method_row1)
    method_group_layout.addWidget(method_row2)

    # =========================
    # Beta 参数
    # =========================
    beta_calculate_check = QCheckBox("beta_calculate")

    beta_default_beta = QDoubleSpinBox()
    beta_default_beta.setRange(0.0, 100.0)
    beta_default_beta.setDecimals(6)
    beta_default_beta.setSingleStep(0.1)

    beta_method_combo = QComboBox()
    beta_method_combo.addItems(["psresp", "log"])

    beta_start = QDoubleSpinBox()
    beta_start.setRange(0.0, 100.0)
    beta_start.setDecimals(6)
    beta_start.setSingleStep(0.1)

    beta_end = QDoubleSpinBox()
    beta_end.setRange(0.0, 100.0)
    beta_end.setDecimals(6)
    beta_end.setSingleStep(0.1)

    beta_step = QDoubleSpinBox()
    beta_step.setRange(0.000001, 100.0)
    beta_step.setDecimals(6)
    beta_step.setSingleStep(0.1)

    beta_M = QSpinBox()
    beta_M.setRange(1, 1_000_000_000)

    beta_n_jobs = QSpinBox()
    beta_n_jobs.setRange(-1, 1_000_000)

    beta_plot_check = QCheckBox("plot")

    beta_n_bins = QSpinBox()
    beta_n_bins.setRange(1, 1_000_000)

    beta_plot_mode = QComboBox()
    beta_plot_mode.addItems(["save", "show"])

    beta_group = make_form_group("Beta 参数", [
        ("beta_calculate", beta_calculate_check),
        ("default_beta", beta_default_beta),
        ("method", beta_method_combo),
        ("beta_start", beta_start),
        ("beta_end", beta_end),
        ("beta_step", beta_step),
        ("M", beta_M),
        ("n_jobs", beta_n_jobs),
        ("plot", beta_plot_check),
        ("n_bins", beta_n_bins),
        ("plot_mode", beta_plot_mode),
    ])

    # =========================
    # LSP 参数
    # =========================
    lsp_divide_freq_step = QSpinBox()
    lsp_divide_freq_step.setRange(1, 1_000_000)

    lsp_sig_threshold = QDoubleSpinBox()
    lsp_sig_threshold.setRange(0.0, 1.0)
    lsp_sig_threshold.setDecimals(8)
    lsp_sig_threshold.setSingleStep(0.001)

    lsp_top_n = QSpinBox()
    lsp_top_n.setRange(1, 1_000_000)

    lsp_MC_check = QCheckBox("MC")

    lsp_M = QSpinBox()
    lsp_M.setRange(1, 1_000_000_000)

    lsp_n_jobs = QSpinBox()
    lsp_n_jobs.setRange(-1, 1_000_000_000)

    lsp_plot_mode = QComboBox()
    lsp_plot_mode.addItems(["save", "show"])

    lsp_method_combo = QComboBox()
    lsp_method_combo.addItems(["lsp", "glsp"])

    lsp_time_axis_mode = QComboBox()
    lsp_time_axis_mode.addItems(["jd", "ym"])

    lsp_time_input_format = QComboBox()
    lsp_time_input_format.addItems(["jd", "mjd"])

    lsp_group = make_form_group("LSP 参数", [
        ("mode", lsp_method_combo),
        ("divide_freq_step", lsp_divide_freq_step),
        ("sig_threshold", lsp_sig_threshold),
        ("top_n", lsp_top_n),
        ("MC", lsp_MC_check),
        ("M", lsp_M),
        ("n_jobs", lsp_n_jobs),
        ("plot_mode", lsp_plot_mode),
        ("time_axis_mode", lsp_time_axis_mode),
        ("time_input_format", lsp_time_input_format),
    ])

    # =========================
    # WWZ 参数
    # =========================
    wwz_c = QDoubleSpinBox()
    wwz_c.setRange(0.0, 100.0)
    wwz_c.setDecimals(8)
    wwz_c.setSingleStep(0.0001)

    wwz_p_start = QDoubleSpinBox()
    wwz_p_start.setRange(0.0000001, 1_000_000.0)
    wwz_p_start.setDecimals(8)
    wwz_p_start.setSingleStep(10)

    wwz_p_end = QDoubleSpinBox()
    wwz_p_end.setRange(0.0000001, 1_000_000.0)
    wwz_p_end.setDecimals(8)
    wwz_p_end.setSingleStep(10)

    wwz_divide_freq_step = QSpinBox()
    wwz_divide_freq_step.setRange(1, 1_000_000)

    wwz_tau_number = QSpinBox()
    wwz_tau_number.setRange(1, 1_000_000_000)

    wwz_z_height = QSpinBox()
    wwz_z_height.setRange(1, 1_000_000_000)

    wwz_MC_check = QCheckBox("MC")

    wwz_M = QSpinBox()
    wwz_M.setRange(1, 1_000_000_000)

    wwz_n_jobs = QSpinBox()
    wwz_n_jobs.setRange(-1, 1_000_000_000)

    wwz_sig_threshold = QDoubleSpinBox()
    wwz_sig_threshold.setRange(0.0, 1.0)
    wwz_sig_threshold.setDecimals(8)
    wwz_sig_threshold.setSingleStep(0.001)

    wwz_top_n = QSpinBox()
    wwz_top_n.setRange(1, 1_000_000_000)

    wwz_plot_mode = QComboBox()
    wwz_plot_mode.addItems(["save", "show"])

    wwz_time_scale = QComboBox()
    wwz_time_scale.addItems(["JD", "MJD"])

    wwz_peak_prominence = QDoubleSpinBox()
    wwz_peak_prominence.setRange(0.0, 1_000_000.0)
    wwz_peak_prominence.setDecimals(6)
    wwz_peak_prominence.setSingleStep(0.2)

    wwz_use_log_scale_period = QCheckBox("use_log_scale_period")

    wwz_group = make_form_group("WWZ 参数", [
        ("c", wwz_c),
        ("p_start", wwz_p_start),
        ("p_end", wwz_p_end),
        ("divide_freq_step", wwz_divide_freq_step),
        ("tau_number", wwz_tau_number),
        ("z_height", wwz_z_height),
        ("MC", wwz_MC_check),
        ("M", wwz_M),
        ("n_jobs", wwz_n_jobs),
        ("sig_threshold", wwz_sig_threshold),
        ("top_n", wwz_top_n),
        ("plot_mode", wwz_plot_mode),
        ("time_scale", wwz_time_scale),
        ("peak_prominence", wwz_peak_prominence),
        ("use_log_scale_period", wwz_use_log_scale_period),
    ])

    # =========================
    # Jurkevich 参数
    # =========================
    custom_jv_start = QSpinBox()
    custom_jv_start.setRange(1, 1_000_000_000)

    custom_jv_end = QSpinBox()
    custom_jv_end.setRange(1, 1_000_000_000)

    custom_jv_step = QSpinBox()
    custom_jv_step.setRange(1, 1_000_000_000)

    custom_jv_bins = QSpinBox()
    custom_jv_bins.setRange(1, 1_000_000)

    custom_jv_plot_mode = QComboBox()
    custom_jv_plot_mode.addItems(["save", "show"])

    jv_group = make_form_group("Jurkevich 参数", [
        ("test_periods_start", custom_jv_start),
        ("test_periods_end", custom_jv_end),
        ("test_periods_step", custom_jv_step),
        ("m_bins", custom_jv_bins),
        ("plot_mode", custom_jv_plot_mode),
    ])

    # =========================
    # DCF 参数
    # =========================
    custom_dcf_delta_tau = QSpinBox()
    custom_dcf_delta_tau.setRange(1, 1_000_000)

    custom_dcf_c = QSpinBox()
    custom_dcf_c.setRange(1, 1_000_000)

    custom_dcf_max_tau = QSpinBox()
    custom_dcf_max_tau.setRange(1, 1_000_000_000)

    custom_dcf_distance = QSpinBox()
    custom_dcf_distance.setRange(1, 1_000_000)

    custom_dcf_plot_mode = QComboBox()
    custom_dcf_plot_mode.addItems(["save", "show"])

    dcf_group = make_form_group("DCF 参数", [
        ("delta_tau", custom_dcf_delta_tau),
        ("c", custom_dcf_c),
        ("max_tau", custom_dcf_max_tau),
        ("distance", custom_dcf_distance),
        ("plot_mode", custom_dcf_plot_mode),
    ])

    # =========================
    # 排版
    # =========================
    layout.addWidget(task_group)
    layout.addWidget(date_group)
    layout.addWidget(output_group)
    layout.addWidget(method_group)
    layout.addWidget(beta_group)
    layout.addWidget(lsp_group)
    layout.addWidget(wwz_group)
    layout.addWidget(jv_group)
    layout.addWidget(dcf_group)
    layout.addStretch(1)

    # =========================
    # 控件引用
    # =========================
    refs: Dict[str, Any] = {
        "folder_path_edit": folder_path_edit,
        "btn_browse_folder": btn_browse_folder,
        "output_path_edit": output_path_edit,
        "btn_browse_output": btn_browse_output,
        "mode_combo": mode_combo,
        "file_type_combo": file_type_combo,
        "file_numbers_edit": file_numbers_edit,
        "state_filename_edit": state_filename_edit,
        "min_points_per_cycle":min_points_per_cycle,
        "rerun_check": rerun_check,

        "global_start_date_check": global_start_date_check,
        "global_start_date_edit": global_start_date_edit,
        "global_end_date_check": global_end_date_check,
        "global_end_date_edit": global_end_date_edit,
        "global_remove_upper_limit_check": global_remove_upper_limit_check,
        "global_remove_max_value_spin": global_remove_max_value_spin,
        "constant_flux":constant_flux,
        "constant_flux_values":constant_flux_values,

        "gen_light_plot_check": gen_light_plot_check,
        "export_docx_check": export_docx_check,
        "docx_name":docx_name,

        "custom_lsp_check": custom_lsp_check,
        "custom_lsp_plot_check": custom_lsp_plot_check,
        "custom_jv_check": custom_jv_check,
        "custom_jv_plot_check": custom_jv_plot_check,
        "custom_dcf_check": custom_dcf_check,
        "custom_dcf_plot_check": custom_dcf_plot_check,
        "custom_wwz_check": custom_wwz_check,
        "custom_wwz_plot_check": custom_wwz_plot_check,

        "custom_jv_start": custom_jv_start,
        "custom_jv_end": custom_jv_end,
        "custom_jv_step": custom_jv_step,
        "custom_jv_bins": custom_jv_bins,
        "custom_jv_plot_mode": custom_jv_plot_mode,

        "custom_dcf_delta_tau": custom_dcf_delta_tau,
        "custom_dcf_c": custom_dcf_c,
        "custom_dcf_max_tau": custom_dcf_max_tau,
        "custom_dcf_distance": custom_dcf_distance,
        "custom_dcf_plot_mode": custom_dcf_plot_mode,

        "beta_calculate_check": beta_calculate_check,
        "beta_default_beta": beta_default_beta,
        "beta_method_combo": beta_method_combo,
        "beta_start": beta_start,
        "beta_end": beta_end,
        "beta_step": beta_step,
        "beta_M": beta_M,
        "beta_n_jobs": beta_n_jobs,
        "beta_plot_check": beta_plot_check,
        "beta_n_bins": beta_n_bins,
        "beta_plot_mode": beta_plot_mode,

        "lsp_method_combo":lsp_method_combo,
        "lsp_divide_freq_step": lsp_divide_freq_step,
        "lsp_sig_threshold": lsp_sig_threshold,
        "lsp_top_n": lsp_top_n,
        "lsp_MC_check": lsp_MC_check,
        "lsp_M": lsp_M,
        "lsp_n_jobs": lsp_n_jobs,
        "lsp_plot_mode": lsp_plot_mode,
        "lsp_time_axis_mode": lsp_time_axis_mode,
        "lsp_time_input_format": lsp_time_input_format,

        "wwz_c": wwz_c,
        "wwz_p_start": wwz_p_start,
        "wwz_p_end": wwz_p_end,
        "wwz_divide_freq_step": wwz_divide_freq_step,
        "wwz_tau_number": wwz_tau_number,
        "wwz_z_height": wwz_z_height,
        "wwz_MC_check": wwz_MC_check,
        "wwz_M": wwz_M,
        "wwz_n_jobs": wwz_n_jobs,
        "wwz_sig_threshold": wwz_sig_threshold,
        "wwz_top_n": wwz_top_n,
        "wwz_plot_mode": wwz_plot_mode,
        "wwz_time_scale": wwz_time_scale,
        "wwz_peak_prominence": wwz_peak_prominence,
        "wwz_use_log_scale_period": wwz_use_log_scale_period,
    }

    # =========================
    # 运行中需要禁用的控件
    # 注意：这里尽量保持你原来注册的内容，不额外增加 export_docx_check
    # =========================
    run_block_widgets: List[QWidget] = [
        folder_path_edit, btn_browse_folder,
        output_path_edit, btn_browse_output,min_points_per_cycle,
        mode_combo, file_type_combo, file_numbers_edit,
        state_filename_edit, rerun_check,
        global_start_date_check, global_start_date_edit,
        global_end_date_check, global_end_date_edit,
        global_remove_upper_limit_check, global_remove_max_value_spin,
        gen_light_plot_check,constant_flux_values,constant_flux,
        custom_lsp_check, custom_lsp_plot_check,
        custom_jv_check, custom_jv_plot_check,
        custom_dcf_check, custom_dcf_plot_check,
        custom_wwz_check, custom_wwz_plot_check,
        custom_jv_start, custom_jv_end, custom_jv_step, custom_jv_bins, custom_jv_plot_mode,
        custom_dcf_delta_tau, custom_dcf_c, custom_dcf_max_tau, custom_dcf_distance, custom_dcf_plot_mode,
        beta_calculate_check, beta_default_beta, beta_method_combo, beta_start, beta_end, beta_step,
        beta_M, beta_n_jobs, beta_plot_check, beta_n_bins, beta_plot_mode,
        lsp_divide_freq_step, lsp_sig_threshold, lsp_top_n, lsp_MC_check, lsp_M, lsp_n_jobs,
        lsp_plot_mode, lsp_time_axis_mode, lsp_time_input_format, lsp_method_combo,
        wwz_c, wwz_p_start, wwz_p_end, wwz_divide_freq_step,
        wwz_tau_number, wwz_z_height, wwz_MC_check, wwz_M, wwz_n_jobs,
        wwz_sig_threshold, wwz_top_n, wwz_plot_mode, wwz_time_scale,
        wwz_peak_prominence, wwz_use_log_scale_period,
    ]

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(content)
    return scroll, refs, run_block_widgets


def build_log_panel(main) -> Tuple[QWidget, Dict[str, Any]]:
    page = QWidget()
    layout = QVBoxLayout(page)

    status_label = QLabel("就绪")
    progress_bar = QProgressBar()
    progress_bar.setRange(0, 100)
    progress_bar.setValue(0)

    layout.addWidget(status_label)
    layout.addWidget(progress_bar)

    from PySide6.QtWidgets import QPlainTextEdit
    log_edit = QPlainTextEdit()
    log_edit.setReadOnly(True)
    log_edit.setMaximumBlockCount(30000)
    layout.addWidget(log_edit, 1)

    refs = {
        "status_label": status_label,
        "progress_bar": progress_bar,
        "log_edit": log_edit,
    }
    return page, refs