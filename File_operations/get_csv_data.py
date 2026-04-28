import heapq
import os
import warnings
from astropy.time import Time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sympy.printing.pretty.pretty_symbology import line_width


def remove_largest_n_heap_mask(numbers, n):
    """使用堆方法，返回一个布尔掩码指示哪些元素应该被保留"""
    if n <= 0:
        return [True] * len(numbers)  # 所有元素都保留

    # 找到最大的n个数字
    largest_n = heapq.nlargest(n, numbers)

    # 统计最大n个数字的出现次数
    count_dict = {}
    for num in largest_n:
        count_dict[num] = count_dict.get(num, 0) + 1

    # 创建掩码列表，初始化为True（保留所有元素）
    mask = [True] * len(numbers)

    # 遍历列表，标记要移除的元素为False
    for i, num in enumerate(numbers):
        if num in count_dict and count_dict[num] > 0:
            mask[i] = False  # 标记为要移除
            count_dict[num] -= 1

    return mask


def create_time_mask(jd_data, start_date=None, end_date=None, custom_indices=None, include_start=True,
                     include_end=True):
    """
    创建 Julian Date 时间数据的掩码

    参数:
    jd_data: array-like, Julian Date 数据数组
    start_date: tuple, 起始日期 (年, 月, 日)
    end_date: tuple, 结束日期 (年, 月, 日)
    custom_indices: array-like, 自定义索引列表
    include_start: bool, 是否包含起始日期
    include_end: bool, 是否包含结束日期

    返回:
    mask: numpy数组, 布尔掩码
    """

    # 确保输入数据为numpy数组
    jd_array = np.asarray(jd_data)
    mask = np.zeros_like(jd_array, dtype=bool)

    # 情况1: 使用自定义索引
    if custom_indices is not None:
        custom_indices = np.asarray(custom_indices)
        # 确保索引在有效范围内
        valid_indices = custom_indices[(custom_indices >= 0) & (custom_indices < len(jd_array))]
        if len(valid_indices) < len(custom_indices):
            warnings.warn("部分自定义索引超出数据范围，已自动过滤")
        mask[valid_indices] = True
        return mask

    # 情况2: 使用时间范围
    if start_date is None or end_date is None:
        raise ValueError("必须提供起始日期和结束日期，或自定义索引")

    # 将日期转换为 Julian Date
    try:
        start_jd = Time(f"{start_date[0]}-{start_date[1]:02d}-{start_date[2]:02d}").jd
        end_jd = Time(f"{end_date[0]}-{end_date[1]:02d}-{end_date[2]:02d}").jd
    except Exception as e:
        raise ValueError(f"日期格式错误: {e}")

    # 根据包含选项创建比较条件
    if include_start and include_end:
        time_mask = (jd_array >= start_jd) & (jd_array <= end_jd)
    elif include_start and not include_end:
        time_mask = (jd_array >= start_jd) & (jd_array < end_jd)
    elif not include_start and include_end:
        time_mask = (jd_array > start_jd) & (jd_array <= end_jd)
    else:
        time_mask = (jd_array > start_jd) & (jd_array < end_jd)

    return time_mask


