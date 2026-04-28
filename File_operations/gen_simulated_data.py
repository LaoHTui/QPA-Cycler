import numpy as np
import matplotlib.pyplot as plt
import os
import re


def generate_positive_signal(length=1000, noise_level=0.5, signal_type='random',
                             period_days=None, amplitude=1.0, freq_variation=0.1,
                             missing_rate=0.0, baseline_error=0.1, time_start=54682.0,time_step=7.0,
                             exposure=1e10, sys_error=0.05):
    """
    生成正值模拟时间序列，支持缺失值和Fermi测量误差

    参数:
    length: 数据点数量 (默认1000)
    noise_level: 噪声强度 (0-1, 默认0.5)
    signal_type: 信号类型: 'periodic', 'quasi-periodic', 'random' (默认)
    period_days: 周期性信号的周期长度 (天数)
    amplitude: 主信号振幅 (默认1.0)
    freq_variation: 准周期性信号频率变化强度 (默认0.1)
    missing_rate: 缺失值比例 (0-1, 默认0)
    baseline_error: 基线测量误差 (默认0.1)
    time_start: 起始时间 (默认54682.0, Fermi MJD时间格式)

    返回:
    time: 时间数组 (可能包含NaN)
    values: 数据数组 (包含缺失值NaN, 全部>0)
    errors: 误差数组 (对应每个数据点)
    """
    # # 自动计算时间步长：使时间序列跨度为周期的3倍
    # if period_days is None or signal_type == 'random':
    #     time_step = 0.01  # 默认时间步长
    # else:
    #     # 自动计算时间步长：使整个时间序列覆盖3个周期
    #     time_step = (3 * period_days) / length

    # 生成时间轴
    t_index = np.arange(length)
    time = time_start + t_index * time_step

    # 基础信号 - 确保所有值大于0
    if signal_type == 'random':
        # 生成正值随机噪声
        base_signal = np.random.exponential(1, length)
    else:
        if period_days is None:
            raise ValueError("Period must be specified for periodic signals")

        # 计算周期点数
        period_points = period_days / time_step

        if signal_type == 'periodic':
            # 正弦波基信号，调整到正值范围
            base_signal = amplitude * np.sin(2 * np.pi * t_index / period_points) + amplitude
        elif signal_type == 'quasi-periodic':
            # 准周期信号
            modulated_freq = 1 / period_points + freq_variation * np.sin(2 * np.pi * t_index * 0.01)
            phase = 2 * np.pi * np.cumsum(modulated_freq) * time_step
            base_signal = amplitude * np.sin(phase) + amplitude

        # 添加随机波动
        base_signal += 0.1 * amplitude * np.random.randn(length)

        # 确保最小值为正
        min_val = np.min(base_signal)
        if min_val <= 0:
            base_signal += (-min_val + 0.1 * amplitude)

    # 添加噪声 - 保持正值
    noise = np.abs(np.random.normal(0, noise_level, length))
    values = base_signal + noise

    # 生成测量误差 (Fermi卫星模型)
    # 典型Fermi源：通量1e-7 ph/cm²/s 对应约100光子/月
    count_rate = values * 1e7  # 缩放因子使数值合理
    lam = count_rate * exposure * time_step / len(time)
    # 用np.clip裁剪数组：下限0，上限1e18（兼容标量/数组）
    lam_clipped = np.clip(lam, 0, 1e8)
    photon_counts = np.random.poisson(lam_clipped)

    # 精确Fermi误差模型
    with np.errstate(divide='ignore', invalid='ignore'):
        # 统计误差部分
        statistical_error = np.sqrt(photon_counts) / exposure

        # 系统误差部分 (与通量成正比)
        systematic_error = sys_error * values

        # 总误差
        base_errors = np.sqrt(statistical_error ** 2 + systematic_error ** 2)

        # 添加随机波动 (5% 仪器不确定性)
        errors = np.abs(base_errors + 0.05 * base_errors * np.random.randn(length))

    # 添加缺失值
    if missing_rate > 0:
        missing_mask = np.random.rand(length) < missing_rate
        values[missing_mask] = np.nan
        errors[missing_mask] = np.nan

    return time, values, errors


