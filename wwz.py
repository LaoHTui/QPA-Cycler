import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
from scipy.signal import find_peaks, savgol_filter
from scipy.ndimage import gaussian_filter
from tqdm import tqdm
import matplotlib.gridspec as gridspec
from matplotlib.ticker import MaxNLocator
from matplotlib import transforms
import ruptures as rpt

plt.rcParams['font.sans-serif'] = ['SimHei']  # 使用黑体
plt.rcParams['mathtext.fontset'] = 'stix'  # STIX字体支持数学符号
plt.rcParams['font.family'] = 'STIXGeneral'
plt.rcParams['axes.unicode_minus'] = False


def wwz_Method(series, flux, tau_number, frequency_parameter_list, c, z_height=2000):
    """
    实现了WWZ（Weighted Wavelet Z-transform）方法的函数，用于分析时间序列数据。
                        based on G. Foster's FORTRAN

    参数:
    series: 一维时间序列数组。
    flux: 对应于时间序列的流量（或任何被测量）数组。
    tau_number: 时移τ列表的数量。
    frequency_list: 长度为3，频率范围列表，包括开始频率、结束频率和频率步长,即 [fre_min, fre_max, fre_step]。
    c: WWZ方法中的参数，影响权重函数的宽度。一般小于0.2 1-2
    z_height: Z变换结果的最大阈值，默认为2000。

    返回:
    tau: 时移τ数组
    f: 频率数组
    Z: 二维数组，包含了WWZ变换的结果。[len(tau), len(freq)]
    COI: COI边界数组 [2, len(f)]
    A: 二维数组，包含了振幅谱。
    N_eff: 二维数组，包含了有效数据点数。
    """
    # 相对化时间
    series = np.array(series)
    series = series - series[0]
    # 得到数据长度
    data_len = len(series)

    # 频率f
    freq_low = frequency_parameter_list[0]
    freq_high = frequency_parameter_list[1]
    freq_steps = frequency_parameter_list[2]
    f = np.arange(freq_low, freq_high + freq_steps, freq_steps)
    f_len = len(f)

    # 时移τ
    tau = np.linspace(min(series), max(series), tau_number)
    tau_len = len(tau)

    # 计算COI影响锥
    mid_tau = (min(series) + max(series)) / 2
    coi_left_boundaries, coi_right_boundaries = np.zeros(f_len), np.zeros(f_len)
    # 由权重wi衰减到1/e时判定
    for j, f1 in enumerate(f):
        if f1 == 0:  # 处理零频率情况
            coi_left_boundaries[j] = np.nan
            coi_right_boundaries[j] = np.nan
            continue

        temp = 2 * np.pi * f1 * np.sqrt(c)
        delta_T = 1 / temp if temp != 0 else np.nan

        if (min(series) + delta_T) > mid_tau or (max(series) - delta_T) < mid_tau:
            coi_left_boundaries[j] = np.nan
            coi_right_boundaries[j] = np.nan
        else:
            coi_left_boundaries[j] = min(series) + delta_T
            coi_right_boundaries[j] = max(series) - delta_T
    COI = np.array([coi_left_boundaries, coi_right_boundaries])

    # 初始化输出矩阵
    N_eff = np.zeros((tau_len, f_len))
    V_x = np.zeros((tau_len, f_len))
    V_y = np.zeros((tau_len, f_len))
    A = np.zeros((tau_len, f_len))

    # 定义极小值阈值
    EPS = 1e-12

    # 主循环,遍历所有时移和频率
    for i in tqdm(range(tau_len)):
        tau_value = tau[i]
        # 重置搜索起始点
        n_start = 0

        for j, fre_value in enumerate(f):
            if fre_value == 0:  # 跳过零频率
                continue

            w_value = 2 * np.pi * fre_value

            # 初始化相关项
            phi1, phi2, phi3, flux_new, weight_list = [], [], [], [], []
            weight2 = 0.0

            # 计算权重和相关项
            for index in range(n_start, data_len):
                dz = w_value * (series[index] - tau_value)
                dw = np.exp(-c * dz ** 2)

                # 添加权重阈值检查
                if dw > EPS:  # 使用更宽松的阈值
                    weight_list.append(dw)
                    weight2 += dw ** 2
                    flux_new.append(flux[index])
                    phi1.append(1.0)  # 标量值而非数组
                    phi2.append(np.cos(dz))
                    phi3.append(np.sin(dz))
                elif dz > 0:  # 时间超过当前τ，提前终止
                    break
                else:
                    # 更新时间起始点以提高效率
                    n_start = index + 1

            if len(weight_list) == 0:
                N_eff[i, j] = 0
                V_x[i, j] = 0
                V_y[i, j] = 0
                A[i, j] = 0
                continue

            # 转换为numpy数组
            weight_list = np.array(weight_list)
            flux_new = np.array(flux_new)
            phi1 = np.array(phi1)
            phi2 = np.array(phi2)
            phi3 = np.array(phi3)

            # 计算权重总和
            sum_wi = np.sum(weight_list)

            if sum_wi < EPS:
                N_eff[i, j] = 0
                V_x[i, j] = 0
                V_y[i, j] = 0
                A[i, j] = 0
                continue

            # 计算有效数据点数 5-4
            if weight2 < EPS:
                N_eff[i, j] = 0
            else:
                N_eff[i, j] = sum_wi ** 2 / weight2

            # 计算原始方差 V_x 5-9
            weighted_flux = weight_list * flux_new
            weighted_flux_sq = weight_list * flux_new ** 2
            mean_flux = np.sum(weighted_flux) / sum_wi
            mean_flux_sq = np.sum(weighted_flux_sq) / sum_wi
            V_x[i, j] = mean_flux_sq - mean_flux ** 2
            V_x[i, j] = max(V_x[i, j], EPS)  # 确保非负

            # 计算内积矩阵 S 4-2 4-3
            phi = [phi1, phi2, phi3]
            S = np.zeros((3, 3))
            for k in range(3):
                for m in range(3):
                    S[k, m] = np.sum(weight_list * phi[k] * phi[m]) / sum_wi

            # 计算S的逆矩阵（带条件数检查）
            try:
                cond_num = np.linalg.cond(S)
                if cond_num > 1e12 or np.linalg.det(S) < EPS:
                    # 病态矩阵，跳过计算
                    V_y[i, j] = 0
                    A[i, j] = 0
                    continue
                else:
                    S_inverse = np.linalg.inv(S)
            except np.linalg.LinAlgError:
                V_y[i, j] = 0
                A[i, j] = 0
                continue

            # 计算投影后的信号 4-4 4-1
            phi_x_ii = np.zeros(3)
            for k in range(3):
                phi_x_ii[k] = np.sum(weight_list * phi[k] * flux_new) / sum_wi

            ya = S_inverse.dot(phi_x_ii)
            y_t = ya[0] * phi1 + ya[1] * phi2 + ya[2] * phi3

            # 计算投影后的方差 V_y 5-10
            weighted_y_t = weight_list * y_t
            weighted_y_t_sq = weight_list * y_t ** 2
            mean_y_t = np.sum(weighted_y_t) / sum_wi
            mean_y_t_sq = np.sum(weighted_y_t_sq) / sum_wi
            V_y[i, j] = mean_y_t_sq - mean_y_t ** 2
            V_y[i, j] = max(V_y[i, j], 0)  # 确保非负

            # 计算振幅谱 5-14
            A[i, j] = np.sqrt(ya[1] ** 2 + ya[2] ** 2)

    # 计算WWZ变换结果 5-12（带稳定性检查）
    Z = np.zeros_like(V_x)
    for i in range(tau_len):
        for j in range(f_len):
            # 前置条件检查
            if N_eff[i, j] < 3.5 or V_x[i, j] <= V_y[i, j]:
                Z[i, j] = 0
                continue

            delta_V = V_x[i, j] - V_y[i, j]
            if delta_V < EPS:
                Z[i, j] = 0
            else:
                Z_val = (N_eff[i, j] - 3) * V_y[i, j] / (2 * delta_V)
                # 限制最大Z值
                Z[i, j] = min(Z_val, z_height) if Z_val > 0 else 0
    # print(f"lentau = {len(tau)}, lenf = {len(f)}, lenZ = {Z.shape}")

    return tau, f, Z, COI, A, N_eff


