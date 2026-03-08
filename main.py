import glob
import os
import json
import re
import shutil
import time
import numpy as np
from datetime import datetime

from File_operations import get_csv_data as gcd, get_txt_data as gtd
import gen_final_table as gen_table
import gen_lightcurve_plot as lightcurve
import jurkevich as jv
import lsp
import dcf
import wwz
import auto_filter_methods as afm

os.environ['PYTHONIOENCODING'] = 'UTF-8' # 确保路径合法


def save_state(state, state_path, filename='state.json'):
    """
    保存程序状态到指定文件。

    参数:
    - state: 要保存的程序状态，通常为一个字典。
    - filename: 保存状态的文件名，默认为'state.json'。

    该函数将程序状态转换为JSON格式并保存到指定的文件中。
    """
    with open(os.path.join(state_path, f'{filename}.json'), 'w') as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def load_state(state_path, filename='state.json'):
    """
    从指定文件加载程序状态。

    参数:
    - filename: 要加载状态的文件名，默认为'state.json'。

    返回:
    - 如果文件存在且包含有效的JSON数据，则返回加载的程序状态。
    - 如果文件不存在或为空，则返回None。
    """
    file_path = os.path.join(state_path, f'{filename}.json')
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    else:
        return None

def process_data(source_name, series, flux, flux_err, output_file, state, state_filename, config_map):
    """通用数据处理函数，用于执行各种分析方法并保存结果"""



    with open(f'{config_map}.json') as f:
        config = json.load(f)
    mode = config['global']['mode']

    # 创建输出目录
    output_dirs = ['DCF', 'Jurkevich', 'LSP', 'WWZ', 'Light_Plot', 'Running_Data', 'back_up'] if mode == 'customize' else ['Light_Plot', 'Running_Data', 'back_up']
    for d in output_dirs:
        os.makedirs(os.path.join(output_file, d), exist_ok=True)

    # 生成光变曲线图
    if config['gen_light_plot']:
        lightcurve.gen_lightcurve_plot(
            source_name,
            series,
            flux,
            os.path.join(output_file, 'Light_Plot')
        )

    running_data_path = os.path.join(output_file, 'Running_Data')
    if mode == 'customize':
        # LSP方法
        if config['customize']['LSP']:
            print(f'*********************{source_name}开始LSP*********************')
            frequency, power = lsp.lsp_Method(series, flux, flux_err,
                                              multiple_freq_max=config['customize']['lsp_params']['multiple_freq_max'],
                                              divide_freq_step=config['customize']['lsp_params']['divide_freq_step'])
            sigmas, _ = lsp.calculate_Lsp_FAP(series, flux, frequency, M=config['customize']['lsp_params']['M'],
                                              n_jobs=config['customize']['lsp_params']['n_jobs'])
            lsp_period = lsp.analysis_LSP_Periods(frequency, power, *sigmas)
            print(f'LSP period: {lsp_period}')
            state.setdefault('lsp_expected_period', []).append(lsp_period)
            if config['customize']['LSP_Plot']:
                lsp.gen_Lsp_plot(source_name, frequency, power, *sigmas, os.path.join(output_file, 'LSP'))
            # 保存状态
            save_state(state, state_path=running_data_path, filename=state_filename)
        else:
            lsp_period = np.nan
            state.setdefault('lsp_expected_period', []).append(lsp_period)
        # Jurkevich方法
        if config['customize']['Jurkevich']:
            print(f'*********************{source_name}开始Jurkevich*********************')
            jv_test_periods = np.arange(config['customize']['jv_params']['test_periods_start'],
                                        config['customize']['jv_params']['test_periods_end'],
                                        config['customize']['jv_params']['test_periods_step'])
            v2, _ = jv.jurkevich_Method(series, flux, jv_test_periods, m=config['customize']['jv_params']['m_bins'])
            jv_period = jv.analysis_Jurkevich_Periods(v2, jv_test_periods)
            print(f'Jurkevich period: {jv_period}')
            state.setdefault('jv_expected_period', []).append(jv_period)
            if config['customize']['JV_Plot']:
                jv.plot_Vm2(source_name, jv_test_periods, v2, os.path.join(output_file, 'Jurkevich'))
            # 保存状态
            save_state(state, state_path=running_data_path, filename=state_filename)
        else:
            jv_period = np.nan
            state.setdefault('jv_expected_period', []).append(jv_period)
        # DCF方法
        if config['customize']['DCF']:
            print(f'*********************{source_name}开始DCF*********************')
            dcf_result, err, tau = dcf.dcf_Method(series, flux,
                                                  delta_tau=config['customize']['dcf_params']['delta_tau'],
                                                  c=config['customize']['dcf_params']['c'],
                                                  max_tau=config['customize']['dcf_params']['max_tau'],
                                                  normalize=config['customize']['dcf_params']['normalize'])
            dcf_period = dcf.analysis_DCF_Periods(dcf_result, tau,
                                                  distance=config['customize']['dcf_params']['distance'],
                                                  height=config['customize']['dcf_params']['height'])
            state.setdefault('dcf_possible_period', []).append(dcf_period)
            print(f'DCF period: {dcf_period}')
            if config['customize']['DCF_Plot']:
                dcf.plot_DCF(tau, dcf_result, err, config['customize']['dcf_params']['delta_tau'], [],
                             [], [], source_name, save_path=output_file, plot_mode="save")

            # 保存状态
            save_state(state, state_path=running_data_path, filename=state_filename)
        else:
            dcf_period = np.nan
            state.setdefault('dcf_possible_period', []).append(dcf_period)

        # WWZ方法
        if config['customize']['WWZ']:
            print(f'*********************{source_name}开始WWZ*********************')
            tau_wwz, f_wwz, Z_wwz, COI_wwz, *_ = wwz.wwz_Method(series, flux,
                                                                config['customize']['wwz_params']['tau_number'],
                                                                [config['customize']['wwz_params']['freq_min'],
                                                                 config['customize']['wwz_params']['freq_max'],
                                                                 config['customize']['wwz_params']['freq_step']],
                                                                c=config['customize']['wwz_params']['c'],
                                                                z_height=config['customize']['wwz_params']['z_height'])
            wwz_period = wwz.analysis_WWZ_Periods(f_wwz, Z_wwz)
            print(f'WWZ period: {wwz_period}')
            state.setdefault('wwz_possibly_period', []).append(wwz_period)
            if config['customize']['WWZ_Plot']:
                wwz.gen_wwz_plot(tau_wwz, f_wwz, Z_wwz, COI_wwz, source_name, os.path.join(output_file, 'WWZ'))
        else:
            wwz_period = np.nan
            state.setdefault('wwz_possibly_period', []).append(wwz_period)
    if mode == 'auto':
        flag,afm_dict = afm.auto_filter_method(source_name, series, flux, flux_err, config_map, output_file)
        state.setdefault('afm_dict', []).append(afm_dict)
    else:
        print("不存在该模式")

    save_state(state, state_path = running_data_path, filename = state_filename)

    backup_path = os.path.join(output_file, 'back_up')
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    with open(os.path.join(backup_path, f'state_{timestamp}.json'), 'w') as f1:
        json.dump(state, f1)
    if mode == 'auto':
        return afm_dict  # 保存状态并备份
    if mode == 'customize':
        return


