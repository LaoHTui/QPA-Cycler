import math
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import numpy as np
import matplotlib.pyplot as plt

import harmonic
import fwhm as c_fwhm
plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False

"""
    需要注意serise应为days，注意单位的转换
"""

def dcf_Method(serise, data, delta_tau, c, max_tau, normalize=False):
    """
    计算光子通量的时间延迟交叉相关函数。

    参数:
    Julian_data: 时间数据序列。
    Photon_Flux: 光子通量数据序列。
    delta_tau: 时间延迟步长。
    c: 时间窗口宽度。
    max_tau: 最大时间延迟。
    normalize: 是否对光子通量进行归一化处理，默认为False。

    返回:
    dcf: DCF值列表。
    err_dcf: DCF误差列表。
    tau_list: 时间延迟列表。
    """
    # 初始化变量
    tau, ave_F1, ave_F2, dev_F1, dev_F2, dcf_tau = 0, 0, 0, 0, 0, 0
    dcf, err_dcf, tau_list = [], [], []
    data = np.array(data)

    # 根据参数normalize决定是否归一化光子通量数据
    if normalize:
        data = (data - np.nanmin(data)) / (np.nanmax(data) - np.nanmin(data))

    # 主循环，遍历所有时间延迟
    while tau < max_tau:
        count, UDCF_sum = 0, []
        tau_list.append(tau)
        index_pairs_i, index_pairs_j = [], []

        # 寻找配对的光子通量指数
        for i in range(len(serise)):
            for j in range(len(serise)):
                if tau - c / 2 <= serise[j] - serise[i] < tau + c / 2:
                    index_pairs_i.append(i)
                    index_pairs_j.append(j)

        # 计算配对光子通量的平均值和标准差
        if len(index_pairs_i) > 1 and len(index_pairs_j) > 1:
            ave_F1, ave_F2, dev_F1, dev_F2 = np.nanmean(data[index_pairs_i]), np.nanmean(
                data[index_pairs_j]), np.nanstd(data[index_pairs_i], ddof=1), np.nanstd(
                data[index_pairs_j], ddof=1)
        elif len(index_pairs_i) == 1 or len(index_pairs_j) == 1:
            ave_F1, ave_F2, dev_F1, dev_F2 = np.nanmean(data[index_pairs_i]), np.nanmean(
                data[index_pairs_j]), data[index_pairs_i], data[index_pairs_j]
        else:
            ave_F1, ave_F2, dev_F1, dev_F2 = np.nan, np.nan, np.nan, np.nan

        # 计算未归一化的DCF值
        for i, j in zip(index_pairs_i, index_pairs_j):
            if np.isfinite(ave_F1) and np.isfinite(ave_F2) and dev_F1 != 0 and dev_F2 != 0:
                temp = (data[i] - ave_F1) * (data[j] - ave_F2) / (dev_F1 * dev_F2)
                if np.isfinite(temp):
                    UDCF_sum.append(temp.round(2))
                    count += 1

        # 计算DCF值并添加到列表中
        if count > 0:
            dcf_tau = np.nansum(UDCF_sum) / count
            dcf.append(dcf_tau)
        else:
            dcf.append(np.nan)

        # 处理DCF值为0的情况，将其替换为np.nan
        for i in range(len(dcf)):
            if np.array_equal(dcf[i], np.array([0.])):
                dcf[i] = np.nan

        # 计算DCF的误差
        temp2, count = [], 0
        for i, j in zip(index_pairs_i, index_pairs_j):
            if np.isfinite(ave_F1) and np.isfinite(ave_F2) and dev_F1 != 0 and dev_F2 != 0:
                temp = (data[i] - ave_F1) * (data[j] - ave_F2) / (dev_F1 * dev_F2)
                temp2.append((temp - dcf_tau) ** 2)
                count += 1

        if count > 1:
            err_dcf.append(math.sqrt(np.nansum(temp2)) / (count - 1))
        else:
            err_dcf.append(np.nan)

        # 更新tau值，进行下一轮循环
        tau += delta_tau

    # 返回所有计算得到的DCF值
    return dcf, err_dcf, tau_list

