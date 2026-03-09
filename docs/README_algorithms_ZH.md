# QPA-Cycler

## Automated Multi-method Quasi-Periodicity Detection Pipeline

QPA-Cycler 是一个多方法交叉自动化检测准周期候选源的管道，集成了多种周期检测算法，通过多方法交叉验证来提高准周期信号检测的准确性。

## 算法原理介绍

### Lomb-Scargle Periodogram (LSP)

LSP 是一种针对非均匀采样时序数据的频谱分析方法，能有效检测隐藏的周期性信号。其通过最小二乘法拟合不同频率的正弦波，计算其功率谱。

#### 统计显著性检验

- **信噪比 (Signal-to-Noise Ratio - SNR)**

- **假警报概率 (False Alarm Probability - FAP)**：使用蒙特卡洛模拟方法，基于幂律噪声的生成模型                        $P(f) \propto f^{-\alpha}$                       。

### 离散相关系数 (DCF)

DCF 用于测量两个时间序列在不同时间滞后下的相关性，特别适用于不规则采样的数据。

#### 核心公式

未装箱的离散相关函数值：
 $DCF_{ij}=\frac{(x(t_i)-\bar{x})(y(t_j)-\bar{y})}{\sigma_x \sigma_y}$ 
对有噪数据：
 $DCF_{ij}=\frac{(x(t_i)-\bar{x})(y(t_j)-\bar{y})}{\sqrt{(\sigma_x^2-\sigma_{x,e}^2)(\sigma_y^2-\sigma_{y,e}^2)}}$ 

### Jurkevich 方法 (JV)

一种基于数据均方差期望原理的周期提取算法。对于非均匀采样时间序列                        $x(t_i)$                                               $i=1,2,3...N$                       ，其样本平均值和样本方差分别为：
试验周期为                        $T_{test}$                       ，分组索引公式
数据被划分为                        $M$                        组，则第                        $k$                        组的样本平均值和样本方差分别为：
 $M$                        组数据的总方差并进行归一化。

### 加权小波 Z - 变换 (WWZ)

WWZ 是一种强大的时频分析方法，特别适用于分析非平稳（频率和振幅随时间变化）的时间序列信号。

#### 核心定义

- 权重函数（Morlet-Grossman 小波核）：                      $W(t,\tau,f,s)=e^{-\pi t^2 (t-\tau)^2}$ 

- 投影向量                        $\vec{V}_i$                       ：                      $\vec{V}_i = [1, \cos(2\pi f (t_i-\tau)), \sin(2\pi f (t_i-\tau))]$ 

- 系数由                       $\vec{\beta} = (\mathbf{V}^T \mathbf{W} \mathbf{V})^{-1} \mathbf{V}^T \mathbf{W} \mathbf{x}$                       得出，其中                        $\mathbf{V}_i$                        为矩阵                        $\mathbf{V}$                       （                       $N$                       ，3）的第                        $i$                        行，                       $\mathbf{W}(i,i)$                        为权重矩阵，                       $\mathbf{x}(1,i)$                        为时间序列矩阵。

#### Z - 统计量

 $Z(f,\tau)=\frac{(N-3)}{2} \frac{\chi_r^2 - \chi_{min}^2}{\chi_{min}^2}$ 
其中                        $N=2df$ 

#### 影响锥 (Cone of Influence - COI)

 $\tau_{COI} \in [t_{min}+\frac{1}{2f\Delta t}, t_{max}-\frac{1}{2f\Delta t}]$                      ，COI 之外的                        $Z$                        值应被忽略。

#### 脊线追踪 (Ridge Tracking)

 $R(\tau)=\argmax_f(Z(\tau,f))$ 
脊线连接条件：                       $\frac{|R(\tau)-R(\tau-1)|}{R(\tau)} < \epsilon$ 

#### 漂移判定

简单线性回归模型：                      $f(t) = \alpha_1 t + \alpha_0 + \epsilon$ 
其中，                       $\alpha_1$                        是漂移率（单位：Hz/day 或 Hz/s），                       $\alpha_0$                        是截距，其符号决定了漂移方向，                       $\epsilon$                        是误差项。
置信区间                       $CI_{\alpha_1} = [\alpha_1 - t_{\alpha/2, n-2} \cdot SE(\alpha_1), \alpha_1 + t_{\alpha/2, n-2} \cdot SE(\alpha_1)]$ 
其中，n 是样本量（数据点个数），α 为显著性水平，SE 估计标准误，区间外为漂移，内为稳定。