def save_to_txt(filename, time, values, errors, signal_type, params=None, period_days=None):
    """
    保存时间序列到文本文件，符合指定格式

    参数:
    filename: 输出文件名
    time: 时间数组
    values: 数据数组
    errors: 误差数组
    signal_type: 信号类型标签
    params: 参数字典（可选）
    period_days: 以天为单位的周期长度（可选）
    """
    with open(filename, 'w') as f:
        # 写入文件头信息
        f.write(f"# Signal Type: {signal_type}\n")
        if period_days is not None:
            f.write(f"# Period: {period_days:.3f} days\n")
        if params is not None:
            # 写入所有参数值
            for key, value in params.items():
                f.write(f"# {key}: {value}\n")
        f.write("# Time\tValue\tError\n")

        # 写入数据点
        for t, val, err in zip(time, values, errors):
            if np.isnan(val) or np.isnan(err):
                f.write(f"{t:.4f}\t\t\n")
            else:
                f.write(f"{t:.4f}\t{val:.6f}\t{err:.6f}\n")


def parse_period_from_filename(filename):
    """从文件名解析周期信息"""
    # 匹配文件名格式: periodic_5.25days_123.txt
    match = re.search(r'periodic_([\d.]+)days_(\d+)', filename)
    if match:
        return float(match.group(1))

    # 匹配准周期文件名格式: quasiperiodic_5.25days_123.txt
    match = re.search(r'quasiperiodic_([\d.]+)days_(\d+)', filename)
    if match:
        return float(match.group(1))

    return None


# 批量生成并保存数据集（所有文件在同一目录）
def generate_and_save_dataset(output_dir="simulated_data",
                              num_random_type=5,
                              num_periodic_type=5,
                              num_quasi_periodic_type=5,
                              length=500,
                              noise_level=0.3,
                              amplitude=1.5,
                              freq_variation=0.2,
                              missing_rate=0.1,
                              baseline_error=0.1,
                              time_start=54682.0,
                              time_step = 7,
                              period_min=30.0,
                              period_max=300.0):
    """
    批量生成并保存三类时间序列到文本文件

    参数:
    output_dir: 输出目录
    num_per_type: 每类样本数
    length: 每个样本的长度
    noise_level: 基本噪声水平
    amplitude: 信号振幅
    freq_variation: 频率变化强度
    missing_rate: 缺失值比例
    baseline_error: 基线误差
    time_start: 起始时间（MJD格式）
    period_min: 最小周期长度（天）
    period_max: 最大周期长度（天）
    """
    # 创建输出目录
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print("Generating and saving datasets...")

    # 通用参数模板
    common_params = {
        'length': length,
        'amplitude': amplitude,
        'baseline_error': baseline_error,
        'time_start': time_start
    }

    # 生成随机信号（无周期）
    print(f"Generating {num_random_type} samples of random signals...")
    for i in range(num_random_type):
        # 随机调整参数
        nl = np.clip(noise_level * np.random.uniform(0.8, 1.2), 0.01, 1.0)
        mr = np.clip(missing_rate * np.random.uniform(0.5, 1.5), 0, 0.5)

        # 生成时间序列
        time, values, errors = generate_positive_signal(
            length=length,
            noise_level=nl,
            signal_type='random',
            missing_rate=mr,
            baseline_error=baseline_error,
            time_start=time_start,
            time_step=time_step
        )

        # 保存到文件
        filename = os.path.join(output_dir, f"random_{i + 1:03d}.txt")
        params = common_params.copy()
        params.update({
            'noise_level': nl,
            'missing_rate': mr
        })
        save_to_txt(filename, time, values, errors, 'random', params)
        print(f"Saved {filename}")

    # 生成周期信号
    print(f"\nGenerating {num_periodic_type} samples of periodic signals...")
    for i in range(num_periodic_type):
        # 随机调整参数
        nl = np.clip(noise_level * np.random.uniform(0.8, 1.2), 0.01, 1.0)
        mr = np.clip(missing_rate * np.random.uniform(0.5, 1.5), 0, 0.5)
        period = np.random.uniform(period_min, period_max)

        # 生成时间序列
        time, values, errors = generate_positive_signal(
            length=length,
            noise_level=nl,
            signal_type='periodic',
            period_days=period,
            amplitude=amplitude,
            missing_rate=mr,
            baseline_error=baseline_error,
            time_start=time_start,
            time_step=time_step
        )

        # 保存到文件
        filename = os.path.join(output_dir, f"periodic_{period:.2f}days_{i + 1:03d}.txt")
        params = common_params.copy()
        params.update({
            'noise_level': nl,
            'missing_rate': mr,
            'period_days': period
        })
        save_to_txt(filename, time, values, errors, 'periodic', params, period)
        print(f"Saved {filename} (period: {period:.2f} days)")

    # 生成准周期信号
    print(f"\nGenerating {num_quasi_periodic_type} samples of quasi-periodic signals...")
    for i in range(num_quasi_periodic_type):
        # 随机调整参数
        nl = np.clip(noise_level * np.random.uniform(0.8, 1.2), 0.01, 1.0)
        mr = np.clip(missing_rate * np.random.uniform(0.5, 1.5), 0, 0.5)
        period = np.random.uniform(period_min, period_max)
        fv = freq_variation * np.random.uniform(0.5, 1.5)

        # 生成时间序列
        time, values, errors = generate_positive_signal(
            length=length,
            noise_level=nl,
            signal_type='quasi-periodic',
            period_days=period,
            amplitude=amplitude,
            freq_variation=fv,
            missing_rate=mr,
            baseline_error=baseline_error,
            time_start=time_start,
            time_step=time_step
        )

        # 保存到文件
        filename = os.path.join(output_dir, f"quasiperiodic_{period:.2f}days_{i + 1:03d}.txt")
        params = common_params.copy()
        params.update({
            'noise_level': nl,
            'freq_variation': fv,
            'missing_rate': mr,
            'period_days': period
        })
        save_to_txt(filename, time, values, errors, 'quasi-periodic', params, period)
        print(f"Saved {filename} (period: {period:.2f} days)")

    print(f"\nDataset generation complete! Total samples: {num_random_type + num_periodic_type + num_quasi_periodic_type}")
    print(f"Output directory: {output_dir}")
    return output_dir


