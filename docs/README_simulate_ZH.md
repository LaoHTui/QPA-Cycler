# gen_simulated_data.py使用说明

## 脚本功能

这是一个用于生成模拟时间序列数据的 Python 脚本，可生成随机、周期性、准周期性三种类型的正值时间序列，支持添加缺失值和测量误差，还可批量生成数据集。

> [!Tip]
> 模拟数据生成的原理详见算法文档[ZH](README_algorithms_ZH.md)

## 核心参数说明

### 主要函数 `generate_positive_signal` 关键参数：

|参数名|说明|默认值|
|---|---|---|
|length|数据点数量|1000|
|noise_level|噪声强度（0-1）|0.5|
|signal_type|信号类型：`random`/`periodic`/`quasi-periodic`|`random`|
|period_days|周期信号的周期（天），周期 / 准周期信号必须指定|None|
|missing_rate|缺失值比例（0-1）|0.0|
|time_step|时间步长（天）|7.0|
### 批量生成函数 `generate_and_save_dataset` 关键参数：

|参数名|说明|默认值|
|---|---|---|
|output_dir|输出目录|"simulated_data"|
|num_random_type|随机信号样本数|5|
|num_periodic_type|周期信号样本数|5|
|num_quasi_periodic_type|准周期信号样本数|5|
|period_min/period_max|周期信号的周期范围（天）|30.0/300.0|
## 快速使用示例

### 1. 直接运行脚本

```bash

python gen_simulated_data.py
```

会在`S:\\example\\data`目录生成 2 个随机、2 个周期、2 个准周期信号文件。

### 2. 作为模块导入使用

#### 生成单个周期信号

```python

import gen_simulated_data as gsd

# 生成周期为100天的信号
time, values, errors = gsd.generate_positive_signal(
    length=500,
    signal_type='periodic',
    period_days=100,
    noise_level=0.3,
    missing_rate=0.05
)
# 保存数据
gsd.save_to_txt("periodic_signal.txt", time, values, errors, "periodic", period_days=100)
```

#### 批量生成数据集

```python

import gen_simulated_data as gsd

gsd.generate_and_save_dataset(
    output_dir="./my_data",
    num_random_type=3,
    num_periodic_type=3,
    num_quasi_periodic_type=3,
    length=500,
    period_min=50,
    period_max=200
)
```

## 输出说明

生成的文本文件开头是参数说明，之后是`时间\t值\t误差`格式的数据，缺失值位置为空。
示例：

```Plain Text

# Signal Type: periodic
# Period: 100.000 days
# Time	Value	Error
54682.0000	2.123456	0.123456
54689.0000	1.876543	0.098765
54696.0000
```
