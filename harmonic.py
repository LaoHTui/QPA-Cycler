from typing import Tuple, Any, List
import numpy as np

def is_harmonic(p1:float|int, err1:float|int, p2:float|int, err2:float|int, common_ratios:list, sigma_threshold=2.0) \
        -> tuple[bool, Any, float | Any]:
    """
    判断比值r是否在统计上与目标整数比target_ratio一致。
    假设误差err 独立且服从正态分布。若误差相关或非正态（如偏态分布），结果可能偏差。
    """
    if p1 == 0 or p2 == 0:
        print("❌ 输入的周期不能为0")
        return False, np.nan, np.nan
    r = p1 / p2
    # 误差传播公式: δr/r = sqrt( (δP1/P1)^2 + (δP2/P2)^2 )
    delta_r = r * np.sqrt((err1 / p1) ** 2 + (err2 / p2) ** 2)

    # 遍历给定的常见整数比，判定是否在可接受范围内成谐波
    for target_ratio in common_ratios:
        # 计算与目标值的偏差，并用比值的不确定性进行归一化
        deviation_in_sigma = abs(r - target_ratio) / delta_r if delta_r != 0 else np.nan

        # 如果偏差在N个标准差之内，则认为统计一致
        if deviation_in_sigma <= sigma_threshold:
            # print(f"✅ 在2σ水平上显著: r = {r:.3f} 与 {target_ratio} 一致 (偏差 = {deviation_in_sigma:.2f}σ)")
            return True, target_ratio, deviation_in_sigma

    # print(f"❌ 比值 r = {r:.3f} 与所列常见整数比在2σ水平上无显著关联。")
    return False, target_ratio, deviation_in_sigma


def self_harmonic_detection(p: list[float], err: list[float], common_ratios: list = None, sigma_threshold: float = 2.0,
                            reverse:bool = True) -> list[bool]:
    """
    从一组周期测量值中识别基波周期（base periods）。

    参数:
        p: 周期测量值列表
        err: 对应周期的误差列表
        common_ratios: 常见整数比列表（应包含分数和整数，如 [1/5, 1/4, 1/3, 1/2, 2/3, 1.0, 3/2, 2.0, 3.0, 4.0, 5.0]）
        sigma_threshold: 谐波检测的阈值（默认2σ）

    返回:
        base_periods: 基波周期列表（按从大到小排序）
        base_periods_err: 基波周期的误差列表
    """
    if not len(p) or not len(err) :
        return []
    if common_ratios is None:
        common_ratios = [1 / 5, 1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0, 5.0, 5 / 2, 5 / 3, 5 / 4]
    # 将周期和误差按周期值从大到小排序（基波通常是最大周期）
    # 排序处理（保留原始索引）
    indexed_p = list(enumerate(p))
    indexed_p.sort(key=lambda x: x[1], reverse=reverse)
    indices, sorted_p = zip(*indexed_p)
    sorted_err = [err[i] for i in indices]

    n = len(sorted_p)
    is_harmonic_flag = [False] * n  # 标记是否为谐波
    base_mask = [False] * len(p)  # 初始化原始长度的掩码
    base_periods = []
    base_periods_err = []

    # 从大到小遍历周期
    for i in range(n):
        if is_harmonic_flag[i]:
            continue  # 跳过已标记为谐波的周期
        else:
            orig_idx = indices[i]
            base_mask[orig_idx] = True
            # 当前周期作为候选基波
            base_periods.append(sorted_p[i])
            base_periods_err.append(sorted_err[i])


        # 检查其他周期是否是该基波的谐波
        for j in range(n):
            if i == j or is_harmonic_flag[j]:
                continue

            # 检查两种可能的谐波关系：
            is_harm1, _, d = is_harmonic(
                sorted_p[i], sorted_err[i],
                sorted_p[j], sorted_err[j],
                common_ratios,
                sigma_threshold = sigma_threshold
            )

            # 检查反比关系（交换参数顺序）
            is_harm2, _, d = is_harmonic(
                sorted_p[j], sorted_err[j],
                sorted_p[i], sorted_err[i],
                common_ratios,
                sigma_threshold = sigma_threshold
            )

            if is_harm1 or is_harm2:
                is_harmonic_flag[j] = True  # 标记为谐波


    return base_mask

if __name__ == '__main__':
    # 输入数据（多个相关列表）

    periods = [51.0, 99.0, 150.0, 201.0, 249.0]
    errors = [
        0.025009432271879985, 0.06047336703256632, 0.09436556202834964,
        0.14380380301738296, 0.07437549125875002]
    amplitudes = [10.2, 8.5, 7.3, 6.1, 5.0]
    phases = [0.1, 0.2, 0.3, 0.4, 0.5]

    # 自谐波检测
    base_mask = self_harmonic_detection(periods, errors,)

    # 使用掩码筛选其他数据
    base_periods = [p for p, mask in zip(periods, base_mask) if mask]
    base_errors = [err for err, mask in zip(errors, base_mask) if mask]
    base_amplitudes = [amp for amp, mask in zip(amplitudes, base_mask) if mask]
    base_phases = [phase for phase, mask in zip(phases, base_mask) if mask]

    print("基波周期:", base_periods)
    print("基波误差:", base_errors)
    print("基波振幅:", base_amplitudes)
    print("基波相位:", base_phases)
