import os
import shutil
import time
from copy import deepcopy
import json
import numpy as np
import gen_lightcurve_plot as lightcurve

from .archive_manager import save_archive_from_state
from .config_manager import load_config
from .data_loader import load_csv_source, load_txt_source, extract_date_range
from .exporter import export_docx_report
from .file_manager import manage_sequential_file_naming, parse_target_numbers, scan_numbered_files
from .source_processor import process_source
from .state_manager import ensure_json_suffix, load_or_init_state, save_state


SOURCE_OVERRIDE_GLOBAL_KEYS = {
    "start_date",
    "end_date",
    "remove_upper_limit",
    "remove_max_value_numbers",
}


def deep_merge(base: dict, override: dict) -> dict:
    """
    递归合并字典：
    - override 中有的字段覆盖 base
    - 子字典递归合并
    - 不修改原始 base
    """
    result = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = deepcopy(v)
    return result


def sanitize_source_override(override: dict) -> dict:
    """
    只保留单源覆盖里允许的字段。
    当前只允许 global 下的日期/清洗字段。
    """
    if not isinstance(override, dict):
        return {}

    out = {}
    global_part = override.get("global", {})
    if isinstance(global_part, dict):
        clean_global = {}
        for k in SOURCE_OVERRIDE_GLOBAL_KEYS:
            if k in global_part:
                clean_global[k] = deepcopy(global_part[k])
        if clean_global:
            out["global"] = clean_global

    return out


def sanitize_source_overrides(source_overrides: dict) -> dict:
    if not isinstance(source_overrides, dict):
        return {}
    out = {}
    for k, v in source_overrides.items():
        clean = sanitize_source_override(v)
        if clean:
            out[str(k)] = clean
    return out


def resolve_target_numbers(global_cfg, available_numbers):
    """
    智能解析目标编号：
    1. 优先检查手动勾选列表 (selected_source_numbers)。
    2. 如果勾选列表为空，则回退解析全局范围设置 (file_numbers)。
    """
    available_list = list(available_numbers)
    available_set = {int(x) for x in available_list}

    manual = global_cfg.get("selected_source_numbers", [])

    if isinstance(manual, (list, tuple, set)) and len(manual) > 0:
        out = []
        for x in manual:
            try:
                n = int(x)
                if n in available_set:
                    out.append(n)
            except Exception:
                continue

        if out:
            return sorted(set(out))
        else:
            print("[pipeline] 手动勾选列表中的文件在目录中未找到，将回退到全局范围设置。")

    file_range_setting = global_cfg.get("file_numbers", -1)

    print(f"[pipeline] 正在按全局范围设置解析文件: {file_range_setting}")

    target_nums = parse_target_numbers(
        file_range_setting,
        available_numbers=available_list
    )

    return target_nums


def _persist_state_and_archive(state: dict, running_data_path: str, state_filename: str) -> str:
    """
    先保存 state，再同步到程序根目录 Archive/archive.json
    """
    final_state_file = save_state(state, state_path=running_data_path, filename=state_filename)
    try:
        save_archive_from_state(state, "archive")
    except Exception as e:
        print(f"[pipeline] 同步 archive 失败：{e}")
    return final_state_file


