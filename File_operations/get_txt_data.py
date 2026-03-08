import os
import numpy as np


def  get_txt_data(file_map,state):
    x, y, z = [], [], []
    # 读取txt文件
    # 打开文件
    with open(file_map, 'r') as file:
        # 跳过第一行（无论是否为注释）
        next(file)
        for line in file:
            line = line.strip()  # 去掉行首尾的空格和换行符
            # 新增：跳过以#开头的注释行和空行
            if not line or line.startswith('#'):
                continue
            # 确保行不为空且不是注释
            if line:
                columns = line.split()  # 按空格或制表符分割行
                if len(columns) >= 3:  # 确保行中有至少三列数据
                    x.append(float(columns[0]))  # 提取第一列并转换为浮点数
                    y.append(float(columns[1]))  # 提取第二列并转换为浮点数
                    z.append(float(columns[2]))  # 提取第三列并转换为浮点数

    # 将列表转换为 NumPy 数组
    julian_dates_s = np.array(x)
    # julian_dates_o = np.round(julian_dates_s / 86400, 4)  # 转化为day
    julian_dates_o = julian_dates_s
    photon_fluxes_o = np.array(y)
    photon_fluxes_err = np.array(z)

    # 提取源名称 以'_'来分隔，若原数据不同，则可能会出现问题
    filename = os.path.basename(file_map)
    source_name = filename.split("_")[0] + "_" + filename.split("_")[1] + "_" + filename.split("_")[2]

    # 去掉错误数据如nan
    mask = ~np.isnan(julian_dates_o) & ~np.isnan(photon_fluxes_o)
    julian_dates = julian_dates_o[mask]
    photon_fluxes = photon_fluxes_o[mask]
    photon_fluxes_err = photon_fluxes_err[mask]

    state.setdefault('processed_files', []).append(filename)

    # print(julian_dates)
    # print(photon_fluxes)

    return source_name, julian_dates, photon_fluxes, photon_fluxes_err