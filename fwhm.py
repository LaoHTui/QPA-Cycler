import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from scipy.signal import find_peaks
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei']

def calculate_fwhm(x, y, peak_guess, resolution=  None):
    """
    计算一组数据的FWHM（半高全宽）

    参数:
    x : 横坐标数组
    y : 纵坐标数组

    返回:
    fwhm : 半高全宽值
    """
    assert len(x) == len(y), "x and y must have same length"
    x = np.asarray(x)
    y = np.asarray(y)

    # 找到峰值位置和高度
    peak_idx = np.argmin(np.abs(x - peak_guess))
    peak_height = y[peak_idx]

    # 计算半高位置
    half_max = peak_height / 2.0

    # 找到左侧交点
    left_idx = np.where(y[:peak_idx] <= half_max)[0]
    if len(left_idx) > 0:
        left_idx = left_idx[-1]  # 取最后一个小于等于半高的点
    else:
        left_idx = 0

    # 找到右侧交点
    right_idx = np.where(y[peak_idx:] <= half_max)[0]
    if len(right_idx) > 0:
        right_idx = right_idx[0] + peak_idx  # 调整索引位置
    else:
        right_idx = len(y) - 1

    # 线性插值提高精度
    # 左侧插值
    if left_idx < peak_idx - 1:
        x_left = np.interp(half_max,
                           [y[left_idx], y[left_idx + 1]],
                           [x[left_idx], x[left_idx + 1]])
    else:
        x_left = x[left_idx]

    # 右侧插值
    if right_idx > peak_idx:
        x_right = np.interp(half_max,
                            [y[right_idx - 1], y[right_idx]],
                            [x[right_idx - 1], x[right_idx]])
    else:
        x_right = x[right_idx]

    dx = np.mean(np.diff(x)) if resolution is None else resolution
    fwhm_uncertainty = dx * np.sqrt(2)  # 两个边界各贡献dx/√2
    # 计算FWHM
    fwhm = x_right - x_left

    return {
        'left_bound': x_left,
        'right_bound': x_right,
        'fwhm': fwhm,
        "fwhm_uncertainty": fwhm_uncertainty,
        'half_height': half_max
    }