import json
import os
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
import matplotlib.dates as mdates
from File_operations import get_csv_data as gcd


def get_lightcurve_data(file_path, config_map, m=8):
    """
    负责数据读取、预处理和统计计算
    """
    # 1. 读取配置
    with open(f'{config_map}.json') as f:
        config = json.load(f)

    start_date_str = config["global"].get("start_date")
    end_date_str = config["global"].get("end_date")

    if start_date_str and end_date_str:
        start_date = tuple(map(int, start_date_str.split(',')))
        end_date = tuple(map(int, end_date_str.split(',')))
    else:
        start_date, end_date = None, None

    remove_max_number = config['global'].get('remove_max_value_numbers', 0)

    # 2. 获取原始数据
    source_name, Julian_data, Photon_Flux, Photon_Flux_err, upper_limit_mask = gcd.get_csv_data(
        file_path,
        remove_upper_limit=False,
        start_date=start_date,
        end_date=end_date,
        remove_max_value_numbers=remove_max_number
    )

    # 3. 数据类型转换与校验
    jd = np.asarray(Julian_data, dtype=float)
    flux = np.asarray(Photon_Flux, dtype=float)
    flux_err = np.asarray(Photon_Flux_err, dtype=float)
    n_total = len(jd)

    if n_total == 0:
        raise ValueError("读取到的数据为空，请检查输入文件或日期范围。")

    if upper_limit_mask is None:
        upper_limit_mask = np.zeros(n_total, dtype=bool)
    else:
        upper_limit_mask = np.asarray(upper_limit_mask, dtype=bool)

    det_mask = ~upper_limit_mask
    n_det = int(np.sum(det_mask))
    n_ul = int(np.sum(upper_limit_mask))

    # 4. 时间转换 (JD -> Datetime)
    # JD 2440587.5 是 Unix epoch (1970-01-01)
    dates = pd.to_datetime(jd - 2440587.5, unit='D', origin='unix')

    # 5. 统计计算
    ul_ratio = n_ul / n_total if n_total > 0 else 0
    det_ratio = n_det / n_total if n_total > 0 else 0

    # P_min 计算逻辑
    p_min = np.nan
    if n_det > 1:
        t_range = jd[det_mask][-1] - jd[det_mask][0]
        p_min = round((t_range * m) / n_det, 2)

    # 封装处理后的数据
    processed_data = {
        'dates': dates,
        'flux': flux,
        'flux_err': flux_err,
        'upper_limit_mask': upper_limit_mask,
        'det_mask': det_mask
    }

    stats = {
        'source_name': source_name,
        'N_total': n_total,
        'N_eff': n_det,
        'N_ul': n_ul,
        'det_ratio': det_ratio,
        'ul_ratio': ul_ratio,
        'P_min': p_min,
        'm': m
    }

    return processed_data, stats


def plot_lightcurve(processed_data, stats, save_path, fig_mode='save'):
    """
    负责基于处理后的数据进行绘图
    """
    dates = processed_data['dates']
    flux = processed_data['flux']
    flux_err = processed_data['flux_err']
    upper_limit_mask = processed_data['upper_limit_mask']
    det_mask = processed_data['det_mask']

    source_name = stats['source_name']

    fig, ax = plt.subplots(figsize=(16, 6))

    # --- 绘制检测点 ---
    if stats['N_eff'] > 0:
        ax.errorbar(
            dates[det_mask],
            flux[det_mask],
            yerr=flux_err[det_mask],
            fmt='o-',
            color='black',
            ecolor='gray',
            elinewidth=1.2,
            capsize=2,
            markersize=3,
            linewidth=1.0,
            alpha=0.7,
            label=f"Detection (N_eff={stats['N_eff']}, {stats['det_ratio'] * 100:.1f}%)",
            zorder=4
        )

    # --- 绘制 Upper Limit 点 ---
    if stats['N_ul'] > 0:
        ax.scatter(
            dates[upper_limit_mask],
            flux[upper_limit_mask],
            marker='v',
            s=15,
            color='tab:red',
            alpha=0.65,
            label=f"Upper limit (N_ul={stats['N_ul']}, {stats['ul_ratio'] * 100:.1f}%)",
            zorder=3
        )

    # --- 美化细节 ---
    ax.set_xlabel('Date')
    ax.set_ylabel(r'Photon Flux [0.1-100 GeV] cm$^{-2}$ s$^{-1}$')
    title_str = (
        f"{source_name} | N_total={stats['N_total']}, N_eff={stats['N_eff']}, "
        f"N_ul={stats['N_ul']}, UL%={stats['ul_ratio'] * 100:.1f}% | "
        f"P_min={stats['P_min']}(m={stats['m']})"
    )
    ax.set_title(title_str)

    ax.grid(ls='--', linewidth=0.8, color='gray', alpha=0.6)

    # 日期格式化
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y.%m.%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate()

    ax.legend(loc='best', frameon=True)
    plt.tight_layout()

    # --- 保存或显示 ---
    if fig_mode == 'show':
        plt.show()
    else:
        os.makedirs(save_path, exist_ok=True)
        out_file = os.path.join(save_path, f'{source_name}_LightCurve.png')
        plt.savefig(out_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f'{source_name} - 光变曲线绘图完成，已保存到: {out_file}')

    return stats

# --- 使用示例 ---
# data, stats = get_lightcurve_data("path/to/file.csv", "config_name")
# plot_lightcurve(data, stats, "./output_plots", fig_mode='save')