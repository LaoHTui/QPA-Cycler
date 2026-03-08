import os
import numpy as np
import pandas as pd


def get_csv_data(file_map,state):
    # 读取CSV文件
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

    state.setdefault('processed_files', []).append(filename)

    return source_name, julian_dates, photon_fluxes, photon_fluxes_err