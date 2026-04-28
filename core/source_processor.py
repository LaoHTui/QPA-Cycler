import os
import numpy as np

# import auto_filter_methods as afm
from methods import dcf, lsp, jurkevich as jv, wwz

from .state_manager import backup_state, save_state


def _create_output_dirs(output_file: str, mode: str):
    """
    根据模式创建输出目录
    """
    output_dirs = (
        ["DCF", "Jurkevich", "LSP", "WWZ", "Light_Plot", "Running_Data", "back_up"]
        if mode == "customize"
        else ["Light_Plot", "Running_Data", "back_up"]
    )

    for d in output_dirs:
        os.makedirs(os.path.join(output_file, d), exist_ok=True)

    return os.path.join(output_file, "Running_Data")


def _run_beta_for_source(
        source_name,
        series,
        flux,
        flux_err,
        output_file,
        config,
        state,
        state_filename,
        source_result,
        periodogram_mode
):
    custom_cfg = config.get("customize", {})
    beta_params = custom_cfg.get("beta_params", {})
    beta_best, beta_err = lsp.get_psd_slope(
        series,
        flux,
        flux_err,
        source_name,
        method=beta_params.get("method", "psresp"),
        beta_range=np.arange(beta_params.get("beta_start", 0.1),
                             beta_params.get("beta_end", 1.5),
                             beta_params.get("beta_step", 0.1)),
        M=beta_params.get("M", 1000),
        n_jobs=beta_params.get("n_jobs", -1),
        plot=beta_params.get("plot", True),
        n_bins=beta_params.get("n_bins", 10),
        save_path=os.path.join(output_file, "LSP"),
        plot_mode=beta_params.get("plot_mode", "save"),
        periodogram_mode=periodogram_mode
    )
    print(f"拟合得到的最佳 beta: {beta_best:.2f} ± {beta_err:.2f}")

    source_result["Beta"] = {
        "beta_best": float(beta_best),
        "beta_err": float(beta_err),
    }

    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)
    return beta_best, beta_err


def _run_lsp_for_source(
        source_name,
        series,
        flux,
        flux_err,
        stats,
        beta,
        output_file,
        config,
        state,
        state_filename,
        source_result,
        periodogram_mode
):
    """
    执行 LSP
    """
    custom_cfg = config.get("customize", {})
    lsp_params = custom_cfg.get("lsp_params", {})

    print(f"*********************{source_name}开始LSP*********************")

    freq, lsp_power, _ = lsp.lsp_Method(
        series,
        flux,
        flux_err,
        divide_freq_step=lsp_params.get("divide_freq_step", 10),
        periodogram_mode=periodogram_mode
    )

    if lsp_params.get("MC", True):

        sig = lsp.calculate_Lsp_FAP(
            series,
            flux,
            flux_err,
            beta_best=beta,
            frequency=freq,
            M=lsp_params.get("M", 10000),
            n_jobs=lsp_params.get("n_jobs", -1),
            periodogram_mode=periodogram_mode
        )
    else:
        sig = None

    min_period = 0
    if isinstance(stats, dict):
        min_period = stats.get("P_min", 0)

    lsp_periods = lsp.get_LSP_periods(
        freq,
        lsp_power,
        sig,
        sig_threshold=lsp_params.get("sig_threshold", 0.997),
        top_n=lsp_params.get("top_n", 3),
        min_period=min_period
    )

    if not lsp_periods:
        print("没有发现超过设定置信度的周期信号。")
    else:
        for s in lsp_periods:
            print(
                f"检测到信号！ 峰值高斯拟合后周期: {s['period']:.2f} ± {s['period_err']:.2f}天, "
                f"置信度: {s['significance'] * 100:.2f}%, 即 {s['sigma']}σ"
            )

    state.setdefault("lsp_expected_period", []).append(lsp_periods)

    source_result["LSP"] = {
        "periods": lsp_periods,
        "periodogram_mode": periodogram_mode
    }

    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)
    plot_params = lsp_params.get("plot_params", {})
    if custom_cfg.get("LSP_Plot", False):
        lsp.plot_LSP(
            source_name,
            freq,
            lsp_power,
            sig,
            lsp_periods,
            series,
            flux,
            flux_err,
            plot_mode=plot_params.get("plot_mode", "save"),
            save_path=os.path.join(output_file, "LSP"),
            time_axis_mode=plot_params.get("time_axis_mode", "ym"),
            time_input_format=plot_params.get("time_input_format", "jd"),
            periodogram_mode=periodogram_mode
        )
    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)