### 谐波判定方法

从一组带误差的候选周期中，自动识别并筛选出基波，同时标记出哪些是它们的谐波。

#### 计算周期比值及其不确定性 (误差传播)

 $r=\frac{T_i}{T_j}$ 
 $\sigma_r = r \cdot \sqrt{(\frac{\sigma_{T_i}}{T_i})^2 + (\frac{\sigma_{T_j}}{T_j})^2}$ 
判定条件为：
 $|r - r_{harmonic}| \leq \sigma_{harmonic}$ 
其中                        $r_{harmonic}$                        为可能整数比，                       $\sigma_{harmonic}$                        为显著性阈值。

### FWHM 全高半宽

 $FWHM = T_{high} - T_{low}$ 
边界插值公式：
 $T_{bound} = T_k + (T_{k+1}-T_k) \cdot \frac{y_{peak}-y_{bound}}{y_{k+1}-y_k}$ 
测量不确定度估计：                      $\sigma_{FWHM} = \Delta T \cdot \sqrt{2}$ 

## 周期性验证管道 (PVP)

### 多方法一致性决策

通过多种周期检测方法的结果进行交叉验证，只有当多种方法都检测到相同的周期信号时，才判定为存在周期性信号，提高检测的准确性。

### 有序多方法合成策略

按照不同方法的检测性能和适用场景，有序地组合多种方法，先使用计算量较小、检测速度快的方法进行初步筛选，再使用更复杂、更准确的方法进行验证，提高检测效率和准确性。

### 周期性验证管道流程

1. 输入非均匀采样时间序列数据

2. 分别使用 LSP、DCF、JV、WWZ 等方法进行周期检测

3. 对各方法的检测结果进行一致性验证

4. 使用谐波判定方法筛选基波和谐波

5. 计算 FWHM 全高半宽，确定周期的精度

6. 输出最终的周期性检测结果

## 模拟数据结果

通过生成三种已知周期值的模拟数据来测试 PVP 方法的准确性，核心生成公式：
 $x(t) = \frac{1}{S + \Delta S} \cdot \sin(2\pi \frac{(t-t_0)}{T_{true}})$ 
 $\sigma_x = \sqrt{(\frac{\sigma_S}{S})^2 + \sigma_{sys}^2}$ 
其中，                       $S$                        为通量值，                       $C$                        为光子计数，                       $E$                        为曝光量，                       $\sigma_{sys}$                        为系统误差，                       $k$                        为系统误差系数                       $\sigma_{sys}=k \cdot S$                      。

### 模拟数据类型

1. **周期性信号**：固定周期的正弦信号

2. **准周期性信号**：频率随时间变化的正弦啁啾信号

3. **随机信号**：无周期性的随机噪声信号

### 检测结果

|Source Name|Signal Type|Real Period|Detected Period|Detected Period Error|Judgment|
|---|---|---|---|---|---|
|1_periodic1|periodic_signal|1185.45 days|1187.413|14.122|True|
|2_periodic4|periodic_signal|469.48 days|469.899|6.832|True|
|3_periodic4|periodic_signal|472.54 days|471.82|0.903|True|
|4_periodic8|periodic_signal|829.12 days|829.214|13.312|True|
|5_periodic8|periodic_signal|881.48 days|879.202|8.511|True|
|6_quasiperiodic1|quasiperiodic_signal|1091.89 days|-|-|False|
|7_quasiperiodic1|quasiperiodic_signal|147.61 days|-|-|False|
|8_quasiperiodic3|quasiperiodic_signal|361.35 days|-|-|False|
|9_quasiperiodic3|quasiperiodic_signal|365.21 days|-|-|False|
|10_quasiperiodic7|quasiperiodic_signal|763.84 days|-|-|False|
|11_random001.txt|random_signal|-|-|-|True|
|12_random002.txt|random_signal|-|-|-|True|
|13_random003.txt|random_signal|-|-|-|True|
|14_random004.txt|random_signal|-|-|-|True|
|15_random005.txt|random_signal|-|-|-|True|
### 性能指标

- 检测率：50.00%

- 误检率：16.67%

- 周期性信号的准确率：40.00%

- 随机信号的准确率：100.00%

