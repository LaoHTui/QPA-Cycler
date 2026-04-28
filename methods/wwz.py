import os
import warnings
import numpy as np
import matplotlib
matplotlib.use('Agg') #加这个就不会崩溃
import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import matplotlib.gridspec as gridspec
import math
from numba import njit, prange
from scipy.stats import norm
from joblib import Parallel, delayed
import matplotlib.dates as mdates

from methods.lsp import gen_TK95_noise

warnings.filterwarnings('ignore', category=RuntimeWarning,
                        message='Mean of empty slice')

plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False


@njit(cache=True)
def _solve_3x3(
        a00, a01, a02,
        a10, a11, a12,
        a20, a21, a22,
        b0, b1, b2
):
    """
    解 3x3 线性方程组 A x = b
    使用带部分主元的高斯消元。
    如果矩阵接近奇异，会做极小正则处理，避免数值崩溃。
    """
    M = np.empty((3, 4), dtype=np.float64)

    M[0, 0] = a00
    M[0, 1] = a01
    M[0, 2] = a02
    M[0, 3] = b0
    M[1, 0] = a10
    M[1, 1] = a11
    M[1, 2] = a12
    M[1, 3] = b1
    M[2, 0] = a20
    M[2, 1] = a21
    M[2, 2] = a22
    M[2, 3] = b2

    for col in range(3):
        # 找主元
        pivot = col
        max_abs = abs(M[col, col])
        for row in range(col + 1, 3):
            v = abs(M[row, col])
            if v > max_abs:
                max_abs = v
                pivot = row

        # 如果主元太小，做一个极小正则，防止除零
        if max_abs < 1e-15:
            M[col, col] = M[col, col] + 1e-12
            max_abs = abs(M[col, col])
            if max_abs < 1e-15:
                return 0.0, 0.0, 0.0

        # 交换行
        if pivot != col:
            for k in range(col, 4):
                tmp = M[col, k]
                M[col, k] = M[pivot, k]
                M[pivot, k] = tmp

        # 归一化当前行
        piv = M[col, col]
        for k in range(col, 4):
            M[col, k] = M[col, k] / piv

        # 消元
        for row in range(3):
            if row != col:
                factor = M[row, col]
                if factor != 0.0:
                    for k in range(col, 4):
                        M[row, k] = M[row, k] - factor * M[col, k]

    return M[0, 3], M[1, 3], M[2, 3]