def get_csv_data(file_path, state=None, remove_upper_limit=True, start_date=None, end_date=None,
                 custom_indices=None, include_start=True, include_end=True, remove_max_value_numbers=0):
    """
    从CSV文件读取天文数据并进行处理

    参数:
    file_path: CSV文件路径
    state: 用于存储源名称的字典
    remove_upper_limit: 是否移除上限值（标记为'<'的值）
    start_date, end_date: 时间范围筛选
    custom_indices: 自定义索引筛选
    include_start, include_end: 是否包含边界日期
    remove_max_value_numbers: 移除最大的n个通量值

    返回:
    source_name: 源名称
    julian_dates: 处理后的儒略日
    photon_fluxes: 处理后的光子通量
    photon_fluxes_err: 处理后的通量误差
    """

    # 读取CSV文件
    try:
        df = pd.read_csv(file_path, header=0, na_values='-')
    except pd.errors.EmptyDataError:
        df = pd.DataFrame()
        print(f"文件 {file_path} 为空，已跳过！")
        return None, None, None, None, None

    # 初始化上限标记数组
    remove_upper_limit_mask = np.full(len(df), False)

    # 处理包含'<'的上限值
    if len(df) > 0 and df.iloc[:, 4].dtype == 'object':
        upper_limit_condition = df.iloc[:, 4].str.contains('<', na=False)
        remove_upper_limit_mask[upper_limit_condition] = True
        df.iloc[:, 4] = df.iloc[:, 4].str.replace('<', '').astype(float)

    # 从csv中提取数据列
    julian_dates_o = df.iloc[:, 1].values if len(df) > 0 else np.array([])
    photon_fluxes_o = df.iloc[:, 4].values.astype(float) if len(df) > 0 else np.array([])
    photon_fluxes_err = df.iloc[:, 5].values.astype(float) if len(df) > 0 else np.array([])

    # 如果没有数据，返回空值
    if len(julian_dates_o) == 0:
        return None, None, None, None, None

    # 创建掩码：确保数据点和err都有有效值
    normal_data_mask = ~remove_upper_limit_mask
    upper_limit_data_mask = remove_upper_limit_mask

    # 正常数据需要数据值和err都有效
    valid_normal_mask = ~np.isnan(julian_dates_o) & ~np.isnan(photon_fluxes_o) & ~np.isnan(photon_fluxes_err)
    valid_normal_mask = valid_normal_mask & normal_data_mask

    # 上限数据只需要数据值有效
    valid_upper_mask = ~np.isnan(julian_dates_o) & ~np.isnan(photon_fluxes_o)
    valid_upper_mask = valid_upper_mask & upper_limit_data_mask

    # 合并掩码
    mask = valid_normal_mask | valid_upper_mask

    # 应用掩码
    julian_dates = julian_dates_o[mask]
    photon_fluxes = photon_fluxes_o[mask]
    photon_fluxes_err = photon_fluxes_err[mask]
    remove_upper_limit_mask = remove_upper_limit_mask[mask]  # 修正：应该是remove_upper_limit_mask而不是~

    # 移除上限值
    if remove_upper_limit:
        keep_mask = ~remove_upper_limit_mask
        julian_dates = julian_dates[keep_mask]
        photon_fluxes = photon_fluxes[keep_mask]
        photon_fluxes_err = photon_fluxes_err[keep_mask]
        remove_upper_limit_mask = remove_upper_limit_mask[keep_mask]  # 更新上限掩码

    # 提取源名称
    filename = os.path.basename(file_path)
    source_name = filename.split("_")[0] + "_" + filename.split("_")[1] + "_" + filename.split("_")[2]

    # 应用时间范围筛选
    if start_date is not None and end_date is not None:
        time_mask = create_time_mask(julian_dates, start_date, end_date, None, include_start, include_end)
        julian_dates = julian_dates[time_mask]
        photon_fluxes = photon_fluxes[time_mask]
        photon_fluxes_err = photon_fluxes_err[time_mask]
        remove_upper_limit_mask = remove_upper_limit_mask[time_mask]

    # 应用自定义索引筛选
    if custom_indices is not None:
        custom_mask = create_time_mask(julian_dates, None, None, custom_indices, include_start, include_end)
        julian_dates = julian_dates[custom_mask]
        photon_fluxes = photon_fluxes[custom_mask]
        photon_fluxes_err = photon_fluxes_err[custom_mask]
        remove_upper_limit_mask = remove_upper_limit_mask[custom_mask]

    # 移除最大的n个通量值
    if remove_max_value_numbers > 0 and len(photon_fluxes) > 0:
        remove_max_mask = remove_largest_n_heap_mask(photon_fluxes, remove_max_value_numbers)
        julian_dates = julian_dates[remove_max_mask]
        photon_fluxes = photon_fluxes[remove_max_mask]
        photon_fluxes_err = photon_fluxes_err[remove_max_mask]
        remove_upper_limit_mask = remove_upper_limit_mask[remove_max_mask]

    if state is not None:
        state.setdefault('source_names', []).append(source_name)

    return source_name, julian_dates, photon_fluxes, photon_fluxes_err, remove_upper_limit_mask


