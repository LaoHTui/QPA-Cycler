from collections import defaultdict
import numpy as np
from matplotlib import pyplot as plt
from scipy.signal import find_peaks
import harmonic
import fwhm
from harmonic import self_harmonic_detection

plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False


def jurkevich_Method(serise, data, test_periods, m, normalize=True):
    """
    实现 Jurkevich 方法进行时间序列分析。


    参数:
    serise - 时间数据数组（例如，儒略日期）。
    data - 对应的流量数据或测量值数组。
    test_periods - 要测试的周期数组。
    m - 与时间序列的谐波成分相关的参数。

    返回:
    normalized_values - 归一化后的方差值列表。
    f - 基于归一化值计算得到的系数列表。
    """

    if normalize:
        data = (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))

    # 初始化存储中间结果和最终结果的列表
    Vm2 = []
    normalized_values = []
    f = []

    # 遍历每个测试周期
    for p in test_periods:
        # 计算相对时间
        relative_time = serise - serise[0]

        # 计算每个时间点在相空间中的整数索引
        GN = np.floor(
            [m * relative_time[i] / p - m * np.floor(relative_time[i] / p) for i in range(len(relative_time))]).astype(
            int)

        # 初始化一个字典来按相位索引分组流量数据
        group_dict = defaultdict(list)

        # 分组流量数据
        for idx, value in enumerate(GN):
            group_dict[value].append(data[idx])

        # 将字典值转换为列表，并计算每组的方差
        group = list(group_dict.values())
        variances = [np.nanvar(g) for g in group if len(g) > 1]  # 至少2个点才能计算方差
        if variances:
            # 计算并存储当前周期的平均方差
            Vm2.append(np.mean(variances))
        else:
            Vm2.append(np.nan)  # 标记无效周期

    # 归一化 Vm2 值
    for value in Vm2:
        norm_value = round(((value - min(Vm2)) / (max(Vm2) - min(Vm2))), 8)
        normalized_values.append(norm_value)

        # 根据归一化值计算并存储系数
        if norm_value != 0:
            f.append(round(((1 - norm_value) / norm_value), 4))
        else:
            f.append(0)

    return normalized_values, f


# 旧方法
def analysis_Jurkevich_Periods(normalized_values, test_periods, allow_err=0.1, n=4) -> list:
    """
    根据Jurkevich方法分析并选取最小周期。

    参数:
    - normalized_values: 归一化值列表，用于评估不同周期的相关性。
    - test_periods: 测试周期列表，包含不同的周期选项。
    - allow_err: 允许的误差范围，用于判断周期间的差异是否可接受，默认为0.1。
    - n: 选取的最小周期数量，默认为4。

    返回:
    - 经过筛选的最小周期列表，包括单独的最小周期和组合周期。
    """

    # 选取归一化值最小的n个索引
    smallest_idx1 = np.argsort(normalized_values)[:n]
    # 移除小于或等于100的测试周期对应的归一化值
    for idx in smallest_idx1:
        if test_periods[idx] <= 100:
            normalized_values = np.delete(normalized_values, idx)
            test_periods = np.delete(test_periods, idx)
            smallest_idx1 = np.argsort(normalized_values)[:n]

    # 再次选取归一化值最小的n个索引
    smallest_idx2 = np.argsort(normalized_values)[:n]
    # 将对应的测试周期排序
    temp_periods = np.sort(test_periods[smallest_idx2])
    # 计算排序后的周期最大值与最小值之差
    R = max(temp_periods) - min(temp_periods)
    # 根据允许的误差范围移除部分周期
    to_remove = []
    for i in range(len(temp_periods) - 1, 0, -1):  # 从后向前遍历
        gap = abs(temp_periods[i] - temp_periods[i - 1])
        if gap / R < allow_err:
            to_remove.append(smallest_idx2[i])

    # 移除元素
    to_remove = sorted(to_remove, reverse=True)  # 从后向前移除
    for idx in to_remove:
        normalized_values = np.delete(normalized_values, idx)
        test_periods = np.delete(test_periods, idx)

    # 获取归一化值最小的n个索引对应的测试周期
    index = np.argsort(normalized_values)[:n]
    min_periods = test_periods[index]
    # 找出这些周期中的最小值
    fin_period = min_periods[0]

    # 将调整后的周期和可能的周期组合
    result = np.append(min_periods, fin_period)

    # 返回结果列表
    return result.tolist()