def gen_wwz_plot(taus, freqs, Z, COI, source_name, save_path, ticks_number=5):
    """
    生成并保存一个WWZ（Wavelet Transform）分析图。

    参数:
    taus - 时间尺度数组，用于x轴。
    freq - 频率数组，用于y轴。
    Z - WWZ分析的结果矩阵。
    source_name - 数据源名称，用于打印完成信息。
    save_path - 图片保存路径。
    ticks_number - 轴刻度数量，默认为5。
    """
    # 创建一个新的图像和轴

    fig = plt.figure(figsize=(10, 6))

    # 创建一个gridspec布局，定义两个子图的相对大小
    gs = gridspec.GridSpec(1, 2, width_ratios=[2.1, 1])

    # 创建子图
    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax1.set_title(f'{source_name} - WWZ', fontsize=12)
    # 设置y轴和x轴的标签和字体大小
    ax1.set_ylabel('Frequency (Hz)', fontsize=12)
    ax1.set_xlabel('Time (s)', fontsize=12)

    # 在taus数组的末尾添加一个元素，使其适合后续的绘图需求
    taus = np.append(taus, taus[-1] + taus[1] - taus[0])

    # 创建一个基于taus的网格
    tau_grid = np.tile(taus, (Z.shape[1] + 1, 1)).transpose()

    # 计算频率数组的步长
    freq_step = freqs[1] - freqs[0]

    # 计算每个频率区间的下界
    freq_lows = freqs - freq_step / 2

    # 计算最高频率的上界
    freq_highest = freqs.max() + freq_step / 2
    freq_bounds = np.append(freq_lows, freq_highest)

    # 创建一个基于频率界限的网格
    freq_grid = np.tile(freq_bounds, (Z.shape[0] + 1, 1))
    # 使用pcolormesh方法绘制WWZ分析图
    im = ax1.pcolormesh(tau_grid, freq_grid, Z)

    # 添加颜色条
    ax1.figure.colorbar(im, ax=ax1)

    # 5. 添加半透明COI区域
    ax1.fill_betweenx(freqs, taus[0], COI[0],
                      hatch='///', color='gray', alpha=0.6)
    ax1.fill_betweenx(freqs, COI[1], taus[-1],
                      hatch='///', color='gray', alpha=0.6)

    # 阴影线
    ax1.plot(COI[0], freqs, color='r', linewidth=1, alpha=0.8, label='COI')
    ax1.plot(COI[1], freqs, color='r', linewidth=1, alpha=0.8)
    ax1.legend()

    # 设置x轴和y轴的刻度数量
    ax1.xaxis.set_major_locator(MaxNLocator(nbins=ticks_number))  # x轴最大5个刻度
    ax1.yaxis.set_major_locator(MaxNLocator(nbins=ticks_number))  # y轴最大5个刻度
    # 精确设置边界
    ax1.set_xlim(min(taus), max(taus))
    ax1.set_ylim(min(freqs), max(freqs))

    projected_wwz = _projection(Z)
    base = plt.gca().transData
    rot = transforms.Affine2D().rotate_deg(-90)

    ax2.plot(np.sort(freqs)[::-1], projected_wwz, transform=rot + base)
    ax2.yaxis.set_visible(False)
    max_index = np.argmax(projected_wwz)
    sort_freq = np.sort(freqs)[::-1]
    max_freq = float(sort_freq[max_index])
    max_y = projected_wwz[max_index]

    # 在ax2中添加红色虚线
    ax2.axhline(y=-1 * max_freq, color='r', linestyle='--')

    # 添加文本标注
    ax2.text(max_freq - max_freq * 0.05, max_y, f'Period: {analysis_WWZ_Periods(freqs, Z):.2f}', va='center',
             ha='right', color='black',
             transform=transforms.Affine2D().rotate_deg(-90) + ax2.transData)

    ax2.set_xlabel('τ-average WWZ', fontsize=12)

    # 保存图像
    plt.savefig(f'{save_path}/{source_name} - WWZ.png', dpi=300)
    print(f'{source_name}的WWZ图像绘图完成,已保存在{save_path}/{source_name} - WWZ.png')
    plt.close()
    return None