@njit(parallel=False, cache=True)
def _wwz_core_numba(series, flux, tau, omega, c):
    """
    Numba 核心：并行计算 N_eff, V_x, V_y, A
    series, flux, tau, omega 都要求是 float32 连续数组 减少精度
    """
    tau_len = tau.shape[0]
    f_len = omega.shape[0]

    N_eff = np.empty((tau_len, f_len), dtype=np.float32)
    V_x = np.empty((tau_len, f_len), dtype=np.float32)
    V_y = np.empty((tau_len, f_len), dtype=np.float32)
    A = np.empty((tau_len, f_len), dtype=np.float32)

    weight_cutoff = 1e-9

    for i in prange(tau_len):
        tau_value = tau[i]

        # 保留原始逻辑：每个 tau 内部从 1 开始扫描
        n_start = 1

        for j in range(f_len):
            w_value = omega[j]

            # 累积量
            sum_w = 0.0
            weight2 = 0.0

            weighted_flux = 0.0
            weighted_flux_sq = 0.0

            sum_wc = 0.0
            sum_ws = 0.0
            sum_wcc = 0.0
            sum_wss = 0.0
            sum_wcs = 0.0

            sum_wcy = 0.0
            sum_wsy = 0.0

            valid_count = 0

            # 原始扫描逻辑
            for index in range(n_start, series.shape[0]):
                dz = w_value * (series[index] - tau_value)
                dw = math.exp(-c * dz * dz)

                if dw > weight_cutoff:
                    cdz = math.cos(dz)
                    sdz = math.sin(dz)
                    y = flux[index]

                    sum_w += dw
                    weight2 += dw * dw

                    weighted_flux += dw * y
                    weighted_flux_sq += dw * y * y

                    sum_wc += dw * cdz
                    sum_ws += dw * sdz
                    sum_wcc += dw * cdz * cdz
                    sum_wss += dw * sdz * sdz
                    sum_wcs += dw * cdz * sdz

                    sum_wcy += dw * cdz * y
                    sum_wsy += dw * sdz * y

                    valid_count += 1

                elif dz > 0.0:
                    # 继续往后只会更远，权重更小，可直接停止
                    break
                else:
                    # 还在 tau 左侧，但权重已经太小，更新起点
                    n_start = index + 1

            if valid_count == 0 or sum_w <= 0.0 or weight2 <= 0.0:
                N_eff[i, j] = np.nan
                V_x[i, j] = np.nan
                V_y[i, j] = np.nan
                A[i, j] = np.nan
                continue

            # 有效点数 5-4
            neff = (sum_w * sum_w) / weight2
            N_eff[i, j] = neff

            # V_x 5-9
            mean_flux = weighted_flux / sum_w
            vx = weighted_flux_sq / sum_w - mean_flux * mean_flux
            if vx <= 0.0:
                vx = 1e-12
            V_x[i, j] = vx

            # 构造 S 矩阵（归一化后的内积矩阵）
            S00 = 1.0
            S01 = sum_wc / sum_w
            S02 = sum_ws / sum_w
            S11 = sum_wcc / sum_w
            S12 = sum_wcs / sum_w
            S22 = sum_wss / sum_w

            # phi_x_ii
            b0 = mean_flux
            b1 = sum_wcy / sum_w
            b2 = sum_wsy / sum_w

            # 解线性方程，得到 ya
            a0, a1, a2 = _solve_3x3(
                S00, S01, S02,
                S01, S11, S12,
                S02, S12, S22,
                b0, b1, b2
            )

            # 这里不用逐点重建 y_t，再求 V_y；
            # 直接用等价形式：
            # E[y_t] = a^T mu,   E[y_t^2] = a^T S a
            ey = a0 + a1 * S01 + a2 * S02

            ey2 = (
                    a0 * a0 * S00
                    + 2.0 * a0 * a1 * S01
                    + 2.0 * a0 * a2 * S02
                    + a1 * a1 * S11
                    + 2.0 * a1 * a2 * S12
                    + a2 * a2 * S22
            )

            vy = ey2 - ey * ey
            V_y[i, j] = vy

            # 振幅谱 5-14
            A[i, j] = math.sqrt(a1 * a1 + a2 * a2)

    return N_eff, V_x, V_y, A


def wwz_Method(series, flux, tau_number, frequency_list, c, z_height=2000):
    """
    Numba 加速版 WWZ
    - 保持原 WWZ 数学逻辑
    - 只把计算核心交给 Numba
    - 结果输出格式与原函数一致
    """

    # -----------------------------
    # 1) 输入预处理
    # -----------------------------
    series = np.asarray(series, dtype=np.float64)
    flux = np.asarray(flux, dtype=np.float64)

    # 为了让扫描逻辑成立，确保按时间升序
    order = np.argsort(series)
    series = np.ascontiguousarray(series[order])
    flux = np.ascontiguousarray(flux[order])

    # 相对化时间
    series = series - series[0]
    data_len = len(series)

    # -----------------------------
    # 2) 频率与 tau 网格
    # -----------------------------
    freq_low = frequency_list[0]
    freq_high = frequency_list[1]
    freq_steps = frequency_list[2]

    f = np.arange(freq_low, freq_high + freq_steps, freq_steps, dtype=np.float64)
    omega = 2.0 * np.pi * f

    tau = np.linspace(series.min(), series.max(), tau_number, dtype=np.float64)

    # -----------------------------
    # 3) 调用 Numba 核心
    # -----------------------------
    # 第一次调用会有 JIT 编译开销，第二次开始才体现速度
    N_eff, V_x, V_y, A = _wwz_core_numba(series, flux, tau, omega, c)

    # -----------------------------
    # 4) 计算 Z
    # -----------------------------
    denominator = 2.0 * (V_x - V_y)
    Z = np.full_like(V_x, np.nan, dtype=np.float64)

    valid_mask = (denominator > 0.0) & (N_eff > 3.0)
    Z[valid_mask] = np.abs((N_eff[valid_mask] - 3.0) * V_y[valid_mask] / denominator[valid_mask])

    # 限制最大值
    Z[Z > z_height] = z_height

    # -----------------------------
    # 5) COI（向量化，保留原逻辑）
    # -----------------------------
    mid_tau = (series[0] + series[-1]) / 2.0
    coi_left_boundaries = np.zeros(len(f), dtype=np.float64)
    coi_right_boundaries = np.zeros(len(f), dtype=np.float64)

    for j, f1 in enumerate(f):
        if f1 == 0:
            coi_left_boundaries[j] = np.nan
            coi_right_boundaries[j] = np.nan
            continue

        temp = 2.0 * np.pi * f1 * np.sqrt(c)
        if temp < 1e-9:
            delta_T = 1e18
        else:
            delta_T = 1.0 / temp

        coi_left_boundaries[j] = min(series[0] + delta_T, mid_tau)
        coi_right_boundaries[j] = max(series[-1] - delta_T, mid_tau)

    COI = np.array([coi_left_boundaries, coi_right_boundaries], dtype=np.float64)

    # -----------------------------
    # 6) P_max
    # -----------------------------
    P_max = np.pi * np.sqrt(c) * np.abs(series[-1] - series[0])

    return tau, f, Z, COI, P_max, A, N_eff


