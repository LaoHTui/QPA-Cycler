# QPA-Cycler
QPA-Cycler的全程是Quasi-Periodic Analysis Cycler（准周期分析）,Cycler表示循环检测与自动化流程。
QPA-Cycler是一套面向时序数据周期分析的 Python 工具集，核心聚焦非均匀采样时序数据（如天文领域光变曲线）的周期检测，整合了多种经典周期分析算法，提供「数据读取→数据预处理→模式选择→算法分析→结果可视化→计算结果文档导出」全流程能力。

## 扩展文档
- 📖 中文详细使用文档：[中文文档](docs/README_zh.md)
- 📝 算法原理详解：[算法文档](algorithms/README.md)
- 💡 示例代码演示：[示例说明](examples/README.md)

## 功能特性
- 多算法支持：集成 DCF、Jurkevich、Lomb-Scargle、WWZ、谐波分析等经典周期检测算法；
- 可视化能力：一键生成光变曲线、周期分析结果图表；
- 结果导出：支持将分析结果整理为结构化表格并导出为 Word 文档；
- 灵活数据处理：支持 CSV/TXT 格式时序数据读取，内置模拟数据生成功能；
- 数据预处理：提供自动滤波方法，提升周期检测精度。


## 快速开始
### 环境依赖
确保安装以下 Python 库（建议使用 `pip` 安装）：
```bash
pip install numpy pandas matplotlib scipy python-docx
```
##基本使用流程
*1.配置参数config.json`，自定义数据路径、分析算法参数、输出路径等；
*2.运行主程序：
```bash
python main.py
```
*3.查看结果：
可视化图表会自动保存至 temp_images/ 目录；
结构化分析结果表格及 Word 文档会输出至指定路径。

> [!Tip]
> How to use BabelDOC in Zotero
> 
> 1. Immersive Translate Pro members can use the [immersive-translate/zotero-immersivetranslate](https://github.com/immersive-translate/zotero-immersivetranslate) plugin
> 2. PDFMathTranslate self-deployed users can use the [guaguastandup/zotero-pdf2zh](https://github.com/guaguastandup/zotero-pdf2zh) plugin

### Supported Language
[Supported Language](https://xxx.com/supported-language)