def _run_jurkevich_for_source(
        source_name,
        series,
        flux,
        stats,
        output_file,
        config,
        state,
        state_filename,
        source_result
):
    """
    执行 Jurkevich
    """
    custom_cfg = config.get("customize", {})
    jv_params = custom_cfg.get("jv_params", {})

    print(f"*********************{source_name}开始Jurkevich*********************")

    jv_test_periods = np.arange(
        jv_params.get("test_periods_start", 100),
        jv_params.get("test_periods_end", 3000),
        jv_params.get("test_periods_step", 10)
    )

    v2 = jv.jurkevich_Method(
        series,
        flux,
        jv_test_periods,
        m=jv_params.get("m_bins", 2)
    )

    min_period = 0
    if isinstance(stats, dict):
        min_period = stats.get("P_min", 0)

    best_p, p_err, bounds = jv.get_period(jv_test_periods, v2, min_period=min_period)

    state.setdefault("jv_expected_period", []).append(best_p)

    source_result["Jurkevich"] = {
        "period": best_p,
        "period_err": p_err,
        "boundary_list": bounds
    }

    if custom_cfg.get("JV_Plot", False):
        print(
            f"Jurkevich方法得到周期：{best_p}+-{p_err}"
        )
        jv.plot_Vm2(
            source_name,
            jv_test_periods,
            v2,
            best_p,
            p_err,
            bounds,
            plot_mode=jv_params.get("plot_mode", "save"),
            save_path=os.path.join(output_file, "Jurkevich")
        )

    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)


def _run_dcf_for_source(
        source_name,
        series,
        flux,
        stats,
        output_file,
        config,
        state,
        state_filename,
        source_result
):
    """
    执行 DCF
    """
    custom_cfg = config.get("customize", {})
    dcf_params = custom_cfg.get("dcf_params", {})

    print(f"*********************{source_name}开始DCF*********************")

    tau, dcf_value, err = dcf.dcf_Method(
        series,
        flux,
        delta_tau=dcf_params.get("delta_tau", 3),
        c=dcf_params.get("c", 8),
        max_tau=dcf_params.get("max_tau", 2000),
    )
    min_period = 0
    if isinstance(stats, dict):
        min_period = stats.get("P_min", 0)

    dcf_period = dcf.get_dcf_periods(
        tau, dcf_value, err,
        min_period=min_period,
        distance_days=dcf_params.get("distance", 5),
    )

    state.setdefault("dcf_possible_period", []).append(dcf_period)
    print(f"DCF period: {dcf_period}")

    source_result["DCF"] = {
        "period": dcf_period
    }

    if custom_cfg.get("DCF_Plot", False):
        dcf.plot_DCF(
            tau,
            dcf_value,
            err,
            dcf_period,
            source_name,
            dcf_params.get("c", 8),
            save_path=os.path.join(output_file, "DCF"),
            plot_mode=dcf_params.get("plot_mode", "save")
        )

    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)


def _run_wwz_for_source(
        source_name,
        series,
        flux,
        flux_err,
        beta,
        stats,
        output_file,
        config,
        state,
        state_filename,
        source_result
):
    """
    执行 WWZ
    """
    custom_cfg = config.get("customize", {})
    wwz_params = custom_cfg.get("wwz_params", {})

    print(f"*********************{source_name}开始WWZ*********************")

    p_start = wwz_params.get("p_start", 100)
    freq_end = 1 / p_start
    p_end = wwz_params.get("p_end", 3000)
    freq_start = 1 / p_end
    step = wwz_params.get("divide_freq_step", 10)
    frequency_parameter_list = [freq_start, freq_end, freq_start / step]

    c_wwz = wwz_params.get("c", 0.0125)
    z_height = wwz_params.get("z_height", 20000)
    tau_number = wwz_params.get("tau_number", 1000)

    wwz_taus, wwz_freqs, wwz_Z, wwz_COI, wwz_P_max, wwz_A, wwz_N_eff = wwz.wwz_Method(
        series,
        flux,
        tau_number,
        frequency_parameter_list,
        c=c_wwz,
        z_height=z_height
    )

    # 这里原代码固定为 False，保留原逻辑
    MC = wwz_params.get("MC", False)
    if MC:
        sig, g_sig = wwz.get_wwz_significance_mc(
            series,
            flux,
            flux_err,
            beta,
            tau_number,
            frequency_parameter_list,
            c_wwz,
            M=wwz_params.get("M", 10000),
            n_jobs=wwz_params.get("n_jobs", -1)
        )
    else:
        sig, g_sig = None, None

    min_period = 0
    if isinstance(stats, dict):
        min_period = stats.get("P_min", 0)
    wwz_result = wwz.get_wwz_peaks(
        wwz_taus,
        wwz_freqs,
        wwz_Z,
        c_wwz,
        sig,
        sig_threshold=wwz_params.get("sig_threshold", 5),
        top_n=wwz_params.get("top_n", 3),
        min_period=min_period
    )

    state.setdefault("wwz_possibly_period", []).append(wwz_result)

    source_result["WWZ"] = {
        "result": wwz_result
    }

    plot_params = wwz_params.get("plot_params", {})

    if custom_cfg.get("WWZ_Plot", False):
        wwz.plot_wwz(
            wwz_taus,
            wwz_freqs,
            wwz_Z,
            wwz_COI,
            source_name,
            wwz_P_max,
            sig,
            g_sig,
            wwz_result,
            c_wwz,
            t0_abs=series[0],
            plot_mode=plot_params.get("plot_mode", "save"),
            time_scale=plot_params.get("time_scale", "JD"),
            save_path=os.path.join(output_file, "WWZ"),
            peak_prominence=plot_params.get("peak_prominence", 3),
            use_log_scale_period=plot_params.get("use_log_scale_period", True),
        )
    save_state(state, state_path=os.path.join(output_file, "Running_Data"), filename=state_filename)