- 总体准确率：60.00%

## Fermi LAT 数据运行结果

|Source Name|Detected Period1|Detected Period2|Detected Period3|Detected Period4|Detected Period5|Detected Period6|
|---|---|---|---|---|---|---|
|1_4FGL_J0001.5+2113|-|-|-|-|-|-|
|2_4FGL_J0004.3+4614|-|-|-|-|-|-|
|3_4FGL_J0004.4-4737|274.0385±2.1254|325.7143±3.0026|2230.0±138.948|-|-|-|
|4_4FGL_J0005.9+3824|2556.763±1038.598|-|-|-|-|-|
|5_4FGL_J0010.6+2043|-|-|-|-|-|-|
|6_4FGL_J0010.6-3025|-|-|-|-|-|-|
|7_4FGL_J0011.4+0057|-|-|-|-|-|-|
|8_4FGL_J0016.2-0016|-|-|-|-|-|-|
|9_4FGL_J0017.5-0514|-|-|-|-|-|-|
|10_4FGL_J0019.6+7327|-|-|-|-|-|-|
|11_4FGL_J0023.7+4457|-|-|-|-|-|-|
|12_4FGL_J0023.7-6820|-|-|-|-|-|-|
|13_4FGL_J0024.7+0349|-|-|-|-|-|-|
|14_4FGL_J0028.4+2001|1779.977±72.733|-|-|-|-|-|
|15_4FGL_J0030.3-4224|-|-|-|-|-|-|
|16_4FGL_J0038.2-2459|269.1589±2.7924|-|-|-|-|-|
## 参数设置

### 模拟数据参数

|Parameter Name|Parameter Value|
|---|---|
|length|500|
|noise_level|0.3|
|amplitude|1.5|
|freq_variation|0.2|
|missing_rate|0.1|
|baseline_error|0.1|
|time_start|54682.0|
|time_step|30|
|period_min|130.0|
|period_max|1500.0|
|exposure|10000000000.0|
|sys_error|0.05|
### LSP 方法参数

|Parameter Name|Parameter Value|
|---|---|
|M|1000|
|n_jobs|10|
|multiple_freq_max|100|
|divide_freq_step|10|
### DCF 方法参数

|Parameter Name|Parameter Value|
|---|---|
|height|0.1|
|min_prominence_rate|0.5|
|self_harmonic|True|
|reverse|True|
|n_harmonics|2|
|sigma_threshold|2.0|
|peak_width_factor|0.1|
|snr_threshold|5.0|
|fap_threshold|0.001|
### JV 方法参数

|Parameter Name|Parameter Value|
|---|---|
|delta_tau|30|
|c|40|
|max_tau|3000|
|normalize|True|
### WWZ 方法参数

|Parameter Name|Parameter Value|
|---|---|
|height|0.15|
|prominence|0.3|
|snr_threshold|3.0|
|distance_rate|4|
|self_harmonic|True|
|sigma_threshold|2.0|
|reverse|False|
### 其他参数

|Parameter Name|Parameter Value|
|---|---|
|test_periods_start|100|
|test_periods_end|3000|
|test_periods_step|10|
|m_bins|2|
|Parameter Name|Parameter Value|
|---|---|
|max_serise|3000|
|v2_threshold|0.2|
|min_peak_distance|10|
|prominence|0.1|
|self_harmonic|True|
|sigma_threshold|2.0|
|reverse|True|
|Parameter Name|Parameter Value|
|---|---|
|c|0.0125|
|scan_range|1.8|
|freq_step|0.0001|
|tau_number|600|
|z_height|20000|
|Parameter Name|Parameter Value|
|---|---|
|min_size|60|
|confidence|0.99|
|peak_mode|peak|
## 使用方法

1. 克隆仓库：

```bash

git clone https://github.com/yourusername/QPA-Cycler.git
cd QPA-Cycler
```

1. 安装依赖：

```bash

pip3 install -r requirements.txt
```

1. 运行管道：

```bash

python3 qpacycler.py --input data/your_data.txt --output results/
```

## 贡献

欢迎提交 Pull Request 来改进这个项目。如果你发现了 bug 或者有新的功能需求，可以提交 Issue。

## 许可证

本项目采用 MIT 许可证，详情请见 LICENSE 文件。
> （注：文档部分内容可能由 AI 生成）