def run_pipeline(config_map: str = "config"):
    """
    主流程入口：
    1. 读配置
    2. 整理文件编号
    3. 加载/初始化 state
    4. 逐个文件处理
    5. 保存 state
    6. 同步 archive（程序根目录/Archive/archive.json）
    7. 导出 docx（可选）
    """
    config = load_config(config_map)
    if not isinstance(config, dict):
        raise ValueError("配置文件内容必须是 JSON 对象。")

    raw_overrides = config.get("source_overrides", {}) or {}
    source_overrides = sanitize_source_overrides(raw_overrides)
    if raw_overrides != source_overrides:
        print("[pipeline] 已清理 source_overrides 中不支持的字段，只保留 global 日期/清洗覆盖。")
    config["source_overrides"] = source_overrides

    global_cfg = config.get("global", {})

    folder_path = global_cfg.get("folder_path")
    output_path = global_cfg.get("output_path")
    state_filename = global_cfg.get("state_filename", "state")
    file_type = global_cfg.get("file_type", "csv")
    mode = global_cfg.get("mode", "customize")
    rerun = global_cfg.get("rerun", False)
    min_points_per_cycle = global_cfg.get("min_points_per_cycle", 10)

    constant_flux_values = global_cfg.get("constant_flux_values", 5.0)
    constant_flux = global_cfg.get("constant_flux", False)

    if not folder_path:
        raise ValueError("config.global.folder_path 不能为空")
    if not output_path:
        raise ValueError("config.global.output_path 不能为空")
    if file_type not in {"csv", "txt"}:
        raise ValueError(f"不支持的 file_type: {file_type}")
    if mode not in {"auto", "customize"}:
        raise ValueError(f"不支持的 mode: {mode}")

    os.makedirs(output_path, exist_ok=True)
    running_data_path = os.path.join(output_path, "Running_Data")
    os.makedirs(running_data_path, exist_ok=True)
    os.makedirs(os.path.join(output_path, "Light_Plot"), exist_ok=True)
    os.makedirs(os.path.join(output_path, "back_up"), exist_ok=True)

    print("*********************开始文件标号*********************")
    manage_sequential_file_naming(file_type=file_type, directory=folder_path, mode="number")

    config_file = ensure_json_suffix(config_map)
    config_name = os.path.splitext(os.path.basename(config_file))[0]
    target_file = os.path.join(running_data_path, os.path.basename(config_file))
    shutil.copy2(config_file, target_file)
    print(f"文件已复制到: {target_file}")

    start_time = time.time()

    state_file = os.path.join(running_data_path, ensure_json_suffix(state_filename))

    if rerun:
        print("rerun为True, 重新开始计算")
        if os.path.exists(state_file):
            base, ext = os.path.splitext(state_file)
            counter = 1

            new_state_file = f"{base}_{counter}{ext}"
            while os.path.exists(new_state_file):
                counter += 1
                new_state_file = f"{base}_{counter}{ext}"

            os.rename(state_file, new_state_file)
            print(f"旧状态文件已重命名为: {new_state_file}，重新开始计算")
        else:
            print("未找到状态文件，直接开始新计算")

    state = load_or_init_state(running_data_path, state_filename)

    if state is None:
        state = {}

    if state.get("processed_files"):
        print("继续从之前计算过的源后开始计算")
    else:
        print("没有找到状态文件，重新开始计算")

    if not os.path.isdir(folder_path):
        raise ValueError(f"目录不存在或无法访问: {folder_path}")

    file_map = scan_numbered_files(folder_path, file_type=file_type)

    print(f"[pipeline] 扫描完成。目录: {folder_path}, 类型: {file_type}, 发现文件数: {len(file_map)}")

    if not file_map:
        print(f"未找到任何匹配的 {file_type} 文件。")

    numbers = global_cfg.get("file_numbers", -1)
    target_numbers = resolve_target_numbers(global_cfg, file_map.keys())

    selected_source_numbers = global_cfg.get("selected_source_numbers", [])
    if isinstance(selected_source_numbers, list) and selected_source_numbers:
        print(f"将优先读取预览页勾选的编号文件: {selected_source_numbers}")
    else:
        if isinstance(numbers, int):
            if numbers < 0:
                print("将读取所有编号文件")
            else:
                print(f"将读取单个编号文件: {numbers}")
        elif isinstance(numbers, list):
            print(f"将读取数字列表文件: {numbers}")
        elif isinstance(numbers, str):
            print(f"将读取指定范围文件: {numbers}")

    if not target_numbers:
        print("没有可处理的目标编号。")

    source_overrides = config.get("source_overrides", {}) or {}

    for num in sorted(target_numbers):
        if num not in file_map:
            print(f"!! 跳过缺失文件编号: {num}")
            continue

        file_path = file_map[num]
        filename = os.path.basename(file_path)
        print(f"读取文件: {filename}")

        effective_config = deepcopy(config)
        override_cfg = source_overrides.get(str(num), {})
        if isinstance(override_cfg, dict) and override_cfg:
            effective_config = deep_merge(effective_config, override_cfg)

        start_date, end_date = extract_date_range(effective_config)

        if file_type == "csv":
            if not filename.endswith(".csv"):
                print(f"文件：{filename}类型错误，跳过")
                continue

            if filename in state.get("processed_files", []):
                print(f"文件：{filename}被处理过，跳过")
                continue

            source_name, julian_dates, photon_fluxes, photon_fluxes_err, remove_upper_limit_mask = load_csv_source(
                file_path,
                state,
                effective_config
            )

            if constant_flux:
                print(f"源{ source_name}-使用固定 flux 值{constant_flux_values}")
                photon_fluxes = np.full(len(julian_dates), constant_flux_values)

            n_min = min_points_per_cycle * 3
            if julian_dates is None or len(julian_dates) == 0 or len(julian_dates) <= n_min:
                print(f"警告：文件 {filename} 中没有有效数据，或只有少数数据点，已跳过！")
                state.setdefault("skipped_sources", {})[filename] = {
                    "source_name": source_name,
                    "reason": f"insufficient_data(<= {n_min})"
                }
                state.setdefault("processed_files", []).append(filename)

                _persist_state_and_archive(state, running_data_path, state_filename)
                continue

            processed_data, stats = lightcurve.get_lightcurve_data(file_path, config_map)
            if config.get("gen_light_plot", False):
                lightcurve.plot_lightcurve(
                    processed_data,
                    stats,
                    os.path.join(output_path, "Light_Plot"),
                    fig_mode="save"
                )

            result = process_source(
                source_name,
                julian_dates,
                photon_fluxes,
                photon_fluxes_err,
                output_path,
                state,
                state_filename,
                effective_config,
                config_name,
                stats=stats
            )
            # result["matched_file"] = filename

            if mode == "customize":
                result["applied_start_date"] = start_date
                result["applied_end_date"] = end_date
                result["constant_flux"] = bool(constant_flux)
                result["constant_flux_values"] =  float(constant_flux_values)

                if source_name not in state.setdefault("valid_sources", []):
                    state["valid_sources"].append(source_name)
                state.setdefault("results", {})[source_name] = result

            state.setdefault("processed_files", []).append(filename)

            _persist_state_and_archive(state, running_data_path, state_filename)

        elif file_type == "txt":
            if not filename.endswith(".txt"):
                print(f"文件：{filename}类型错误，跳过")
                continue

            if filename in state.get("processed_files", []):
                print(f"文件：{filename}被处理过,或者文件类型错误，跳过")
                continue

            source_name, julian_dates, photon_fluxes, photon_fluxes_err = load_txt_source(
                file_path,
                state
            )

            if constant_flux:
                print(f"源{source_name}-使用固定 flux 值{constant_flux_values}")
                photon_fluxes = np.full(len(julian_dates), constant_flux_values)

            if julian_dates is None or len(julian_dates) == 0:
                print(f"警告：文件 {filename} 中没有有效数据，已跳过！")
                state.setdefault("skipped_sources", {})[filename] = {
                    "source_name": source_name,
                    "reason": "insufficient_data"
                }

                state.setdefault("processed_files", []).append(filename)

                _persist_state_and_archive(state, running_data_path, state_filename)
                continue

            stats = None

            result = process_source(
                source_name,
                julian_dates,
                photon_fluxes,
                photon_fluxes_err,
                output_path,
                state,
                state_filename,
                effective_config,
                config_name,
                stats=stats
            )

            if mode == "customize":
                result["applied_start_date"] = start_date
                result["applied_end_date"] = end_date
                result["constant_flux"] = constant_flux
                result["constant_flux_values"] = constant_flux_values

                if source_name not in state.setdefault("valid_sources", []):
                    state["valid_sources"].append(source_name)
                state.setdefault("results", {})[source_name] = result

            state.setdefault("processed_files", []).append(filename)

            _persist_state_and_archive(state, running_data_path, state_filename)

        else:
            print(f"未定义文件类型: {file_type}")
            continue

    end_time = time.time()
    elapsed_time = end_time - start_time

    final_state_file = _persist_state_and_archive(state, running_data_path, state_filename)

    print(f"状态文件已经储存在：{final_state_file}")
    print(
        f"*************************全部源已经计算完毕,程序运行时间：{round(elapsed_time, 3)} 秒*************************"
    )

    # 默认值（如果动态读取失败则使用启动时的值）
    export_docx = global_cfg.get("export_docx", True)
    output_filename = global_cfg.get("docx_name", "report_docx") + ".docx"

    try:
        # 强制定位当前正在使用的配置文件路径
        dynamic_config_path = ensure_json_suffix(config_map)

        if os.path.exists(dynamic_config_path):
            with open(dynamic_config_path, 'r', encoding='utf-8') as f:
                latest_data = json.load(f)
                latest_global = latest_data.get("global", {})

                # 1. 动态获取是否导出的开关
                raw_export_val = latest_global.get("export_docx", True)
                if isinstance(raw_export_val, str):
                    export_docx = raw_export_val.strip().lower() in {"1", "true", "yes", "on"}
                else:
                    export_docx = bool(raw_export_val)

                # 2. 动态获取报告名称
                latest_docx_name = latest_global.get("docx_name", "report_docx")
                output_filename = str(latest_docx_name).strip() + ".docx"

                print(f"[pipeline] 运行结束前检测到最新配置：export_docx={export_docx}, name={output_filename}")
    except Exception as e:
        print(f"[pipeline] 动态读取最新配置失败: {e}，将维持原计划。")

    # =========================================================
    # 执行导出
    # =========================================================
    if export_docx:
        print(f"[pipeline] 正在生成 Word 报告: {output_filename}")
        export_docx_report(
            data_path=output_path,
            state_dict_filename=state_filename,
            json_params_filename=config_name,
            docx_output_path=output_path,
            output_filename=output_filename,
        )
    else:
        print("[pipeline] 检测到 export_docx 为 False，跳过生成 Word 报告。")

    return state