#####################################周期检测#############################################


def gaussian(x, a, mu, sigma):
    """用于拟合峰值计算误差的高斯函数"""
    return a * np.exp(-(x - mu) ** 2 / (2 * sigma ** 2))


def get_z_projection(Z, taus, freqs, c):
    for j, f1 in enumerate(freqs):
        Z_copy = Z.copy()
        dt = 1 / (2 * np.pi * f1 * np.sqrt(c))
        # 找到该频率下，时间轴上处于 COI 内的索引
        mask_coi = (taus < (taus.min() + dt)) | (taus > (taus.max() - dt))
        Z_copy[mask_coi, j] = np.nan  # 将 COI 区域设为无效

    # 现在求平均，结果就只包含可靠区域了
    z_projection = np.nanmean(Z_copy, axis=0)
    return z_projection


def get_wwz_peaks(taus, freqs, Z, c, sig=None,
                  sig_threshold=0.997,
                  top_n=3,
                  min_period=0.0):
    """
    改进版：检测周期峰值、计算误差，并强制过滤掉小于 min_period 的候选峰。

    参数:
    - taus, freqs, Z, c: WWZ 基础参数
    - sig: MC 模拟显著性分布数据
    - sig_threshold: 显著性门槛 (如 0.997 对应 3-sigma)
    - top_n: 最终返回最强的几个峰
    - min_period: 关键参数！只有周期大于此值的峰才会被处理（单位与 tau 一致）
    """

    # 1. 获取 WWZ 平面在频率轴上的投影
    z_proj = get_z_projection(Z, taus, freqs, c)

    # 2. 找到所有局部峰值 (初步筛选)
    # prominence 设置为最大值的 5%，避免在纯噪声里挣扎
    peaks, _ = find_peaks(z_proj, prominence=np.max(z_proj) * 0.05)

    all_results = []
    df = freqs[1] - freqs[0] if len(freqs) > 1 else 0

    for p_idx in peaks:
        f_peak = freqs[p_idx]
        raw_period = 1.0 / f_peak

        # --- 核心逻辑：最小周期过滤 ---
        # 如果当前峰值的周期小于设定的最小值，直接跳过，不浪费计算资源进行后续拟合
        if raw_period < min_period:
            continue

        power_peak = z_proj[p_idx]

        # --- 显著性过滤 ---
        if sig is not None:
            sim_distribution = sig[:, p_idx]
            significance = np.sum(sim_distribution < power_peak) / len(sim_distribution)
            significance = min(significance, 1 - 1 / (len(sig) + 1))

            if significance < sig_threshold:
                continue
        else:
            significance = np.nan

        # --- 局部高斯拟合计算精确周期和误差 ---
        # 选取峰值附近的窄窗口
        window = 5
        idx_start = max(0, p_idx - window)
        idx_end = min(len(freqs), p_idx + window + 1)

        f_fit = freqs[idx_start:idx_end]
        z_fit = z_proj[idx_start:idx_end]

        if len(f_fit) >= 4:
            try:
                # 初始估值 [振幅, 频率中心, 标准差]
                p0 = [power_peak, f_peak, df * 2]
                popt, _ = curve_fit(gaussian, f_fit, z_fit, p0=p0, maxfev=1000)

                f_best = popt[1]
                f_sigma = abs(popt[2])
                f_fwhm = 2.355 * f_sigma  # 半高全宽

                period = 1.0 / f_best
                # 误差传递: ΔP = Δf / f^2
                period_err = f_fwhm / (f_best ** 2)

                # 再次检查拟合后的周期是否依然满足最小值限制
                if period < min_period:
                    continue
            except:
                f_best, period, period_err = f_peak, raw_period, 0.0
        else:
            f_best, period, period_err = f_peak, raw_period, 0.0

        # 计算对应的 Sigma 层级
        sigma_val = norm.ppf(significance) if not np.isnan(significance) else 0

        all_results.append({
            'period': round(period, 4),
            'period_err': round(period_err, 4),
            'power': round(power_peak, 3),
            'freq': round(f_best, 5),
            'significance': round(sigma_val, 2),
        })

    # 3. 排序逻辑：按功率从大到小排序
    all_results = sorted(all_results, key=lambda x: x['power'], reverse=True)

    # 4. 返回前 N 个
    return all_results[:top_n]