def _projection(wwz_data):
    wwz_data = np.array(wwz_data)
    len_freq = wwz_data.shape[1]
    len_tau = wwz_data.shape[0]
    projected_wwz = []

    for i in range(len_freq):
        ave = np.sum(wwz_data[:, i]) / len_tau
        projected_wwz.append(ave)

    return projected_wwz


def analysis_WWZ_Periods(freq_list, wwz_data):
    projected_wwz = _projection(wwz_data)
    max_index = np.argmax(projected_wwz)
    wwz_max = np.max(projected_wwz)

    possible_freq = freq_list[max_index]
    possible_period = round(1 / possible_freq, 2)
    print(f'WWZ_Projection最大值{wwz_max}，对应频率为{possible_period}')
    return possible_period


def apply_coi_constraints(tau, freqs, Z, COI):
    """
    应用COI约束，将不可靠区域置零

    参数:
    tau: 时间尺度数组
    freqs: 频率数组
    Z: WWZ变换结果矩阵
    COI: 影响锥边界 [2, len(freqs)]

    返回:
    Z_masked: 应用COI约束后的WWZ矩阵
    """
    Z_masked = Z.copy()

    # 创建COI掩码
    coi_mask = np.zeros_like(Z, dtype=bool)

    for j, f_val in enumerate(freqs):
        # 获取当前频率的COI边界
        left_bound = COI[0, j]
        right_bound = COI[1, j]

        # 标记COI区域外的点
        for i, t_val in enumerate(tau):
            if t_val < left_bound or t_val > right_bound:
                coi_mask[i, j] = True

    # 将COI区域外的点置零
    Z_masked[coi_mask] = 0

    return Z_masked


