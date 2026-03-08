from matplotlib import pyplot as plt


def gen_lightcurve_plot(source_name, Julian_data, Photon_Flux, save_path):
    """
    生成并保存光变曲线图。

    参数:
    - source_name: 数据来源名称，用于图的标题和标签。
    - Julian_data: 朱利安日期数据，用于X轴。
    - Photon_Flux: 光子通量数据，用于Y轴。
    - save_path: 图像保存路径（不含文件名,但包含源的名字），用于指定保存位置。

    该函数创建一个图形，绘制光变曲线，并保存为PNG格式。
    """
    plt.figure(figsize=(16, 6))
    plt.scatter(Julian_data, Photon_Flux, s=2, label=f'{source_name}',color='darkblue')
    plt.plot(Julian_data, Photon_Flux, markersize=3, label=f'{source_name}',color='gray')
    plt.xlabel('Julian Date')
    plt.ylabel('Photon Flux[0.1-100 GeV]  cm^-2 s^-1')
    plt.title(f'{source_name}')
    plt.grid(ls='--', linewidth=1, color='gray')

    plt.savefig(f'{save_path}\\{source_name}_Light Curve.png', dpi=300)
    print(f'{source_name} - 光变曲线绘图完成, 保存在{save_path}\\{source_name}_Light Curve.png')
    plt.close()