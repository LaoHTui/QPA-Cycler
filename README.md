# QPA-Cycler
QPA Cycler, also known as Quasi Periodic Analysis Cycler, stands for Cycle Detection and Automation Process.   
QPA Cycler is a Python toolkit for periodic analysis of time-series data, with a core focus on period detection of non-uniform sampled time-series data (such as astronomical light curves). It integrates multiple classic period analysis algorithms and provides the full process capability of  
**"data reading → data preprocessing → mode selection → algorithm analysis → result visualization → calculation result document export"**.   
The purpose is to automate the cycle detection of non-uniform sampling time-series data and obtain reliable candidate sources.

> [!Note]
> 中文详细使用文档：[ZH](docs/README_zh.md)  
> Detailed explanation of algorithm principles:：[EN](docs/README_algorithms.md)|[ZH](docs/README_algorithms_ZH.md)


> [!Important]
> ## Functional characteristics
> 1. **Multi algorithm support**: Integrated classic cycle detection algorithms such as DCF, Jurkevich, Lomb Scargle, WWZ, harmonic analysis, etc;   
> 2. **High degree of freedom analysis**: Multiple/multi terminal reading is achieved by numbering the source files, and the parameters are intuitively adjustable;   
> 3. **Anti crash backup**: The program generates a backup of the analysis result data every minute, and the program can continue running from the interrupt by reading the status file;   
> 4. Visualization ability: One click generation of light curve and periodic analysis result charts;   
> 5. **Result Export**: Supports organizing analysis results into structured tables and exporting them as Word documents;   
> 6. **Flexible data processing**: Supports CSV/TXT format time-series data reading, with built-in analog data generation function;   
> 7. **Data Preprocessing**: Provides automatic filtering methods to improve cycle detection accuracy.   

## Quick Start  

### Environmental dependence
- Python ≥ 3.8
-Dependency libraries: numpy, pandas, matplotlib, Scipy, Python docx

### Install dependencies
Make sure to install the following Python libraries (recommended to use `pip` for installation):
```bash
pip install numpy pandas matplotlib scipy python-docx
```

## Basic usage process
* 1. Configure parameter config. json `, customize data path, data format, analysis algorithm parameters, output path, etc;
> [!Tip]
> For specific parameter instructions and usage, please refer to [ZH](README_comfig_zh.md) | [EN] (README_comfig_n. md)

* 2. Enter the name of the parameter file in the main program (if it is config. json, there is no need to change it)
Run the main program
```bash
python main.py
```
> [!Warning]
> The configuration parameter settings are very important, and it is important to understand their documentation before using them!

* 3. View the results:
The analysis results will be output in the path you have set in config. json, and a folder will be generated including
- Backup: It generates one file every minute and can replace the state file
- Light_Slot: If you choose to generate the light curve image, it will be generated inside
- Running_data: After the program ends, a copy of the parameter file will be made here (the parameter set for this run) and the state file will be placed together (including all method run results). For simulation data, its accuracy results will also be saved here
- The image of the method result (originally classified, but for easier docx reading)
* 4. [Optional] Organize the analysis results into a structured table and export it as a Word document
Run the save2docx program
```bash
python save2docx.py
```
The program will read the status and parameter files from the analysis results and generate a Word document in the results folder

> [!Note]
> The specific usage of save2docx can be found in[]()|[]()

## Example usage
### Here, we use the built-in simulation data generation function in this toolkit as an example

1. Set the simulated data output path (in this example, "S:\\example\\data")
And run gen_Sumulated_data.py
  ```bash
  python gen_sumulated_data.py
  ```
> [!Tip]
> For specific instructions, please refer to [] ()

![Light curve rendering](example/data/signal_examples.png)

2. Set the parameter file name in main, and set the source file entry and result output path for the parameter file
Setting in JSON structure
   ```bash
   "folder_path" : "S:\\example\\data",   
   "output_path" : "S:\\example\\result",
    ```
3. Set global parameter file (in config. json)
- Set the file reading range, here set "-1" (meaning full read)
- If the selection mode (auto/customize) is auto, adjust the corresponding parameters in the auto module; if it is customize, adjust the parameters in the corresponding module as well, and customize the selection algorithm
- Set state file name (default state)
- Set the file type for reading (csv/txt)
- Choose whether to rerun (when rerun is True, stop the program and restart it; when it is False, continue the calculation of the stopped source)
> [!Tip]
> For specific parameter specifications, please refer to[]()

4. Run main.by and wait for the result
  ```bash
python main.py
  ```

5. After running, the program synchronously displays the calculation results and the path for saving the results
  ```bash
状态文件已经储存在：S:\example\result\Running_Data\state
*************************全部源已经计算完毕,程序运行时间：1047.569 秒*************************
```
### Example cycle data results
![周期数据lsp](example/result/1_periodic_245.71days_LSP.png)   
![周期数据wwz](example/result/1_periodic_245.71days-245.8128_WWZ.png)

6. Run after selecting the simulated data section in save2docx
  ```bash
python save2docx.py
```
Obtain comprehensive results, including program computation time, parameter list, analysis structure of each source with bookmarks, and for simulated data, additional accuracy, calculation result labels for each source, etc

## For single method analysis, there are examples of applications in each method, and replacing the path adjustment parameters is sufficient

## Explanation
This project is a time-series data cycle analysis tool developed during the undergraduate stage. Due to personal knowledge and experience limitations, the program and algorithm may have shortcomings and omissions, and it is not the optimal implementation.   
Welcome interested friends to communicate, discuss, optimize and improve together.

Welcome to submit Pull Requests to improve this project. If you find any bugs or have new feature requests, you can open an Issue.

📧  Contact email: hczhang@my.swjtu.edu.cn