def plot_with_period_info(data_dir="simulated_data", num_samples=5):
    """绘制带有周期信息的示例图"""
    # 获取所有文件
    files = [f for f in os.listdir(data_dir) if f.endswith('.txt')]
    np.random.shuffle(files)

    plt.figure(figsize=(15, 3 * min(num_samples, len(files))))

    for i, filename in enumerate(files[:num_samples]):
        filepath = os.path.join(data_dir, filename)
        signal_type = "random"
        period_info = None

        # 从文件名解析信号类型和周期
        if "periodic_" in filename and "quasi" not in filename:
            signal_type = "periodic"
            period_info = parse_period_from_filename(filename)
        elif "quasiperiodic_" in filename:
            signal_type = "quasi-periodic"
            period_info = parse_period_from_filename(filename)

        # 读取文件头获取更多信息
        with open(filepath, 'r') as f:
            header = [f.readline() for _ in range(3)]  # 读取前三行

        # 读取数据
        data = np.genfromtxt(filepath, comments='#', delimiter='\t')
        time = data[:, 0]
        values = data[:, 1]

        plt.subplot(min(num_samples, len(files)), 1, i + 1)

        # 分离有效数据和缺失值
        mask = ~np.isnan(values)

        if np.any(mask):
            plt.plot(time[mask], values[mask], '.', markersize=4)

            # 连接非缺失点
            segments = np.split(values, np.where(np.diff(np.isnan(values)))[0] + 1)
            t_segments = np.split(time, np.where(np.diff(np.isnan(values)))[0] + 1)
            for seg_val, seg_time in zip(segments, t_segments):
                if len(seg_val) > 1 and not np.any(np.isnan(seg_val)):
                    plt.plot(seg_time, seg_val, '-', color='gray', alpha=0.7)

        title = f"{signal_type.capitalize()} Signal: {filename}"
        if period_info:
            title += f" | Period: {period_info:.2f} days"
        plt.title(title)
        plt.xlabel('Time (MJD)')
        plt.ylabel('Flux')

        # 添加网格线
        plt.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(data_dir, 'signal_examples.png'), dpi=120)
    plt.show()