def get_wwz_significance_mc(t, flux, flux_err, beta, tau_num, freq_params, c, M=1000, n_jobs=-1):
    """
    运行 Monte Carlo 模拟计算显著性
    参考论文 3.4 节
    """
    mean_f = np.nanmean(flux)
    std_f = np.nanstd(flux)

    def one_sim():
        # 1. 生成符合斜率 beta 的随机红噪声
        s_flux = gen_TK95_noise(t, beta, std_f, mean_f)
        # 2. 加入观测白噪声 (泊松噪声)
        s_flux += np.random.normal(0, flux_err)

        # 3. 运行 WWZ
        _, _, sim_Z, _, _, _, _ = wwz_Method(t, s_flux, tau_num, freq_params, c)
        # 4. 获取投影功率谱 (Time-averaged)
        z_proj = np.nanmean(sim_Z, axis=0)
        return z_proj

    sigs = Parallel(n_jobs=n_jobs)(
        delayed(one_sim)() for _ in tqdm(range(M), desc=fr"{M} times Monte Carlo simulation calculation of WWZ"))
    sigs = np.array(sigs)  # Shape: (M, n_freqs)

    # 计算全局显著性 (每条曲线的最大值分布)
    global_max_dist = np.max(sigs, axis=1)

    return sigs, global_max_dist