def main(config_map):
    """
    主函数，用于处理指定文件夹中的CSV/TXT文件，分析光变曲线并生成结果。
    :param config_map: 配置文件，用于加载配置参数。
    """
    # 打开参数文件并读取参数
    global target_numbers
    with open(f'{config_map}.json') as f:
        config = json.load(f)

    folder_path = config["global"]["folder_path"]
    output_path = config["global"]["output_path"]
    state_filename = config["global"]["state_filename"]
    file_type = config["global"]["file_type"]
    os.makedirs(output_path, exist_ok=True)
    running_data_path = os.path.join(output_path, 'Running_Data')
    os.makedirs(running_data_path, exist_ok=True)

    # 构建目标文件路径
    target_file = os.path.join(running_data_path, os.path.basename(f'{config_map}.json'))

    # 复制文件
    shutil.copy2(f'{config_map}.json', target_file)
    print(f"文件已复制到: {target_file}")

    gen_result_table =  config['gen_result_table']['plot']
    rerun = config['global']['rerun']

    # 开始记录程序运行时间
    start_time = time.time()

    # 生成最终结果表格图 如果为True,直接生成后结束运行 旧
    if gen_result_table:
        print('*********************开始生成最终结果表格（旧方法 不推荐）*********************')
        # 读取并打印保存的程序状态，用于调试和验证
        with open(f'{running_data_path}\\{state_filename}.json', 'r', encoding='utf-8') as file:
            data = json.load(file)

        source_name_list = []
        # 从保存的状态中提取数据，用于生成最终的统计表
        saved_source_name_list = data['processed_files']
        for f in saved_source_name_list:
            # 分离名字，美观输出
            source_name_list.append(f.split("_")[0] + "_" + f.split("_")[1])
        # 得到每个保存在state里的数据
        saved_jv_expected_period = data['jv_expected_period']
        saved_dcf_possible_period = data['dcf_possible_period']
        saved_lsp_expected_period = data['lsp_expected_period']
        saved_wwz_possibly_period = data['wwz_possibly_period']
        # 生成最终的统计表
        gen_table.gen_final_statistics_table(output_path, source_name_list, saved_jv_expected_period,
                                             saved_dcf_possible_period, saved_lsp_expected_period,
                                             saved_wwz_possibly_period, config['gen_result_table']['quantity'])
        return None


    if rerun:
        print("rerun为True,重新开始计算")
        # 删除上次运行的state文件，如果需要可以备份state,生成最终结果表格图的优先级在他之上
        if os.path.exists(f'{running_data_path}\\{state_filename}.json'):
            os.remove(f'{running_data_path}\\{state_filename}.json')
            print(f"{running_data_path}\\{state_filename}.json状态文件已删除，重新开始计算")
        else:
            print("未找到状态文件")


    # 加载之前保存的程序状态
    state = load_state(state_path = running_data_path, filename=state_filename)
    if state is None:
        # 如果没有找到状态文件，则从头开始计算
        print("没有找到状态文件，重新开始计算")
        state = {'processed_files': []}
    else:
        # 如果找到了状态文件，则从之前的状态继续计算（在没有rerun的基础上）
        print("继续从之前计算过的源后开始计算")
    # -------------------------------------------------开始数据分析-----------------------------------------------------------
    # 遍历输入文件夹中的所有文件
    if not os.path.isdir(folder_path):
        raise ValueError(f"目录不存在或无法访问: {folder_path}")

    # 获取所有匹配文件
    pattern = os.path.join(folder_path, f'*.{file_type}')
    files = glob.glob(pattern)

    # 创建编号到文件路径的映射
    file_map = {}
    for file_path in files:
        file_name = os.path.basename(file_path)
        # 支持更灵活的文件名格式（开头是数字，后跟任意字符）
        match = re.match(r'^(\d+)', file_name)
        if match:
            num = int(match.group(1))
            file_map[num] = file_path

    # 确定要读取的编号集合
    numbers = config['global']['file_numbers']
    if type(numbers) == int:
        if numbers < 0:
            # 读取所有编号文件
            print("将读取所有编号文件")
            target_numbers = set(file_map.keys())
    elif isinstance(numbers, int):
        # 单个数字
        print(f"将读取单个编号文件: {numbers}")
        target_numbers = {numbers}
    elif isinstance(numbers, list):
        # 数字列表
        print(f"将读取数字列表文件: {numbers}")
        target_numbers = set(numbers)
    elif isinstance(numbers, str):
        # 处理字符串格式
        print(f"将读取指定范围文件: {numbers}")
        if '-' in numbers:
            # 范围格式 "3-50"
            start_end = numbers.split('-')
            if len(start_end) == 2:
                try:
                    start = int(start_end[0].strip())
                    end = int(start_end[1].strip())
                    target_numbers = set(range(start, end + 1))
                except ValueError:
                    target_numbers = set()
        elif ',' in numbers:
            # 逗号分隔格式 "1,3,7"
            try:
                target_numbers = set(int(n.strip()) for n in numbers.split(','))
            except ValueError:
                target_numbers = set()
        else:
            # 单个数字字符串 "5"
            try:
                target_numbers = {int(numbers.strip())}
            except ValueError:
                target_numbers = set()
    else:
        target_numbers = set()
    mode = config['global']['mode']
    # 读取目标文件内容
    j = 1
    for num in sorted(target_numbers):
        # 按顺序处理
        if num in file_map:
            try:
                filename = os.path.basename(file_map[num])
                print(f"读取文件: {filename}")
                if file_type == 'csv':
                    if filename.endswith('.csv') and filename not in state['processed_files']:
                        # 只处理CSV文件，并且该文件未被处理过（跳过那些在state文件中的源）
                        source_name, julian_dates, photon_fluxes, photon_fluxes_err = gcd.get_csv_data(file_map[num], state)
                        if mode == 'auto':
                            afm_dict = process_data(source_name, julian_dates, photon_fluxes, photon_fluxes_err, output_path, state, state_filename,
                                     config_map)
                        elif mode == 'customize':
                            process_data(source_name, julian_dates, photon_fluxes, photon_fluxes_err,
                                         output_path, state, state_filename,
                                         config_map)
                        else:
                            print(f"未定义模式:{mode}")
                    elif filename.endswith('.csv') and filename in state['processed_files']:
                        print(f"文件：{filename}被处理过，跳过")
                    else:
                        print(f"文件：{filename}类型错误，跳过")
                if file_type == 'txt':

                    if filename.endswith('.txt') and filename not in state['processed_files']:
                        source_name, julian_dates, photon_fluxes, photon_fluxes_err = gtd.get_txt_data(file_map[num], state)
                        if mode == 'auto':
                            afm_dict = process_data(source_name, julian_dates, photon_fluxes, photon_fluxes_err,
                                                    output_path, state, state_filename,
                                                    config_map)
                        elif mode == 'customize':
                            process_data(source_name, julian_dates, photon_fluxes, photon_fluxes_err,
                                         output_path, state, state_filename,
                                         config_map)
                        else:
                            print(f"未定义模式:{mode}")
                    else:
                        print(f"文件：{filename}被处理过,或者文件类型错误，跳过")
                else:
                    continue
                # 处理不支持的文件类型
                    # raise ValueError(f"不支持的文件类型: {file_type}")

            except Exception as e:
                # 捕获具体错误信息
                error_type = type(e).__name__
                print(f"!! 出现错误 [{num}]: {error_type} - {str(e)}")
        else:
            print(f"!! 跳过缺失文件编号: {num}")

    # 所有文件处理完毕后，输出结果
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(f'状态文件已经储存在：{running_data_path}\\{state_filename}')
    print(f"*************************全部源已经计算完毕,程序运行时间：{round(elapsed_time,3)} 秒*************************")

    # save_state(state_path=running_data_path, filename="candidates", state=candidate_dicts)
    return


if __name__ == '__main__':
    config_map = 'config'
    main(config_map=config_map)