def plot_period_distribution(data_dir="simulated_data"):
    """绘制周期分布图"""
    files = [f for f in os.listdir(data_dir) if ("periodic_" in f or "quasiperiodic_" in f) and f.endswith('.txt')]

    periods = []
    labels = []

    for filename in files:
        filepath = os.path.join(data_dir, filename)
        period = parse_period_from_filename(filename)
        if period is not None:
            periods.append(period)
            if "quasiperiodic_" in filename:
                labels.append("Quasi-periodic")
            else:
                labels.append("Periodic")

    if not periods:
        print("No periodic files found")
        return

    # 为两类信号创建不同的颜色
    colors = ['blue' if label == 'Periodic' else 'green' for label in labels]

    plt.figure(figsize=(10, 6))

    # 绘制柱状图分布
    plt.hist(periods, bins=20, alpha=0.7, color='skyblue', edgecolor='black')

    # 绘制散点图区分周期和准周期
    plt.scatter(periods, [0.5] * len(periods), c=colors, alpha=0.7, s=100,
                label=['Periodic', 'Quasi-periodic'])

    plt.title('Distribution of Periods')
    plt.xlabel('Period (days)')
    plt.ylabel('Number of samples')
    plt.grid(True, alpha=0.3)

    # 添加图例
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='Periodic',
               markerfacecolor='blue', markersize=10),
        Line2D([0], [0], marker='o', color='w', label='Quasi-periodic',
               markerfacecolor='green', markersize=10)
    ]
    plt.legend(handles=legend_elements)

    plt.tight_layout()
    plt.savefig(os.path.join(data_dir, 'period_distribution.png'), dpi=120)
    plt.show()


def extract_true_periods(source_str):
    """
    从source字符串中提取所有真实周期值
    假设格式为: X_periodic_P1days_P2days_..._Pndays
    对于随机信号，返回空列表
    """
    # 检查是否为随机信号（文件名中包含random或stochastic等关键词）
    random_keywords = ['random', 'stochastic', 'noise', 'noperiod']
    if any(keyword in source_str.lower() for keyword in random_keywords):
        return []  # 随机信号，没有真实周期

    # 匹配所有数字（包括小数）后跟"days"的模式
    pattern = r'(\d+\.\d+)days'
    matches = re.findall(pattern, source_str)
    return [float(match) for match in matches]


def is_period_detected(true_period, detected_periods, detected_errors, tolerance=1.0):
    """
    检查真实周期是否被检测到（在误差范围内）

    参数:
    true_period: 真实周期值
    detected_periods: 检测到的周期列表
    detected_errors: 对应的误差列表
    tolerance: 误差容忍系数

    返回:
    bool: 是否检测到
    int: 匹配的检测周期索引（如果没有匹配则为-1）
    """
    for i, (detected_period, detected_error) in enumerate(zip(detected_periods, detected_errors)):
        # 跳过无效检测值（如-1）
        if detected_period == -1:
            continue

        lower_bound = detected_period - tolerance * detected_error
        upper_bound = detected_period + tolerance * detected_error

        if lower_bound <= true_period <= upper_bound:
            return True, i

    return False, -1