def plot_wwz(taus, freqs, Z, COI, source_name, p_max, sig, g_sig, all_results, c,
             t0_abs=None, time_scale='JD',
             plot_mode="save", save_path=".",
             peak_prominence=5.0,
             use_log_scale_period=True):
    """
    WWZ 绘图函数（双 x 轴版本）
    - 底部 x 轴：tau（保持不变）
    - 顶部 x 轴：真实日期（YYYY-MM）

    参数
    ----
    t0_abs : float / pd.Timestamp / str / np.datetime64 / None
        观测起点的“绝对时间”。
        如果你的时间是 JD/MJD 数值，就传数值并设置 time_scale。
        如果你已经知道真实起始日期，也可以直接传 pd.Timestamp('YYYY-MM-DD')。
    time_scale : str
        'JD'  : 标准 Julian Date
        'MJD' : Modified Julian Date
        如果 t0_abs 本身就是 datetime / 字符串，则这个参数基本不会用到。
    """

    def _to_datetime(t_abs, scale='MJD'):
        """把绝对时间起点转成 pandas.Timestamp"""
        if isinstance(t_abs, pd.Timestamp):
            return t_abs
        if isinstance(t_abs, np.datetime64):
            return pd.Timestamp(t_abs)
        if isinstance(t_abs, str):
            return pd.Timestamp(t_abs)

        scale = str(scale).upper()
        if scale == 'JD':
            return pd.to_datetime(float(t_abs), origin='julian', unit='D')
        elif scale == 'MJD':
            return pd.to_datetime(float(t_abs), origin='1858-11-17', unit='D')
        else:
            raise ValueError(
                "time_scale 只能是 'JD'、'MJD'，或者直接传入 datetime / Timestamp / 字符串。"
            )

    # -----------------------------
    # 1) 数据准备
    # -----------------------------
    try:
        non_zero_mask = freqs > 0
        if not np.any(non_zero_mask):
            print("错误：频率数组中没有大于 0 的值。")
            return

        periods = 1.0 / freqs[non_zero_mask]
        Z_plot = Z[:, non_zero_mask]
        coi_left = COI[0][non_zero_mask]
        coi_right = COI[1][non_zero_mask]
    except Exception as e:
        print(f"错误：频率数组处理失败: {e}")
        return

    taus = np.asarray(taus, dtype=np.float64)
    periods = np.asarray(periods, dtype=np.float64)

    # -----------------------------
    # 2) 建图
    # -----------------------------
    fig = plt.figure(figsize=(12, 7))
    gs = gridspec.GridSpec(1, 2, width_ratios=[4, 1], wspace=0.05)

    # --- 主图：WWZ 热力图 ---
    ax1 = fig.add_subplot(gs[0])

    # 为 pcolormesh 构造边界
    if len(taus) > 1:
        tau_step = taus[1] - taus[0]
        taus_ext = np.append(taus, taus[-1] + tau_step)
    else:
        taus_ext = np.array([taus[0], taus[0] + 1.0], dtype=np.float64)

    if len(periods) > 1:
        period_step = np.diff(periods) / 2.0
        period_bounds = np.concatenate([
            [periods[0] - period_step[0]],
            periods[:-1] + period_step,
            [periods[-1] + period_step[-1]]
        ])
    else:
        period_bounds = np.array([periods[0] * 0.95, periods[0] * 1.05], dtype=np.float64)

    tau_grid, period_grid = np.meshgrid(taus_ext, period_bounds, indexing='ij')
    im = ax1.pcolormesh(tau_grid, period_grid, Z_plot, shading='auto', cmap='viridis')

    # --- COI 填充（稳健处理 NaN） ---
    coi_left_fill = np.copy(coi_left)
    coi_right_fill = np.copy(coi_right)
    coi_left_fill[np.isnan(coi_left_fill)] = taus.min()
    coi_right_fill[np.isnan(coi_right_fill)] = taus.max()

    ax1.fill_betweenx(periods, taus.min(), coi_left_fill, color='gray', alpha=0.4, lw=0)
    ax1.fill_betweenx(periods, coi_right_fill, taus.max(), color='gray', alpha=0.4, lw=0)

    ax1.plot(coi_left, periods, color='r', linewidth=1, alpha=0.8, label='COI')
    ax1.plot(coi_right, periods, color='r', linewidth=1, alpha=0.8)

    ax1.set_title(f'{source_name} - WWZ Spectrum', fontsize=15, pad=18)
    ax1.set_ylabel('Period', fontsize=12)
    ax1.set_xlabel('Tau (days)', fontsize=12)
    ax1.set_xlim([taus.min(), taus.max()])

    if p_max <= periods.max():
        ax1.set_ylim([periods.min(), p_max])
    else:
        ax1.set_ylim([periods.min(), periods.max()])

    if use_log_scale_period:
        ax1.set_yscale('log')

    ax1.legend(loc='upper right')

    # 注意：这里把 top=False，避免和“顶部日期轴”冲突
    ax1.tick_params(
        axis='both',
        which='both',
        top=False,
        right=True,
        labeltop=False,
        labelright=False,
        direction='in',
        labelsize=11,
        width=1,
        length=5
    )

    # -----------------------------
    # 3) 顶部双 x 轴：真实日期（YYYY-MM）
    # -----------------------------
    if t0_abs is not None:
        try:
            base_dt = _to_datetime(t0_abs, time_scale)

            tau_left = float(np.nanmin(taus))
            tau_right = float(np.nanmax(taus))

            date_left = base_dt + pd.to_timedelta(tau_left, unit='D')
            date_right = base_dt + pd.to_timedelta(tau_right, unit='D')

            ax_top = ax1.twiny()
            ax_top.patch.set_alpha(0.0)

            # 顶部轴的数值坐标使用 matplotlib date number
            ax_top.set_xlim(mdates.date2num(date_left), mdates.date2num(date_right))

            # 根据跨度自动调整月份刻度间隔
            span_days = max(1.0, (date_right - date_left).total_seconds() / 86400.0)
            span_months = max(1, int(np.ceil(span_days / 30.4375)))
            interval = max(1, int(np.ceil(span_months / 8)))  # 大致控制在 6~8 个刻度

            ax_top.xaxis.set_major_locator(mdates.MonthLocator(interval=interval))
            ax_top.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))

            ax_top.tick_params(
                axis='x',  # 只作用于 x 轴
                which='both',  # 同时应用于主刻度和次刻度
                top=True,  # 在顶部显示刻度线
                labeltop=True,  # 在顶部显示刻度标签
                bottom=False,  # 底部不显示刻度线
                labelbottom=False,  # 底部不显示刻度标签
                direction='in',  # 刻度线朝向图表内部
                labelsize=11,  # 刻度标签字体大小为 11
                width=1,  # 刻度线宽度为 1
                length=5,  # 刻度线长度为 5
                pad=4  # 刻度标签与刻度线的间距为 4
            )

            # 让顶部轴更干净一些
            ax_top.set_yticks([])
            ax_top.spines['bottom'].set_visible(False)
            ax_top.spines['left'].set_visible(False)
            ax_top.spines['right'].set_visible(False)

        except Exception as e:
            print(f"顶部日期轴绘制失败：{e}")

    # -----------------------------
    # 4) 右侧投影图
    # -----------------------------
    ax2 = fig.add_subplot(gs[1], sharey=ax1)

    z_projection = get_z_projection(Z, taus, freqs, c)

    ax2.plot(z_projection, periods, color='blue', linewidth=1.5, label='Projection')
    ax2.fill_betweenx(periods, 0, z_projection, color='blue', alpha=0.2)

    # 显著性曲线
    if sig is not None and g_sig is not None and len(sig) > 0 and len(g_sig) > 0:
        sigma3 = np.nanpercentile(sig, 99.7, axis=0)
        sigma2 = np.nanpercentile(sig, 95.0, axis=0)

        if np.all(np.isnan(z_projection)):
            global_sigma = np.nan
        else:
            obs_peak_power = np.nanmax(z_projection)
            global_p_value = np.mean(np.asarray(g_sig) >= obs_peak_power)

            # 避免 0 或 1 导致 norm.ppf 发散
            eps = 1.0 / (len(g_sig) + 1.0)
            global_p_value = np.clip(global_p_value, eps, 1 - eps)

            global_sigma = norm.ppf(1 - global_p_value)
    else:
        sigma3 = np.zeros_like(periods)
        sigma2 = np.zeros_like(periods)
        global_sigma = np.nan

    ax2.plot(sigma3, periods, 'r--', linewidth=1.2, label='3σ (99.7%)')
    ax2.plot(sigma2, periods, 'b--', linewidth=1.2, label='2σ (95%)')

    # 峰值标记
    if all_results:
        for r in all_results:
            peak_period = r["period"]
            ax2.axhline(
                y=peak_period,
                color='r',
                linestyle='--',
                linewidth=1.2,
                label=f'Peak: {r["period"]:.2f} ± {r["period_err"]:.2f}  '
                      f'{r["significance"]}σ  global: {global_sigma:.2f}σ'
            )

    ax2.set_xlabel('Avg Z-value', fontsize=12)
    ax2.set_title('Projection', fontsize=10)
    ax2.grid(True, linestyle='--', alpha=0.6)
    plt.setp(ax2.get_yticklabels(), visible=False)
    ax2.legend(fontsize='small')

    # -----------------------------
    # 5) Colorbar 和布局
    # -----------------------------
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    fig.colorbar(im, cax=cbar_ax, label='Z-value')

    plt.subplots_adjust(right=0.9, top=0.88)

    # -----------------------------
    # 6) 保存 / 显示
    # -----------------------------
    if plot_mode == "show":
        plt.show()
    elif plot_mode == "save":
        os.makedirs(save_path, exist_ok=True)
        full_path = f'{save_path}/{source_name}_WWZ.png'
        plt.savefig(full_path, dpi=300, bbox_inches='tight')
        print(f'图像已保存至: {full_path}')
        plt.close(fig)