def analyze_peak_frequency_variations(tau, freqs, Z, COI,
                                      min_size=5, confidence=0.95, peak_mode='peak'):
    # 应用COI约束
    Z_masked = apply_coi_constraints(tau, freqs, Z, COI)

    peak_freq_list = []
    time_list = []
    z_value_list = []

    # 1. 在频率维度上检测显著峰值
    if peak_mode == 'peak':
        # 计算全局噪声水平
        noise_level = np.median(Z_masked)

        for i, t in enumerate(tau):
            # 获取当前时间点的频谱
            spectrum = Z_masked[i, :]

            # 跳过全零或无效频谱
            if np.max(spectrum) < noise_level:
                continue

            # 寻找显著峰值
            peaks, properties = find_peaks(
                spectrum,
                height=noise_level * 3,  # 高于噪声水平3倍
                prominence=noise_level * 2,  # 显著高于背景
                distance=5  # 最小频率间隔
            )

            # 如果没有找到峰值，跳过
            if len(peaks) == 0:
                continue

            # 选择最显著的峰值（最高Z值）
            max_idx = np.argmax(properties['peak_heights'])
            freq_idx = peaks[max_idx]
            z_value = properties['peak_heights'][max_idx]

            # 获取当前频率对应的COI边界
            f_val = freqs[freq_idx]
            left_bound = COI[0, freq_idx]
            right_bound = COI[1, freq_idx]

            # 检查时间点是否在COI区域内
            if left_bound <= t <= right_bound:
                peak_freq_list.append(f_val)
                time_list.append(t)
                z_value_list.append(z_value)

    # 2. 在时间维度上追踪脊线
    ridges = []
    current_ridge = []

    # 按时间顺序处理检测到的峰值
    sorted_indices = np.argsort(time_list)
    prev_freq = None

    for idx in sorted_indices:
        t = time_list[idx]
        f = peak_freq_list[idx]
        z = z_value_list[idx]

        # 如果是第一个点或频率变化在合理范围内
        if prev_freq is None or abs(f - prev_freq) < 0.2 * prev_freq:
            current_ridge.append((t, f, z))
        else:
            # 频率跳变太大，结束当前脊线
            if len(current_ridge) >= min_size:
                ridges.append(current_ridge)
            current_ridge = [(t, f, z)]

        prev_freq = f

    # 添加最后一个脊线
    if len(current_ridge) >= min_size:
        ridges.append(current_ridge)

    # 3. 分析每个脊线
    segments = []
    for ridge in ridges:
        times = [point[0] for point in ridge]
        freqs = [point[1] for point in ridge]
        z_values = [point[2] for point in ridge]

        # 跳过太短的脊线
        if len(times) < min_size:
            continue

        # 线性回归分析频率漂移
        slope, intercept, r_value, p_value, std_err = stats.linregress(times, freqs)

        # 计算置信区间
        n = len(times)
        t_critical = stats.t.ppf((1 + confidence) / 2, df=n - 2)
        slope_ci = (slope - t_critical * std_err, slope + t_critical * std_err)

        # 判断是否显著漂移
        is_drifting = not (slope_ci[0] <= 0 <= slope_ci[1])

        segments.append({
            "start_time": times[0],
            "end_time": times[-1],
            "duration": times[-1] - times[0],
            "mean_freq": np.mean(freqs),
            "slope": slope,
            "slope_ci": slope_ci,
            "std_err": std_err,
            "is_drifting": is_drifting,
            "p_value": p_value,
            "segment_freq": freqs,
            "segment_time": times,
            "segment_z": z_values
        })

    # 4. 准备返回数据
    # 展平所有检测到的峰值用于绘图
    all_peak_freqs = peak_freq_list
    all_times = time_list

    # 创建平滑曲线（如果需要）
    if len(all_peak_freqs) > 3:
        window_length = min(11, len(all_peak_freqs))
        if window_length % 2 == 0:
            window_length -= 1
        polyorder = min(3, window_length - 1)
        try:
            freq_smooth = savgol_filter(all_peak_freqs, window_length, polyorder)
        except:
            freq_smooth = all_peak_freqs
    else:
        freq_smooth = all_peak_freqs

    # 突变点检测（基于脊线边界）
    jump_points = [seg["start_time"] for seg in segments[1:]]  # 后续脊线的起点

    return all_peak_freqs, all_times, jump_points, segments, freq_smooth