# 旧方法
def analysis_DCF_Periods(dcf, tau_list, distance=2, height=0.3): # 寻找DCF的周期性，待更新，主要使用寻峰算法

    tau_list = np.array(tau_list)
    peaks_index, _ = find_peaks(dcf, distance=distance, height=height)
    max_peaks_index = []
    for i in range(len(peaks_index)):
        if tau_list[peaks_index][i] != 0:
            max_peaks_index.append(peaks_index[i])


    pecks_tau = tau_list[max_peaks_index]
    print(f"----------------------{(pecks_tau)}-------------------------------")

    if len(pecks_tau) == 0:
        return 0
    else:
        possible_periods = min(pecks_tau)

    return int(possible_periods)

def get_DCF_results(dcf, dcf_err, taus, height=0.3, prominence=0.3, snr_threshold=3.0,
                    distance_rate=4, self_harmonic=True,sigma_threshold=2.0, reverse=False):
    # 找到峰值
    distance = max(1, (taus[1] - taus[0]) * distance_rate)
    peak_indices, _ = find_peaks(dcf, height=height, prominence=prominence, distance=distance)
    print(f"DCF方法找到 {len(peak_indices)} 个峰值")

    candidate_periods, candidate_periods_err, snr = [], [], []
    for idx in peak_indices:
        peak_height = dcf[idx]
        local_error = dcf_err[idx]  # 该峰值点处的误差估计
        signal_to_noise_ratio = peak_height / local_error

        if signal_to_noise_ratio < snr_threshold:  # 一个SNR阈值
            # print(f"在滞后 {taus[idx]} 处的峰可能不可靠 (SNR = {signal_to_noise_ratio:.2f})")
            pass
        else:
            # print(f"在滞后 {taus[idx]} 处发现显著峰，SNR = {signal_to_noise_ratio:.2f}")

            # 得到不确定度。
            fwhm_value = c_fwhm.calculate_fwhm(taus, dcf, taus[idx])["fwhm"]
            candidate_periods.append(taus[idx])
            # u_t = fwhm_value / (2 * signal_to_noise_ratio)
            u_t = fwhm_value / 2
            candidate_periods_err.append(u_t)
            snr.append(signal_to_noise_ratio)
    # 自谐波检测
    if self_harmonic:
        COMMON_RATIO = [1/6,1/7,1/8,1/9,1 / 5, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0, 5.0, 5 / 2, 5 / 3, 5 / 4, 6.0,7.0,8.0,9.0,10]
        base_mask = harmonic.self_harmonic_detection(candidate_periods, candidate_periods_err,
                                                     common_ratios=COMMON_RATIO, sigma_threshold=sigma_threshold,
                                                     reverse= reverse)
        candidate_periods = [p for p, mask in zip(candidate_periods, base_mask) if mask]
        candidate_periods_err = [p for p, mask in zip(candidate_periods_err, base_mask) if mask]
        snr = [p for p, mask in zip(snr, base_mask) if mask]

    return candidate_periods, candidate_periods_err, snr

def quadratic(x, a, b, c):
    return a * x ** 2 + b * x + c