if __name__ == '__main__':
    file_map = r"G:\fuxian\data\1_4FGL_J1555.7+1111_weekly_2026_3_17.csv"
    try:
        df = pd.read_csv(file_map, header=0, na_values='-')
    except pd.errors.EmptyDataError:
        df = pd.DataFrame()  # 返回空 DataFrame 或跳过文件
        print(f"文件 {file_map} 为空，已跳过！")

    # 根据数据类型处理CSV文件中的数据
    if df.iloc[:, 4].dtype == 'object':
        condition = ~df.iloc[:, 4].str.contains('<', na=True)  # 跳过<的数值
        filtered_df = df[condition]  # 过滤掉<的数值
    else:
        filtered_df = df

    # 从csv中提取数据列
    julian_dates_o = filtered_df.iloc[:, 1].values
    photon_fluxes_o = filtered_df.iloc[:, 4].values.astype(float)
    photon_fluxes_err = filtered_df.iloc[:, 5].values.astype(float)

    # 提取源名称 以'_'来分隔，若原数据不同，则可能会出现问题
    filename = os.path.basename(file_map)
    source_name = filename.split("_")[0] + "_" + filename.split("_")[1] + "_" + filename.split("_")[2]

    # 去掉错误数据如nan
    mask = ~np.isnan(julian_dates_o) & ~np.isnan(photon_fluxes_o)
    julian_dates = julian_dates_o[mask]
    photon_fluxes = photon_fluxes_o[mask]
    photon_fluxes_err = photon_fluxes_err[mask]

    # photon_fluxes = 5*np.sin(2*np.pi*julian_dates/365.25)
    tau_number = 1000
    c = 0.0125

    # N = len(julian_dates)
    # freq_start = 1/ np.abs(julian_dates[-1]-julian_dates[0])
    # freq_start = 0.0005
    # freq_end = freq_start * N / 2
    p_start = 100
    freq_end = 1 / p_start
    p_end = 3000
    freq_start = 1 / p_end

    frequency_parameter_list = [freq_start, freq_end, freq_start / 10]

    wwz_taus, wwz_freqs, wwz_Z, wwz_COI, wwz_P_max, wwz_A, wwz_N_eff = wwz_Method(julian_dates, photon_fluxes,
                                                                                  tau_number,
                                                                                  frequency_parameter_list, c,
                                                                                  z_height=2000)

    # beta_best, beta_err = get_psd_slope(julian_dates, photon_fluxes, photon_fluxes_err, source_name,
    #                                     method='psresp', M=1000, plot=False)
    # print(f"检测到最佳斜率 beta = {beta_best:.2f} ± {beta_err:.2f}")
    beta_best = 1.04
    MC = True
    if MC:
        sig, g_sig = get_wwz_significance_mc(julian_dates, photon_fluxes, photon_fluxes_err, beta_best, tau_number,
                                         frequency_parameter_list, c, M=100, n_jobs=-1)
    else:
        sig, g_sig = None,None

    wwz_result = get_wwz_peaks(wwz_taus, wwz_freqs, wwz_Z, c, sig,
                               sig_threshold=0.95,  # 提高门槛到 3-sigma (99.7%)
                               top_n=3)

    plot_wwz(wwz_taus, wwz_freqs, wwz_Z, wwz_COI, source_name, wwz_P_max,sig, g_sig,wwz_result, c,plot_mode="save",t0_abs=julian_dates[0])