def analyze_period_accuracy(json_data:dict, tolerance=1.0):
    """
    分析周期检测的准确率，包括随机信号和无周期检测的情况

    参数:
    json_data: 包含检测结果的JSON数据
    tolerance: 误差容忍系数

    返回:
    dict: 包含详细分析结果和多种准确率指标
    """
    results = {}
    total_true_periods = 0
    total_detected_periods = 0
    correctly_detected_true_periods = 0
    correctly_detected_files_strict = 0  # 所有真实周期都被检测到且没有误检
    correctly_detected_files_relaxed = 0  # 至少一个真实周期被检测到
    correctly_rejected_random_signals = 0  # 正确识别随机信号（没有检测到周期）
    total_random_signals = 0  # 随机信号总数

    # 遍历所有条目
    for key, value in json_data.items():
        # 提取真实周期
        source_name = value["source"]
        true_periods = extract_true_periods(value["source"])

        # 判断是否为随机信号
        is_random_signal = len(true_periods) == 0

        if is_random_signal:
            total_random_signals += 1

        total_true_periods += len(true_periods)

        # 提取检测到的周期和误差
        detected_periods = []
        detected_errors = []

        # 找出所有的period_X字段
        period_keys = [k for k in value.keys() if k.startswith('period_')]

        for period_key in period_keys:
            period_data = value[period_key]
            detected_period = period_data["period"]
            detected_error = period_data["period_err"]

            # 检查是否为无效检测值（如-1）
            if detected_period == -1:
                # 对于无效检测，我们只记录但不计入总检测周期数
                continue

            detected_periods.append(detected_period)
            detected_errors.append(detected_error)

        total_detected_periods += len(detected_periods)

        # 处理随机信号
        if is_random_signal:
            # 对于随机信号，正确的结果应该是没有检测到任何周期
            if len(detected_periods) == 0:
                correctly_rejected_random_signals += 1
                results[key] = {
                    "type": "random_signal",
                    "source_name": source_name,
                    "correct": True,
                    "detected_periods": detected_periods,
                    "message": "正确识别为随机信号（没有检测到周期）"
                }
            else:
                results[key] = {
                    "type": "random_signal",
                    "source_name": source_name,
                    "correct": False,
                    "detected_periods": detected_periods,
                    "message": f"错误地将随机信号识别为有周期信号（检测到{len(detected_periods)}个周期）"
                }
            continue

        # 处理有周期信号
        # 检查每个真实周期是否被检测到
        detected_flags = []
        matched_indices = []

        for true_period in true_periods:
            detected, match_index = is_period_detected(
                true_period, detected_periods, detected_errors, tolerance
            )
            detected_flags.append(detected)
            matched_indices.append(match_index)

            if detected:
                correctly_detected_true_periods += 1

        # 检查误检（检测到但不对应任何真实周期）
        false_positives = []
        for i, detected_period in enumerate(detected_periods):
            # 检查这个检测周期是否匹配了任何真实周期
            is_false_positive = True
            for true_period, match_index in zip(true_periods, matched_indices):
                if match_index == i:
                    is_false_positive = False
                    break

            if is_false_positive:
                false_positives.append(i)

        # 判断文件级别的正确性
        all_detected = all(detected_flags)
        any_detected = any(detected_flags)
        no_false_positives = len(false_positives) == 0

        if all_detected and no_false_positives:
            correctly_detected_files_strict += 1

        if any_detected:
            correctly_detected_files_relaxed += 1

        # 记录结果
        results[key] = {
            "type": "periodic_signal",
            "source_name":source_name,
            "true_periods": true_periods,
            "detected_periods": detected_periods,
            "detected_errors": detected_errors,
            "detected_flags": detected_flags,
            "matched_indices": matched_indices,
            "false_positives": false_positives,
            "all_detected": all_detected,
            "any_detected": any_detected,
            "no_false_positives": no_false_positives,
            "strict_correct": all_detected and no_false_positives
        }

    # 计算各种准确率指标
    periodic_files = len(json_data) - total_random_signals

    detection_rate = correctly_detected_true_periods / total_true_periods if total_true_periods > 0 else 0
    false_positive_rate = (
                                      total_detected_periods - correctly_detected_true_periods) / total_detected_periods if total_detected_periods > 0 else 0

    strict_accuracy = correctly_detected_files_strict / periodic_files if periodic_files > 0 else 0
    relaxed_accuracy = correctly_detected_files_relaxed / periodic_files if periodic_files > 0 else 0

    random_accuracy = correctly_rejected_random_signals / total_random_signals if total_random_signals > 0 else 0

    overall_accuracy = (correctly_detected_files_strict + correctly_rejected_random_signals) / len(json_data) if len(
        json_data) > 0 else 0

    return {
        "detailed_results": results,
        "summary": {
            "total_files": len(json_data),
            "periodic_files": periodic_files,
            "random_files": total_random_signals,
            "total_true_periods": total_true_periods,
            "total_detected_periods": total_detected_periods,
            "correctly_detected_true_periods": correctly_detected_true_periods,
            "correctly_detected_files_strict": correctly_detected_files_strict,
            "correctly_detected_files_relaxed": correctly_detected_files_relaxed,
            "correctly_rejected_random_signals": correctly_rejected_random_signals,
            "detection_rate": detection_rate,
            "false_positive_rate": false_positive_rate,
            "strict_accuracy": strict_accuracy,
            "relaxed_accuracy": relaxed_accuracy,
            "random_accuracy": random_accuracy,
            "overall_accuracy": overall_accuracy
        }
    }