def fit_peak_and_estimate_error(taus, dcf, dec_err, peak_index, window_size=3):
    """
    通过二次函数拟合DCF峰值并估计周期不确定性

    参数:
        lags: 滞后数组
        dcf: DCF值数组
        peak_index: 峰值在数组中的索引
        window_size: 在峰值两侧取的点数 (总点数 = 2*window_size + 1)

    返回:
        best_lag: 精确的峰值位置
        uncertainty: 周期不确定性估计
        popt: 拟合参数 [a, b, c]
        pcov: 参数的协方差矩阵
    """
    # 选择峰值附近的点
    start_idx = max(0, peak_index - window_size)
    end_idx = min(len(taus), peak_index + window_size + 1)
    x_fit = taus[start_idx:end_idx]
    y_fit = dcf[start_idx:end_idx]
    y_err_fit = dec_err[start_idx:end_idx]

    # 提供初始猜测
    p0 = [-0.5, 0, np.max(dcf)]

    # 执行二次拟合
    try:
        popt, pcov, *_ = curve_fit(f=quadratic, xdata=x_fit, ydata=y_fit, p0=p0, sigma=y_err_fit)
        a, b, c = popt
    except RuntimeError:
        print("拟合失败：可能无法收敛到合理解")

    # 计算精确的峰值位置 (抛物线顶点)
    best_lag = -b / (2 * a)

    # 计算顶点位置的不确定性 (误差传播)
    # 顶点位置公式: x0 = -b/(2a)
    # 对a和b的偏导数:
    dx0_da = b / (2 * a ** 2)
    dx0_db = -1 / (2 * a)

    # 从协方差矩阵中提取a和b的方差及协方差
    var_a = pcov[0, 0]
    var_b = pcov[1, 1]
    cov_ab = pcov[0, 1]

    # 误差传播公式: σ_x0^2 = (∂x0/∂a)^2 * σ_a^2 + (∂x0/∂b)^2 * σ_b^2 + 2*(∂x0/∂a)(∂x0/∂b)*cov(a,b)
    uncertainty = np.sqrt(
        (dx0_da ** 2 * var_a) +
        (dx0_db ** 2 * var_b) +
        (2 * dx0_da * dx0_db * cov_ab)
    )

    return taus[peak_index], uncertainty, popt, pcov

def plot_DCF(x, y, err, delta_tau, candidate_periods, candidate_periods_err, snr, source_name, save_path, plot_mode="save"):
    plt.figure(figsize=(12, 8))
    plt.errorbar(x, y, yerr=err, fmt='s', capsize=4, markersize=4, elinewidth=1, color='blue')
    plt.plot(x, y, color='red')
    COLORS = ['blue', 'green', 'red', 'purple', 'orange']
    if candidate_periods:
        for i, (period, error) in enumerate(
                zip(candidate_periods, candidate_periods_err)):
            color = COLORS[i % len(COLORS)]

            # 绘制候选周期线
            plt.axvline(x=period, color=color, linestyle='-', alpha=0.7,
                        label=f'candidate periods {i + 1}: {period:.1f}±{error:.1f} days, SNR={snr[i]:.2f}')

            # 绘制误差范围
            plt.axvspan(period - error, period + error,
                        alpha=0.1, color=color)

    plt.title(f'{source_name} - DCF  Δτ ={delta_tau}', fontsize=18)
    plt.xlabel('τ (days)', fontsize=15)
    plt.ylabel('DCF', fontsize=15)
    plt.legend(loc='upper right', fontsize=12)
    plt.grid(ls='--', linewidth=1, color='gray')
    if plot_mode == "show":
        plt.show()
    if plot_mode == "save":
        plt.savefig(f'{save_path}\\{source_name}_Δτ{delta_tau}_DCF.png', dpi=300)
        plt.close()

        print(f"{source_name} - DCF绘图完成, 保存在{save_path}\\{source_name}_DCF.png")



if __name__ == '__main__':
    # 加载测试数据
    # 创建时间序列 (儒略日)
    days = np.linspace(2450000, 2451000, 1000)  # 1000天，每天一个数据点

    # 波段2：延迟5天的相同信号 + 噪声
    band2 = 10 + 2 * np.sin(2 * np.pi * (days - 5) / 25) + np.random.normal(0, 1, len(days))

    # 使用示例
    delta_tau = 1.0  # 时间延迟步长(天)
    c = 2.0  # 时间窗口宽度(天)
    max_tau = 100.0  # 最大延迟(天)

    # 计算波段1和波段2的DCF
    dcf, err_dcf, tau_list = dcf_Method(days, band2, delta_tau, c, max_tau, normalize=True)

    # 分析结果
    candidate_periods, candidate_periods_err, snr = get_DCF_results(dcf, err_dcf, tau_list, height=0.3,
                                                                    prominence=0.3, snr_threshold=3.0,
                                                                    distance_rate=4, self_harmonic=True,
                                                                     sigma_threshold=1.50)
    print(f" candidate_periods: {candidate_periods}")
    print(f" candidate_periods_err: {candidate_periods_err}")
    print(f" snr: {snr}")

    # 绘制结果
    plot_DCF(tau_list, dcf, err_dcf, delta_tau, candidate_periods, candidate_periods_err, snr, "Test Source", "./", "show")
