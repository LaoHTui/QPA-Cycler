import os
from datetime import datetime
import pandas as pd
from plottable import ColumnDefinition, Table
import numpy as np
from matplotlib import pyplot as plt


def gen_final_statistics_table(save_path, source_name_list, jv_expected_period,
                               dcf_possible_period, lsp_possible_period, wwz_possibly_period,quantity=25):
    """
    生成并保存统计表格的图片。

    参数:
    - save_path: 保存图片的路径。
    - source_name_list: 源名称的列表。
    - jv_expected_period: 预期的Jurkevich周期数据。
    - dcf_possible_period: 可能的DCF周期数据。
    - lsp_possible_period: 可能的LSP周期数据。

    返回值:
    无
    """
    # 检查jv周期数据格式是否正确
    if not all(len(item) == 5 for item in jv_expected_period):
        raise ValueError("jv方法周期输入数量不正确.")

    # 设置每个部分包含的源数量和总部分数量
    quantity = quantity
    number_of_parts = int(np.ceil(len(source_name_list) / quantity))

    # 将源名称列表分割成多个部分
    source_name_parts = [source_name_list[i * quantity:(i + 1) * quantity] for i in range(number_of_parts)]
    # 将预期的jv周期数据分割成多个部分
    jv_parts = [jv_expected_period[i * quantity:(i + 1) * quantity] for i in range(number_of_parts)]
    # 将可能的DCF周期数据分割成多个部分
    dcf_parts = [dcf_possible_period[i * quantity:(i + 1) * quantity] for i in range(number_of_parts)]
    # 将可能的LSP周期数据分割成多个部分
    lsp_parts = [lsp_possible_period[i * quantity:(i + 1) * quantity] for i in range(number_of_parts)]
    # 将可能的WWZ周期数据分割成多个部分
    wwz_parts = [wwz_possibly_period[i * quantity:(i + 1) * quantity] for i in range(number_of_parts)]

    # print(len(source_name_parts),len(jv_parts), len(dcf_parts), len(lsp_parts), len(wwz_parts))

    # 指定保存路径
    save_path = save_path + '\\Result Plots'
    os.makedirs(save_path, exist_ok=True)

    # 遍历每一部分数据
    for i in range(number_of_parts):
        # 解压jv周期,lsp周期数据并重组
        P1, P2, P3, P4, jv_period = zip(*jv_parts[i])
        lsp_p, confidence_Level = zip(*lsp_parts[i])
        n = min(len(jv_period),len(lsp_p))   # 存在问题
        jV_Period = [f'{jv_period[w]} ({P1[w]} {P2[w]} {P3[w]} {P4[w]})' for w in range(n)]
        lsp_period = [f'{round(lsp_p[t],2)} ({confidence_Level[t]})' for t in range(n)]
        wwz_period = wwz_parts[i]

        # 获取对应的DCF周期数据和源名称
        dcf_period = dcf_parts[i]
        source_name = source_name_parts[i]


        # 创建数据字典
        data = {
            'Source Name': source_name,
            'JV Period': jV_Period,
            'DCF Period': dcf_period,
            'LSP Period': lsp_period,
            'WWZ Period': wwz_period
        }

        # 创建DataFrame
        df = pd.DataFrame(data)

        # 创建图形和轴对象
        fig, ax = plt.subplots(figsize=(10, 15))
        # 创建表格并设置属性
        tab = Table(df, column_definitions=[
            ColumnDefinition(name='Source Name', width=3),
            ColumnDefinition(name='JV Period', width=5.1),
            ColumnDefinition(name='DCF Period', width=1.8),
            ColumnDefinition(name='LSP Period', width=3.3),
            ColumnDefinition(name='WWZ Period', width=2)],
                    textprops={"ha": "left", "va": "center"})

        # 保存图片到指定路径
        # 获取格式化的当前时间字符串
        formatted_now = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        plt.savefig(f'{save_path}\\result_plot_{i + 1}_{formatted_now}.png', dpi=300, bbox_inches='tight')
        print(f'第{i + 1}个表格已保存到{save_path}\\result_plot_{i + 1}_{formatted_now}.png')

        plt.close()