def process_source(
        source_name,
        series,
        flux,
        flux_err,
        output_file,
        state,
        state_filename,
        config,
        config_map,
        stats=None
):
    """
    通用数据处理函数，用于执行各种分析方法并保存结果。
    """
    mode = config.get("global", {}).get("mode", "customize")

    # 创建输出目录
    running_data_path = _create_output_dirs(output_file, mode)

    # 单个源的完整结果字典
    source_result = {
        "source_name": source_name,
        "status": "processing",
        "stats": stats,
        "LSP": None,
        "Jurkevich": None,
        "DCF": None,
        "WWZ": None,
        "Beta": None
    }

    # 先放进 state，便于中途崩溃时留下部分结果
    state.setdefault("results", {})[source_name] = source_result

    if mode == "customize":
        custom_cfg = config.get("customize", {})
        beta_param = custom_cfg.get("beta_params", {})
        lsp_params = custom_cfg.get("lsp_params", {})
        periodogram_mode = lsp_params.get("lsp_mode", "lsp")

        if beta_param.get("beta_calculate", True):
            beta, beta_err = _run_beta_for_source(
                source_name,
                series,
                flux,
                flux_err,
                output_file,
                config,
                state,
                state_filename,
                source_result,
                periodogram_mode
            )
        else:
            beta = beta_param.get("default_beta", 0.9)

        # LSP
        if custom_cfg.get("LSP", False):
            _run_lsp_for_source(
                source_name,
                series,
                flux,
                flux_err,
                stats,
                beta,
                output_file,
                config,
                state,
                state_filename,
                source_result,
                periodogram_mode
            )
        else:
            state.setdefault("lsp_expected_period", []).append(np.nan)
            source_result["LSP"] = None

        # Jurkevich
        if custom_cfg.get("Jurkevich", False):
            _run_jurkevich_for_source(
                source_name,
                series,
                flux,
                stats,
                output_file,
                config,
                state,
                state_filename,
                source_result
            )
        else:
            state.setdefault("jv_expected_period", []).append(np.nan)
            source_result["Jurkevich"] = None

        # DCF
        if custom_cfg.get("DCF", False):
            _run_dcf_for_source(
                source_name,
                series,
                flux,
                stats,
                output_file,
                config,
                state,
                state_filename,
                source_result
            )
        else:
            state.setdefault("dcf_possible_period", []).append(np.nan)
            source_result["DCF"] = None

        # WWZ
        if custom_cfg.get("WWZ", False):
            _run_wwz_for_source(
                source_name,
                series,
                flux,
                flux_err,
                beta,
                stats,
                output_file,
                config,
                state,
                state_filename,
                source_result
            )
        else:
            state.setdefault("wwz_possibly_period", []).append(np.nan)
            source_result["WWZ"] = None

        source_result["status"] = "done"

    elif mode == "auto":
        # flag, afm_dict = afm.auto_filter_method(source_name, series, flux, flux_err, config_map, output_file)
        # state.setdefault("afm_dict", []).append(afm_dict)
        # source_result["AFM"] = afm_dict
        # source_result["status"] = "done"
        raise ValueError("auto方法测试中，无法运行")
    else:
        raise ValueError(f"不存在该模式: {mode}")

    # 最后统一保存一次
    save_state(state, state_path=running_data_path, filename=state_filename)

    # 备份 state
    backup_path = os.path.join(output_file, "back_up")
    backup_state(state, backup_path)

    # if mode == "auto":
    #     return afm_dict

    return source_result
