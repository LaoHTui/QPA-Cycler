import os

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter

# 设置绘图中文字体
plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False


def jurkevich_Method(time, data, test_periods, m=10):
    """
    向量化 Jurkevich 方法实现。

    参数:
    time - 时间数组
    data - 观测数据数组
    test_periods - 待测试的周期数组
    m - 相位桶(Bins)的数量，通常取 10-20

    返回:
    v_norm - 归一化的方差比值 (Vm^2 / V_total^2)，越小表示周期性越强
    """
    data = np.array(data)
    time = np.array(time)
    n_points = len(data)

    # 预处理：移除缺失值并计算总方差
    mask = ~np.isnan(data)
    time, data = time[mask], data[mask]
    total_var = np.var(data)

    v_m2_list = []
    rel_time = time - time[0]

    for p in test_periods:
        # 1. 计算相位并分配到 m 个桶中
        phases = (rel_time / p) % 1.0
        bin_indices = (phases * m).astype(int)
        bin_indices = np.clip(bin_indices, 0, m - 1)

        # 2. 向量化计算每个桶的均值和平方和 (利用 np.bincount)
        counts = np.bincount(bin_indices, minlength=m)
        sums = np.bincount(bin_indices, weights=data, minlength=m)
        sq_sums = np.bincount(bin_indices, weights=data ** 2, minlength=m)

        # 3. 计算桶内方差 (Var = E[X^2] - (E[X])^2)
        valid_bins = counts > 1
        bin_vars = np.zeros(m)
        bin_vars[valid_bins] = (sq_sums[valid_bins] / counts[valid_bins]) - \
                               (sums[valid_bins] / counts[valid_bins]) ** 2

        # 4. Jurkevich 统计量：加权平均桶内方差
        # 也可以直接平均 np.mean(bin_vars[valid_bins])
        v_m2 = np.sum(bin_vars[valid_bins] * counts[valid_bins]) / np.sum(counts[valid_bins])
        v_m2_list.append(v_m2)

    # 归一化：Vm2 与总方差的比值
    v_norm = np.array(v_m2_list) / total_var
    return v_norm

def get_period(test_periods, v_norm, min_period=1):
    """
    定位最显著的单个峰值并计算其 FWHM 误差。

    Parameters:
    -----------
    test_periods : array_like
        测试周期数组
    v_norm : array_like
        归一化的v值，长度与test_periods相同
    min_period : float or str, optional
        允许的最小周期，默认'1'

    Returns:
    --------
    best_p : float
        最佳周期值
    error : float
        FWHM误差估计
    (p_left, p_right) : tuple
        周期边界
    """
    # 转换最小周期为数值类型
    min_period = float(min_period)

    # 创建掩码，只选择大于等于最小周期的数据点
    mask = test_periods >= min_period

    if not np.any(mask):
        raise ValueError(f"没有找到大于等于最小周期 {min_period} 的数据点")

    # 应用掩码筛选数据
    filtered_periods = test_periods[mask]
    filtered_v_norm = v_norm[mask]

    # 由于是找最小值，我们反转信号来寻找"峰值"
    inv_v = 1.0 - filtered_v_norm

    # 找到全域内最显著的凹陷（即 inv_v 的全局最大值）
    best_idx = np.argmax(inv_v)
    best_p = filtered_periods[best_idx]

    # 计算 FWHM 作为误差估计
    peak_val = inv_v[best_idx]
    base_val = np.median(inv_v)  # 以中位数为基准线
    half_max = base_val + (peak_val - base_val) / 2.0

    # 寻找左右边界
    try:
        # 左边界
        left_part = inv_v[:best_idx]
        left_idx = np.where(left_part < half_max)[0][-1]
        p_left = filtered_periods[left_idx]

        # 右边界
        right_part = inv_v[best_idx:]
        right_idx = np.where(right_part < half_max)[0][0] + best_idx
        p_right = filtered_periods[right_idx]

        error = (p_right - p_left) / 2.0
    except (IndexError, ValueError):
        error = np.nan
        p_left, p_right = best_p, best_p

    return best_p, error, (p_left, p_right)


def plot_Vm2(source_name, test_periods, v_norm, best_p, error, bounds, plot_mode='save', save_path='.'):
    """可视化分析结果"""
    plt.figure(figsize=(10, 6))

    # 绘制方差比例曲线
    plt.plot(test_periods, v_norm, 'k-', lw=1.2, label='$V_m^2 / V^2$')

    # 标记最显著周期
    plt.axvline(best_p, color='red', linestyle='--', alpha=0.8,
                label=f'Best Period: {best_p:.2f} ± {error:.2f} d')

    # 填充 FWHM 区域
    plt.axvspan(bounds[0], bounds[1], color='red', alpha=0.15, label='FWHM Range')

    plt.xlabel('Period (days)', fontsize=12)
    plt.ylabel('Normalized Variance Index', fontsize=12)
    plt.title(f'{source_name} - Jurkevich', fontsize=14)
    plt.grid(True, alpha=0.3)
    plt.legend()
    if plot_mode == "show":
        plt.show()

    elif plot_mode == "save":
        os.makedirs(save_path, exist_ok=True)
        out_file = os.path.join(save_path, f'{source_name}_JV.png')
        plt.savefig(out_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"{source_name} - LSP 绘图完成，保存在 {out_file}")


# --- 示例演示 ---
if __name__ == "__main__":
    # 1. 生成带噪声和趋势的模拟信号
    np.random.seed(42)
    t = np.linspace(0, 500, 1000)
    true_p = 42.5
    # 正弦信号 + 噪声 + 线性趋势
    y = np.sin(2 * np.pi * t / true_p) + 0.5 * np.random.randn(len(t)) + 0.002 * t

    # 2. 定义搜索范围
    test_p = np.linspace(10, 1000, 1000)

    # 3. 运行优化后的 Jurkevich 算法
    v_norm = jurkevich_Method(t, y, test_p, m=10)

    # 4. 提取最显著的一个周期
    best_p, p_err, bounds = get_period(test_p, v_norm, min_period=50)

    print(f"检测到的最显著周期: {best_p:.3f} +/- {p_err:.3f} 天")

    # 5. 绘图
    plot_Vm2("Object_X", test_p, v_norm, best_p, p_err, bounds, plot_mode='show')