def print_accuracy(analysis:dict):
    # 打印详细结果
    print("详细分析结果:")
    for key, result in analysis["detailed_results"].items():
        print(f"文件 {key}:")
        if result["type"] == "random_signal":
            print(f"  类型: 随机信号")
            print(f"  正确: {result['correct']}")
            print(f"  检测周期: {result['detected_periods']}")
            print(f"  消息: {result['message']}")
        else:
            print(f"  类型: 周期信号")
            print(f"  真实周期: {result['true_periods']}")
            print(f"  检测周期: {result['detected_periods']}")
            print(f"  检测误差: {result['detected_errors']}")
            print(f"  检测标志: {result['detected_flags']}")
            print(f"  匹配索引: {result['matched_indices']}")
            print(f"  误检索引: {result['false_positives']}")
            print(f"  所有真实周期都被检测: {result['all_detected']}")
            print(f"  至少一个真实周期被检测: {result['any_detected']}")
            print(f"  没有误检: {result['no_false_positives']}")
            print(f"  严格正确: {result['strict_correct']}")
        print()

    # 打印总体统计
    summary = analysis["summary"]
    print("总体统计:")
    print(f"文件总数: {summary['total_files']}")
    print(f"周期信号文件数: {summary['periodic_files']}")
    print(f"随机信号文件数: {summary['random_files']}")
    print(f"真实周期总数: {summary['total_true_periods']}")
    print(f"检测周期总数: {summary['total_detected_periods']}")
    print(f"正确检测的真实周期数: {summary['correctly_detected_true_periods']}")
    print(f"严格正确的周期文件数: {summary['correctly_detected_files_strict']}")
    print(f"宽松正确的周期文件数: {summary['correctly_detected_files_relaxed']}")
    print(f"正确识别的随机信号数: {summary['correctly_rejected_random_signals']}")
    print(f"检测率: {summary['detection_rate'] * 100:.2f}%")
    print(f"误检率: {summary['false_positive_rate'] * 100:.2f}%")
    print(f"周期信号严格正确率: {summary['strict_accuracy'] * 100:.2f}%")
    print(f"周期信号宽松正确率: {summary['relaxed_accuracy'] * 100:.2f}%")
    print(f"随机信号正确率: {summary['random_accuracy'] * 100:.2f}%")
    print(f"总体正确率: {summary['overall_accuracy'] * 100:.2f}%")

def get_accuracy_datalist(analysis: dict) -> dict:
    """
    为生成word文档中三线表服务
    """
    type_list = []
    name_list = []
    flag_list = []
    real_period_list = []
    period_list = []
    period_err_list = []
    for key, result in analysis["detailed_results"].items():
        name_list.append(result["source_name"])
        if result["type"] == "random_signal":
            type_list.append(result["type"])
            flag_list.append(result['correct'])
            real_period_list.append("-")
            period_list.append("-")
            period_err_list.append("-")
        else:
            type_list.append(result["type"])
            flag_list.append(result['detected_flags'][0])
            real_period_list.append(result["true_periods"][0] if result["true_periods"] else "-" )
            period_list.append(result['detected_periods'][0] if result['detected_periods'] else "-")
            period_err_list.append(result['detected_errors'][0] if result['detected_errors'] else "-")

    return {
        "Source Name": name_list,
        "Signal Type": type_list,
        "Real Period": real_period_list,
        "Detected Period": period_list,
        "Detected Period Error": period_err_list,
        "Judgment": flag_list,
    }


# 主程序 - 直接调用
if __name__ == "__main__":
    # 设置合理的参数
    output_dir = generate_and_save_dataset(
        output_dir=r"S:\\example\\data",
        num_random_type=2,# 每类生成样本个数（测试用）
        num_periodic_type=2,
        num_quasi_periodic_type=2,
        length=500,  # 每个样本数据点
        noise_level=0.3,  # 基础噪声水平
        amplitude=1.5,  # 信号振幅
        freq_variation=0.1,  # 准周期频率变化强度
        missing_rate=0.01,  # 缺失率
        baseline_error=0.1,  # 基线误差
        time_start=54682.0,  # 起始时间
        time_step=30,   # 时间步长
        period_min=130.0,  # 最小周期
        period_max=1500.0  # 最大周期
    )

    # 可视化示例
    plot_with_period_info(output_dir, num_samples=6)
    plot_period_distribution(output_dir)