def print_segments(segments):
    print("\nDetected change points (time):")

    # Print detailed analysis report
    print("\n" + "=" * 50)
    print("Frequency Drift and Change Point Analysis Report")
    print("=" * 50)

    for i, seg in enumerate(segments):
        print(f"\nSegment #{i + 1}:")
        print(f"  Time range: {seg['start_time']:.1f} - {seg['end_time']:.1f} minutes")
        print(f"  Duration: {seg['duration']:.1f} minutes")
        print(f"  Mean frequency: {seg['mean_freq']:.4f} Hz")
        print(f"  Mean period: {1.0 / seg['mean_freq']:.4f} day")

        if seg["is_drifting"]:
            drift_rate = seg["slope"] * 60  # Convert to Hz/h
            ci_low = seg['slope_ci'][0] * 60
            ci_high = seg['slope_ci'][1] * 60
            print(f"  Drift rate: {drift_rate:.4f} Hz/h (95%CI: [{ci_low:.4f}, {ci_high:.4f}])")
        else:
            print("  No significant drift (95% CI contains 0)")

        print(f"  Slope p-value: {seg['p_value']:.6f}")
        print(f"  Data points: {len(seg['segment_freq'])}")

    return None
def plot_wwz(taus, freqs, Z, COI, peak_freq, freq_smooth, peak_tau, jumps, segments, source_name, plot_mode="save",
             save_path="."):
    fig = plt.figure(figsize=(14, 8))

    # 创建一个gridspec布局
    gs = gridspec.GridSpec(2, 2, width_ratios=[3, 1], height_ratios=[1, 1])

    # 主WWZ图
    ax1 = fig.add_subplot(gs[:, 0])
    ax1.set_title(f'{source_name} - WWZ', fontsize=15)

    # 在taus数组的末尾添加一个元素，使其适合后续的绘图需求

    taus_ext = np.append(taus, taus[-1] + taus[1] - taus[0])

    # 计算频率数组的步长
    freq_step = freqs[1] - freqs[0] if len(freqs) > 1 else freqs[0]

    # 计算每个频率区间的下界
    freq_lows = freqs - freq_step / 2

    # 计算最高频率的上界
    freq_highest = freqs.max() + freq_step / 2
    freq_bounds = np.append(freq_lows, freq_highest)

    tau_grid, freq_grid = np.meshgrid(taus_ext, freq_bounds, indexing='ij')

    # 绘制WWZ频谱
    im = ax1.pcolormesh(tau_grid, freq_grid, Z, shading='auto', cmap='viridis')
    plt.colorbar(im, ax=ax1, label='Z-value')
    # COI区域
    ax1.fill_betweenx(freqs, taus_ext[0], COI[0],
                      hatch='///', color='gray', alpha=0.6)
    ax1.fill_betweenx(freqs, COI[1], taus_ext[-1],
                      hatch='///', color='gray', alpha=0.6)
    # 阴影线
    ax1.plot(COI[0], freqs, color='r', linewidth=1, alpha=0.8, label='COI')
    ax1.plot(COI[1], freqs, color='r', linewidth=1, alpha=0.8)
    ax1.legend()

    ax1.set_ylabel('Frequency', fontsize=12)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.legend()
    ax1.set_ylim([freq_bounds[0], freq_bounds[-1]])

    # 峰值分布点图
    ax2 = fig.add_subplot(gs[0, 1])
    print(peak_tau, peak_freq)
    ax2.scatter(peak_tau, peak_freq, color='b', marker='+', label='Peak Frequency', alpha=0.8)
    ax2.plot(peak_tau, peak_freq, 'r-', alpha=0.5, label='Raw Data')
    ax2.plot(peak_tau, freq_smooth, 'g-', linewidth=1.5, alpha=0.3, label='Smoothed Data')
    # ax2.set_ylim([freq_bounds[0], freq_bounds[-1]])
    for jump in jumps:
        if jump < len(peak_tau):
            ax2.axvline(peak_tau[jump], color='r', linestyle='--', alpha=0.7, linewidth=1.5)

    for i, seg in enumerate(segments):
        start, end = seg["start_time"], seg["end_time"]
        mean_freq = seg["mean_freq"]
        slope = seg["slope"]

        # Plot segment mean line
        ax2.hlines(mean_freq, start, end, colors='purple', linewidth=2, alpha=0.7)

        # Plot drift trend line
        if seg["is_drifting"]:
            x_fit = np.array([start, end])
            y_fit = slope * (x_fit - start) + seg["segment_freq"][0]
            ax2.plot(x_fit, y_fit, 'm--', linewidth=2.5)

            # # Annotate drift rate
            # drift_rate = slope * 60  # Convert to Hz/h
            # ax1.text((start + end) / 2, mean_freq,
            #          f"{drift_rate:.2f} Hz/h",
            #          ha='center', va='bottom', fontsize=10,
            #          bbox=dict(facecolor='white', alpha=0.8))

    ax2.set_title("Frequency Drift and Change Point Analysis", fontsize=10)
    ax2.plot(COI[0], freqs, color='r', linewidth=1, alpha=0.8, label='COI')
    ax2.plot(COI[1], freqs, color='r', linewidth=1, alpha=0.8)
    ax2.set_ylabel("Frequency", fontsize=12)
    ax2.grid(True, linestyle='--', alpha=0.7)
    ax2.legend(loc='upper right')

    # 脊线显著性图
    ax3 = fig.add_subplot(gs[1, 1])

    # Create drift flag timeline
    drift_flag = np.zeros(len(taus))
    drift_significance = np.zeros(len(taus))

    for seg in segments:
        # 使用容差查找最近的索引
        start_idx = np.argmin(np.abs(taus - seg["start_time"]))
        end_idx = np.argmin(np.abs(taus - seg["end_time"]))

        # 验证找到的索引
        tol = 1e-5  # 根据实际情况调整容差
        if abs(taus[start_idx] - seg["start_time"]) > tol:
            print(f"Warning: start_time {seg['start_time']} not found. Using closest: {taus[start_idx]}")
        if abs(taus[end_idx] - seg["end_time"]) > tol:
            print(f"Warning: end_time {seg['end_time']} not found. Using closest: {taus[end_idx]}")

        # Drift flag (1=drifting, 0=stable)
        drift_flag[start_idx:end_idx] = 1 if seg["is_drifting"] else 0
        drift_significance[start_idx:end_idx] = 1 - seg["p_value"]

    # Plot drift flag
    ax3.plot(taus, drift_flag, 'r-', linewidth=2, label='Drift Status')

    # Plot drift significance
    ax3.set_ylim([-0.5, 1.5])

    # Mark change points
    for jump in jumps:
        if jump < len(peak_tau):
            ax3.axvline(peak_tau[jump], color='r', linestyle='--', alpha=0.7, linewidth=1.5)

    ax3.set_xlabel("Time (minutes)", fontsize=12)
    ax3.set_ylabel("Drift Status", fontsize=12)
    ax3.set_yticks([0, 1])
    ax3.set_yticklabels(['Stable', 'Drifting'])
    ax3.grid(True, linestyle='--', alpha=0.7)
    ax3.legend(loc='upper right')

    if plot_mode == "show":
        plt.show()
    if plot_mode == "save":
        plt.savefig(f'{save_path}/{source_name}_WWZ.png', dpi=300)
        print(f'{source_name}的WWZ图像绘图完成,已保存在{save_path}/{source_name} - WWZ.png')
        plt.close()