def get_Jurkevich_results(test_periods: list[float] | np.ndarray, v2: list[float] | np.ndarray,
                          max_serise=1000, v2_threshold=0.2, min_peak_distance=10, prominence=0.1, self_harmonic=True,
                          sigma_threshold=2.0, reverse=True):
    # 反转 Vm² 值（因为我们要找最小值）
    v2 = np.array(v2)
    inverted_v2 = 1 - v2

    # 寻找局部最小值（反转后为局部最大值）
    peaks, _ = find_peaks(
        inverted_v2,
        height=1 - v2_threshold,  # 只考虑显著的最小值
        distance=int(min_peak_distance / (test_periods[1] - test_periods[0])),  # 转换为索引距离
        prominence=prominence  # 最小突出度要求
    )
    # 获取候选周期
    candidate_periods, candidate_v2 = [], []
    for i in peaks:
        if test_periods[i] < max_serise:
            candidate_periods.append(test_periods[i])
            candidate_v2.append(v2[i])

    # 计算FWHM，得到候选周期的误差
    error_results = []
    left_boundary, right_boundary = [], []
    for p in candidate_periods:
        fwhm_results = fwhm.calculate_fwhm(test_periods, inverted_v2, p)
        # 参数估计的不确定度范围
        error_results.append(fwhm_results["fwhm"] / 2.0)

        # 用于画图，得到左右边界
        left_boundary.append(fwhm_results["left_bound"])
        right_boundary.append(fwhm_results["right_bound"])

    # 自谐波检测
    if self_harmonic:
        common_ratios = [1 / 5, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0, 5.0, 5 / 2, 5 / 3, 5 / 4]
        base_mask = harmonic.self_harmonic_detection(candidate_periods, error_results,
                                                     common_ratios=common_ratios, sigma_threshold=sigma_threshold,
                                                     reverse=reverse)
        candidate_periods = [p for p, mask in zip(candidate_periods, base_mask) if mask]
        error_results = [p for p, mask in zip(error_results, base_mask) if mask]
        candidate_v2 = [p for p, mask in zip(candidate_v2, base_mask) if mask]
        left_boundary = [p for p, mask in zip(left_boundary, base_mask) if mask]
        right_boundary = [p for p, mask in zip(right_boundary, base_mask) if mask]
        boundary_list = [left_boundary, right_boundary]

    return candidate_periods, error_results, candidate_v2, boundary_list


def plot_Vm2(source_name, periods, v2, candidate_periods, candidate_periods_err, boundary_list, plot_mode='save',
             save_path="."):
    """
        绘制 Jurkevich 结果

        参数:
        source_name - 源名称
        periods - 测试周期数组
        v2 - 归一化 Vm² 值
        candidate_periods - 候选周期列表
        error_results - 误差计算结果列表
        save_path - 保存路径
        """
    plt.figure(figsize=(14, 10))

    # 绘制 Vm² 曲线
    plt.plot(periods, v2, 'k-', linewidth=1.5, label='Vm²')
    # 绘制候选周期和误差范围
    COLORS = ['blue', 'green', 'red', 'purple', 'orange']
    for i, (period, error, left_bound, right_bound) in enumerate(
            zip(candidate_periods, candidate_periods_err, boundary_list[0], boundary_list[1])):
        color = COLORS[i % len(COLORS)]

        # 绘制候选周期线
        plt.axvline(x=period, color=color, linestyle='-', alpha=0.7,
                    label=f'candidate periods {i + 1}: {period:.1f}±{error:.1f} days')

        # 绘制误差范围
        plt.axvspan(left_bound, right_bound,
                    alpha=0.1, color=color)

    plt.xlabel('Test Period (days)', fontsize=14)
    plt.ylabel('Normalized $V_m^2$', fontsize=14)
    plt.title(f'{source_name} - Jurkevich', fontsize=16)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    if plot_mode == 'save':
        plt.savefig(f'{save_path}/{source_name}_jurkevich_JV.png', dpi=300)
        plt.close()
        print(f'{source_name} - Jurkevich绘图完成, 保存在{save_path}/{source_name}_jurkevich.png')
    elif plot_mode == 'show':
        plt.show()


# 示例使用
if __name__ == "__main__":
    # 生成模拟数据
    np.random.seed(42)
    n_points = 3000
    time = np.linspace(0, 1000, n_points)

    # 真实周期
    true_period = 250.0

    # 创建周期信号
    signal = 0.8 * np.sin(2 * np.pi * time / true_period)

    # 添加噪声和趋势
    noise = 0.3 * np.random.randn(n_points)
    trend = 0.001 * time

    # 组合数据
    data = signal + noise + trend

    # 测试周期范围
    test_periods = np.linspace(100, 1000, 500)

    # 运行 Jurkevich 方法
    v2, f = jurkevich_Method(time, data, test_periods, m=2)

    # 分析显著周期
    candidate_periods, error_results, candidate_v2, boundary_list = get_Jurkevich_results(test_periods, v2)

    # 绘制结果
    plot_Vm2("stt", test_periods, v2, candidate_periods, error_results, boundary_list, "./", 'show')