def visualize_processing_steps(file_path):
    plt.rcParams['font.serif'] = ['Times New Roman']  # 设置英文主字体为Times New Roman
    plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置中文字体为黑体（当遇到中文时使用）
    plt.rcParams['mathtext.fontset'] = 'stix'  # 数学符号使用STIX字体（类似Times New Roman风格）
    plt.rcParams['axes.unicode_minus'] = False  # 正确显示负号
    """可视化数据处理步骤"""
    # 创建图形
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('天文数据处理流程可视化', fontsize=16, fontweight='bold')

    # 1. 原始数据
    print("步骤1: 读取原始数据")
    source_name, jd_raw, flux_raw, err_raw, upper_mask_raw = get_csv_data(
        file_path, remove_upper_limit=False, remove_max_value_numbers=0)

    axes[0, 0].errorbar(jd_raw, flux_raw, yerr=err_raw, fmt='o', capsize=1.5,
                        label='正常数据', alpha=0.7, color='blue',linewidth=0.5)

    # 标记上限数据
    if np.any(upper_mask_raw):
        axes[0, 0].errorbar(jd_raw[upper_mask_raw], flux_raw[upper_mask_raw],
                            yerr=err_raw[upper_mask_raw] if not np.all(np.isnan(err_raw[upper_mask_raw])) else None,
                            fmt='v', capsize=1.5, color='red', label='上限数据', alpha=0.7, linewidth=0.5)

    axes[0, 0].set_title('1. 原始数据（包含上限值）')
    axes[0, 0].set_xlabel('儒略日 (JD)')
    axes[0, 0].set_ylabel('光子通量')
    axes[0, 0].legend()
    axes[0, 0].grid(True, alpha=0.3)

    # 2. 移除上限值后
    print("步骤2: 移除上限值")
    _, jd_no_upper, flux_no_upper, err_no_upper, _ = get_csv_data(
        file_path, remove_upper_limit=True, remove_max_value_numbers=0)

    axes[0, 1].errorbar(jd_no_upper, flux_no_upper, yerr=err_no_upper,
                        fmt='o', capsize=1.5, color='green', alpha=0.7,linewidth=0.5)
    axes[0, 1].set_title('2. 移除上限值后')
    axes[0, 1].set_xlabel('儒略日 (JD)')
    axes[0, 1].set_ylabel('光子通量')
    axes[0, 1].grid(True, alpha=0.3)

    # 3. 时间范围筛选后 (示例：从JD 2450020到2450150)
    print("步骤3: 应用时间范围筛选")
    start_date = (2010, 1, 1)
    end_date = (2010, 6, 1)
    start_jd = Time(f"{start_date[0]}-{start_date[1]:02d}-{start_date[2]:02d}").jd
    end_jd = Time(f"{end_date[0]}-{end_date[1]:02d}-{end_date[2]:02d}").jd
    print(f"时间筛选范围：{start_jd} - {end_jd}")
    _, jd_time_filtered, flux_time_filtered, err_time_filtered, _ = get_csv_data(
        file_path, remove_upper_limit=True,
        start_date=start_date, end_date=end_date,  # 示例日期
        remove_max_value_numbers=0)

    axes[1, 0].errorbar(jd_time_filtered, flux_time_filtered, yerr=err_time_filtered,
                        fmt='o', capsize=3, color='blue', alpha=0.7)
    axes[1, 0].axvspan(start_jd, end_jd, alpha=0.2, color='gray', label='时间筛选范围')
    axes[1, 0].set_title('3. 时间范围筛选后')
    axes[1, 0].set_xlabel('儒略日 (JD)')
    axes[1, 0].set_ylabel('光子通量')
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)

    # 4. 移除最大2个值后
    print("步骤4: 移除最大2个通量值")
    _, jd_final, flux_final, err_final, _ = get_csv_data(
        file_path, remove_upper_limit=True,
        start_date=(2010, 1, 1), end_date=(2010, 6, 1),
        remove_max_value_numbers=2)

    axes[1, 1].errorbar(jd_final, flux_final, yerr=err_final,
                        fmt='o', capsize=3, color='purple', alpha=0.7)

    # 标记被移除的最大值
    if len(flux_time_filtered) > 0:
        max_indices = np.argsort(flux_time_filtered)[-2:]
        axes[1, 1].scatter(jd_time_filtered[max_indices], flux_time_filtered[max_indices],
                           marker='x', s=100, color='red', linewidth=2,
                           label='被移除的最大值')

    axes[1, 1].set_title('4. 移除最大2个值后')
    axes[1, 1].set_xlabel('儒略日 (JD)')
    axes[1, 1].set_ylabel('光子通量')
    axes[1, 1].legend()
    axes[1, 1].grid(True, alpha=0.3)

    plt.tight_layout()
    # plt.savefig('data_processing_visualization.png', dpi=300, bbox_inches='tight')
    plt.show()

# 演示代码
if __name__ == "__main__":
    # 创建示例数据
    sample_file = r"S:\QPAwenz\6830\4FGL_J1700.0+6830_daily_2024_8_9.csv"

    # 可视化处理流程
    visualize_processing_steps(sample_file)