# ridge_analysis 待改进
def trace_ridges(tau, freqs, Z, COI, min_ridge_length=5, prominence_threshold=3.0, gauss_filter=True):
    """
    追踪WWZ频谱中的脊线（准周期信号）

    参数:
    tau: 时间尺度数组
    freqs: 频率数组
    Z: WWZ变换结果矩阵，大小为 (len(tau), len(freq))
    COI: 影响锥边界 [2, len(freqs)]
    min_ridge_length: 最小脊线长度
    prominence_threshold: 脊线显著性阈值

    返回:
    ridges: 脊线列表，每个脊线是(freq_trace, tau_trace, Z_trace)的元组
    """
    # 预处理：高斯平滑减少噪声影响
    if gauss_filter:
        Z_smoothed = gaussian_filter(Z, sigma=1.0)
    else:
        Z_smoothed = Z

    ridges = []
    ridge_id_map = np.zeros_like(Z, dtype=int) - 1  # 脊线ID映射，-1表示未分配

    # 计算每个频率点的噪声水平
    noise_level = np.median(Z, axis=0)

    # 按时间点追踪脊线
    for i, t in enumerate(tau):
        # 跳过COI区域外的点
        if t < COI[0, 0] or t > COI[1, -1]:
            continue

        # 获取当前时间点的频谱
        spectrum = Z_smoothed[i, :]

        # 寻找显著峰值
        peaks, properties = find_peaks(spectrum,
                                       height=noise_level * prominence_threshold,
                                       prominence=prominence_threshold,
                                       distance=5)

        # 处理找到的峰值
        for peak_idx in peaks:
            freq_candidate = freqs[peak_idx]
            z_value = Z[i, peak_idx]

            # 检查是否在COI区域内
            if t < COI[0, peak_idx] or t > COI[1, peak_idx]:
                continue

            # 检查是否可连接到现有脊线
            connected = False
            if i > 0:
                # 在上一时间点附近寻找候选脊线
                # 获取上一个时间点的候选ridge_id
                prev_candidates = np.where(ridge_id_map[i - 1] >= 0)[0]
                for cand_idx in prev_candidates:
                    ridge_id = ridge_id_map[i - 1, cand_idx]
                    prev_freq = ridges[ridge_id][0][-1]

                    # 频率变化在合理范围内
                    if abs(freq_candidate - prev_freq) < 0.1 * prev_freq:
                        # 添加到现有脊线
                        ridges[ridge_id][0].append(freq_candidate)
                        ridges[ridge_id][1].append(t)
                        ridges[ridge_id][2].append(z_value)
                        ridge_id_map[i, peak_idx] = ridge_id
                        connected = True
                        break

            # 创建新脊线
            if not connected:
                new_ridge = ([freq_candidate], [t], [z_value])
                ridges.append(new_ridge)
                ridge_id_map[i, peak_idx] = len(ridges) - 1

    # 过滤短脊线
    valid_ridges = []
    for ridge in ridges:
        if len(ridge[0]) >= min_ridge_length:
            # 计算脊线平均显著性
            avg_prominence = np.mean(ridge[2]) / np.median(noise_level)
            valid_ridges.append((ridge, avg_prominence))

    # 按显著性排序
    valid_ridges.sort(key=lambda x: x[1], reverse=True)

    return [ridge[0] for ridge in valid_ridges]


