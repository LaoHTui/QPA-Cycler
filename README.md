# QPA-Cycler
QPA Cycler, also known as Quasi Periodic Analysis Cycler, stands for Cycle Detection and Automation Process.   
QPA Cycler is a Python toolkit for periodic analysis of time-series data, with a core focus on period detection of non-uniform sampled time-series data (such as astronomical light curves). It integrates multiple classic period analysis algorithms and provides the full process capability of  
**"data reading → data preprocessing → mode selection → algorithm analysis → result visualization → calculation result document export"**.   
The purpose is to automate the cycle detection of non-uniform sampling time-series data and obtain reliable candidate sources.

> [!Note]
> 中文详细使用文档：[ZH](docs/README_zh.md)  
> Detailed explanation of algorithm principles:：[EN](algorithms/README.md)|[ZH]  


> [!Important]
> ## ##Functional characteristics
> 1. * * Multi algorithm support * *: Integrated classic cycle detection algorithms such as DCF, Jurkevich, Lomb Scargle, WWZ, harmonic analysis, etc;   
> 2. * * High degree of freedom analysis * *: Multiple/multi terminal reading is achieved by numbering the source files, and the parameters are intuitively adjustable;   
> 3. * * Anti crash backup * *: The program generates a backup of the analysis result data every minute, and the program can continue running from the interrupt by reading the status file;   
> 4. Visualization ability: One click generation of light curve and periodic analysis result charts;   
> 5. * * Result Export * *: Supports organizing analysis results into structured tables and exporting them as Word documents;   
> 6. * * Flexible data processing * *: Supports CSV/TXT format time-series data reading, with built-in analog data generation function;   
>7 . * * Data Preprocessing * *: Provides automatic filtering methods to improve cycle detection accuracy.   

## 快速开始
### 环境依赖
- Python ≥ 3.8
- 依赖库：numpy、pandas、matplotlib、scipy、python-docx

### 安装依赖
确保安装以下 Python 库（建议使用 `pip` 安装）：
```bash
pip install numpy pandas matplotlib scipy python-docx
```

## 基本使用流程
* 1.配置参数config.json`，自定义数据路径、数据格式、分析算法参数、输出路径等；
> [!Tip]
> 具体参数说明与用法详见[ZH](README_config_zh.md)|[EN](README_config_en.md)

* 2.在主程序输入参数文件名字（若为config.json则无需改变）   
  运行主程序
```bash
python main.py
```
> [!Warning]
> config参数设置很重要，使用时一定要先理解其说明文档！

* 3.查看结果：
分析结果会输出在config.json中你设置好的路径里，同时会生成文件夹包括
  - backup：里面每隔1分钟会生成一个，可以替代state文件
  - Light_Plot：如果你选择了生成光变曲线图像会生成在里面
  - Running_Data：程序结束后，会将参数文件复制一份在这里（为此次运行的参数集）与状态文件放在一起（包含所有方法运行结果），对于模拟数据，其准确度结果也保存在这里
  - 方法结果的图片（原本应该分类，不过为了docx读取更简便）
* 4。[可选]将分析结果整理为结构化表格并导出为 Word 文档
  运行save2docx程序
```bash
python save2docx.py
```
程序会读取分析结果中的状态文件与参数文件，并在结果文件夹中生成 Word 文档

> [!Note]
> save2docx用法具体见[]()|[]()

## 使用示例
### 这里用本工具集里内置模拟数据生成功能来举例子  

1. 设置模拟数据输出路径(本例为"S:\\example\\data")   
   并运行 gen_sumulated_data.py
  ```bash
  python gen_sumulated_data.py
  ```
> [!Tip]
> 具体说明详见[]()

![光变曲线效果图](example/data/signal_examples.png)

2. 在main中设置参数文件名字，并设置参数文件的源文件入口与结果输出路径
   json结构中设置
   ```bash
   "folder_path" : "S:\\example\\data",   
   "output_path" : "S:\\example\\result",
    ```
3. 设置全局参数文件(config.json中)
   - 设置文件读取范围，这里设置"-1"(意为全读取)
   - 选择模式(auto/customize) 若为auto，在auto模块中调节对应参数，若为customiz，同样在对应模块调节参数，并且自定义选择算法
   - 设置状态文件名(默认state)
   - 设置读取文件类型(csv/txt)
   - 选择是否重新运行(rerun为True时，停止程序后重新开始，为False时，接着停止的源继续计算) 
> [!Tip]
> 参数具体说明详见[]()

4. 运行main.py，等待结果
  ```bash
python main.py
  ```

5. 运行结束，程序同步显示计算结果与结果保存路径
  ```bash
状态文件已经储存在：S:\example\result\Running_Data\state
*************************全部源已经计算完毕,程序运行时间：1047.569 秒*************************
```
### 示例周期数据结果
![周期数据lsp](example/result/1_periodic_245.71days_LSP.png)   
![周期数据wwz](example/result/1_periodic_245.71days-245.8128_WWZ.png)

6. 在save2docx选择模拟数据板块后运行
  ```bash
python save2docx.py
```
得到综合结果，包括程序计算时间，参数列表，每个源的分析结构并配有书签，对于模拟数据则多出准确率，每个源计算结果标签等等

## 对于单方法分析，在每个方法中都有示例运用，替换路径调节参数即可 



