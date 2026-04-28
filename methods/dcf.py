import os

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks

# 设置绘图环境
plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False

def dcf_Method(time, data, delta_tau, c, max_tau):
    """
    向量化离散相关函数 (DCF) 计算。
    delta_tau: 步长 (控制画图点的密度)
    c: 窗口宽度 (控制每个点的统计代表性，建议 c >= delta_tau)
    """
    time, data = np.array(time), np.array(data)
    mu, std = np.nanmean(data), np.nanstd(data, ddof=1)
    norm_data = (data - mu) / std if std > 0 else data

    dt_matrix = time[:, np.newaxis] - time[np.newaxis, :]
    udcf_matrix = norm_data[:, np.newaxis] * norm_data[np.newaxis, :]

    tau_axis = np.arange(0, max_tau + delta_tau, delta_tau)
    dcf_list, err_list, final_tau = [], [], []

    for t in tau_axis:
        mask = (dt_matrix >= t - c / 2) & (dt_matrix < t + c / 2)
        pairs = udcf_matrix[mask]
        M = len(pairs)
        if M > 1:
            dcf_val = np.mean(pairs)
            dcf_err = np.sqrt(np.sum((pairs - dcf_val) ** 2)) / (M - 1)
            dcf_list.append(dcf_val)
            err_list.append(dcf_err)
            final_tau.append(t)
        else:
            dcf_list.append(np.nan)
            err_list.append(np.nan)
            final_tau.append(t)

    return np.array(final_tau), np.array(dcf_list), np.array(err_list)


def calculate_fwhm_error(tau, dcf, peak_idx):
    """
    计算给定峰值的 FWHM (全宽半高) 并返回其一半作为不确定度。
    """
    peak_val = dcf[peak_idx]

    # 向左寻找半高点
    try:
        # 寻找局部的基准线 (由于 DCF 会有正负，我们取峰值到 0 的一半)
        half_max = peak_val / 2.0

        # 向左扫描
        left_idx = peak_idx
        while left_idx > 0 and dcf[left_idx] > half_max:
            left_idx -= 1

        # 向右扫描
        right_idx = peak_idx
        while right_idx < len(dcf) - 1 and dcf[right_idx] > half_max:
            right_idx += 1

        fwhm = tau[right_idx] - tau[left_idx]
        return fwhm / 2.0  # 返回半径作为误差范围
    except:
        return (tau[1] - tau[0]) * 2.0  # 兜底逻辑


def get_dcf_periods(tau, dcf, dcf_err, min_period=1.0, top_n=2, distance_days=10.0):
    """
    检测峰值，并使用 FWHM 计算物理误差。
    """
    dt = tau[1] - tau[0]
    dist_pix = max(1, int(distance_days / dt))

    mask = (tau >= min_period) & np.isfinite(dcf)
    valid_idx = np.where(mask)[0]

    peaks, _ = find_peaks(dcf[mask], distance=dist_pix, height=0.1)
    actual_indices = valid_idx[peaks]

    candidates = []
    for idx in actual_indices:
        # 使用 FWHM 逻辑
        err_physical = calculate_fwhm_error(tau, dcf, idx)

        candidates.append({
            'period': tau[idx],
            'uncertainty': err_physical,
            'dcf_strength': dcf[idx]
        })

    # 按强度排，取前 N，再按周期排
    candidates = sorted(candidates, key=lambda x: x['dcf_strength'], reverse=True)[:top_n]
    return sorted(candidates, key=lambda x: x['period'])


def plot_DCF(tau, dcf, dcf_err, candidates, source_name, c_val, plot_mode='save', save_path='.'):
    plt.figure(figsize=(12, 7))
    plt.errorbar(tau, dcf, yerr=dcf_err, fmt='o', ms=3, color='gray', alpha=0.5, label='DCF')
    plt.plot(tau, dcf, 'k-', lw=1, alpha=0.6)

    colors = ['#d62728', '#1f77b4', '#2ca02c', '#ff7f0e']
    for i, cand in enumerate(candidates):
        c = colors[i % len(colors)]
        p, err = cand['period'], cand['uncertainty']

        plt.axvline(p, color=c, ls='--', lw=2)
        # 阴影部分现在将真实反映 FWHM/2
        plt.axvspan(p - err, p + err, color=c, alpha=0.15,
                    label=f"P{i + 1}: {p:.2f} ± {err:.2f} d (DCF={cand['dcf_strength']:.2f})")

    plt.title(f'Discrete Correlation Function - {source_name} (c={c_val})', fontsize=14)
    plt.xlabel('Time Lag $\\tau$ (Days)')
    plt.ylabel('DCF Coefficient')
    plt.legend(loc='upper right')
    plt.grid(True, ls=':', alpha=0.5)
    if plot_mode == "show":
        plt.show()

    elif plot_mode == "save":
        os.makedirs(save_path, exist_ok=True)
        out_file = os.path.join(save_path, f'{source_name}_DCF.png')
        plt.savefig(out_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"{source_name} - DCF 绘图完成，保存在 {out_file}")


# --- 执行 ---
if __name__ == "__main__":
    # 生成带噪声的模拟信号
    np.random.seed(42)
    t = np.sort(np.random.uniform(0, 400, 300))
    # 45天周期
    y = np.sin(2 * np.pi * t / 45.0) + np.random.normal(0, 0.4, len(t))

    # 参数设置建议：
    # 对于 1 天一测的数据：delta_tau=1.0, c=2.0
    d_tau = 1.0
    c_width = 2.0

    tau, dcf, err = dcf_Method(t, y, delta_tau=d_tau, c=c_width, max_tau=130)
    best_results = get_dcf_periods(tau, dcf, err, min_period=10.0, top_n=2)

    plot_DCF(tau, dcf, err, best_results, "Object_A", c_width, plot_mode='show')