def analyze_ridge(ridge):
    """
    分析单个脊线的特征

    返回:
    ridge_features: 包含脊线特征的字典
    """
    freqs, times, z_values = ridge

    # 基本特征
    duration = times[-1] - times[0]
    mean_freq = np.mean(freqs)
    mean_period = 1 / mean_freq
    mean_z = np.mean(z_values)

    # 频率变化特征
    freq_changes = np.diff(freqs)
    freq_drift = np.mean(np.abs(freq_changes)) / mean_freq
    freq_trend = np.polyfit(times, freqs, 1)[0]  # 频率变化斜率

    # 周期稳定性
    periods = 1 / np.array(freqs)
    period_std = np.std(periods)

    # 脊线强度变化
    z_trend = np.polyfit(times, z_values, 1)[0]

    return {
        'start_time': times[0],
        'end_time': times[-1],
        'duration': duration,
        'mean_frequency': mean_freq,
        'mean_period': mean_period,
        'period_std': period_std,
        'frequency_drift': freq_drift,
        'frequency_trend': freq_trend,
        'mean_z': mean_z,
        'z_trend': z_trend,
        'frequencies': freqs,
        'times': times,
        'z_values': z_values
    }


def gen_wwz_plot_with_ridges(tau, freqs, Z, COI, ridges, source_name, save_path):
    """
    可视化WWZ结果和追踪到的脊线

    参数:
    tau: 时间尺度数组
    freqs: 频率数组
    Z: WWZ变换结果矩阵
    COI: COI边界 [2, len(freqs)]
    ridges: 脊线列表
    source_name: 数据源名称
    save_path: 图片保存路径
    """
    fig = plt.figure(figsize=(14, 8))

    # 创建一个gridspec布局
    gs = gridspec.GridSpec(2, 2, width_ratios=[3, 1], height_ratios=[1, 1])

    # 主WWZ图
    ax1 = fig.add_subplot(gs[:, 0])
    ax1.set_title(f'{source_name} - WWZ with Ridge Lines', fontsize=12)

    # 在taus数组的末尾添加一个元素，使其适合后续的绘图需求
    taus_ext = np.append(tau, tau[-1] + tau[1] - tau[0])

    # 创建一个基于taus的网格
    tau_grid = np.tile(taus_ext, (len(freqs) + 1, 1)).transpose()

    # 计算频率数组的步长
    freq_step = freqs[1] - freqs[0] if len(freqs) > 1 else freqs[0]

    # 计算每个频率区间的下界
    freq_lows = freqs - freq_step / 2

    # 计算最高频率的上界
    freq_highest = freqs.max() + freq_step / 2
    freq_bounds = np.append(freq_lows, freq_highest)

    # 创建一个基于频率界限的网格
    freq_grid = np.tile(freq_bounds, (len(tau) + 1, 1))

    # 绘制WWZ频谱
    im = ax1.pcolormesh(tau_grid, freq_grid, Z, shading='auto', cmap='viridis')
    plt.colorbar(im, ax=ax1, label='Z-value')

    # 绘制COI边界
    ax1.plot(COI[0], freqs, 'r--', linewidth=1, label='COI Boundary')
    ax1.plot(COI[1], freqs, 'r--', linewidth=1)

    # 绘制脊线
    colors = plt.cm.tab10(np.linspace(0, 1, len(ridges)))
    for i, ridge in enumerate(ridges):
        freqs_ridge, times_ridge, _ = ridge
        ax1.plot(times_ridge, freqs_ridge, color=colors[i],
                 linewidth=2, label=f'Ridge {i + 1}')

    ax1.set_ylabel('Frequency (Hz)', fontsize=12)
    ax1.set_xlabel('Time (s)', fontsize=12)
    ax1.legend()

    # 周期演化图
    ax2 = fig.add_subplot(gs[0, 1])
    for i, ridge in enumerate(ridges):
        freqs_ridge, times_ridge, _ = ridge
        periods = 1 / np.array(freqs_ridge)
        ax2.plot(times_ridge, periods, color=colors[i],
                 label=f'Ridge {i + 1}: {1 / np.mean(freqs_ridge):.2f}s')

    ax2.set_title('Period Evolution')
    ax2.set_ylabel('Period (s)')
    ax2.legend()

    # 脊线显著性图
    ax3 = fig.add_subplot(gs[1, 1])
    for i, ridge in enumerate(ridges):
        _, times_ridge, z_values = ridge
        ax3.plot(times_ridge, z_values, color=colors[i],
                 label=f'Ridge {i + 1}')

    ax3.set_title('Ridge Significance')
    ax3.set_ylabel('Z-value')
    ax3.set_xlabel('Time (s)')
    ax3.legend()

    plt.tight_layout()
    plt.savefig(f'{save_path}/{source_name}_wwz_ridges.png', dpi=300)
    print(f'WWZ脊线图像已保存: {save_path}/{source_name}_wwz_ridges.png')
    plt.close()


def full_area_ridge_analysis(series, flux, tau_number, frequency_list, c, source_name, save_path):
    """
    完整的脊线追踪与准周期分析流程

    参数:
    series: 时间序列
    flux: 流量数据
    tau_number: τ点数
    frequency_list: 频率范围 [f_min, f_max, f_step]
    c: WWZ参数
    source_name: 数据源名称
    save_path: 结果保存路径

    返回:
    ridge_features: 脊线特征列表
    """
    # 计算WWZ变换
    print("计算WWZ变换...")
    tau, freqs, Z, COI, A, N_eff = wwz_Method(series, flux, tau_number, frequency_list, c)

    # 应用COI约束
    print("应用COI约束...")
    Z_masked = apply_coi_constraints(tau, freqs, Z, COI)

    # 追踪脊线
    print("追踪脊线...")
    ridges = trace_ridges(tau, freqs, Z_masked, COI)

    # 分析脊线特征
    print("分析脊线特征...")
    ridge_features = []
    for ridge in ridges:
        features = analyze_ridge(ridge)
        ridge_features.append(features)

    # 可视化结果
    print("可视化结果...")
    gen_wwz_plot_with_ridges(tau, freqs, Z_masked, COI, ridges, source_name, save_path)

    # 打印脊线特征
    print("\n检测到的准周期脊线特征:")
    for i, feat in enumerate(ridge_features):
        print(f"\n脊线 {i + 1}:")
        print(f"  平均周期: {feat['mean_period']:.4f} ± {feat['period_std']:.4f} s")
        print(f"  持续时间: {feat['duration']:.2f} s (从 {feat['start_time']:.2f} 到 {feat['end_time']:.2f})")
        print(f"  频率漂移: {feat['frequency_drift'] * 100:.2f}%")
        print(f"  平均显著性: {feat['mean_z']:.2f}")

    return ridge_features
