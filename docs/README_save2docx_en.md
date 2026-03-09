# save2docx Function Introduction

## 1. Script Overview

`save2docx.py` is a supporting report generation tool for the QPA-Cycler quasi-periodic analysis program. It is mainly used to generate the results of quasi-periodic analysis (including analysis results of real data and simulated data) into a standardized and beautiful Word format report document, realizing the integrated output of analysis data, visual charts, and parameter configurations, which is convenient for users to view and archive analysis results.

## 2. Core Functional Modules

### 2.1 State Management Module

This module is responsible for saving and loading the running state of the program, supporting state records related to breakpoint resumption:

1. **State Saving**: The `save_state` function saves the running state of the program (such as processing progress, processed files, analysis parameters, etc.) in JSON format to a specified file, ensuring that the previous running state can be restored after the program is interrupted.

2. **State Loading**: The `load_state` function loads the previously saved running state from the specified JSON file to obtain historical processing information and parameter configurations.

### 2.2 Image Processing Module

This module is used to process the visual charts generated during the analysis, realizing the organization and display of images:

1. **Placeholder Image Generation**: When the visual image of a certain algorithm is missing, the `create_placeholder_image` function generates a placeholder image with prompt text to ensure the integrity of the document layout.

2. **Image Grouping and Sorting**: The `get_sorted_images` function groups images by numeric prefixes and sorts the images in each group according to the specified algorithm order (LSP, DCF, JV, WWZ) to ensure the standardization of chart display.

3. **Image Layout Display**: Insert the sorted images into the Word document in a 2×2 grid layout, and add the corresponding algorithm name title to each image.

### 2.3 Word Document Generation Module

This module is the core module of the script, responsible for generating a complete Word report document, including the following functions:

1. **Page Layout Settings**

    - Custom Header: The program name is displayed on the left, and the current date and time are displayed on the right.

    - Custom Footer: Add centered page numbers to facilitate document browsing and referencing.

    - Page Margin Settings: Adjust the top, bottom, left, and right margins of the document to optimize the content display effect.

2. **Table Generation**

    - **Result Table**: Organize the period detection data obtained from the analysis into a three-line table format, displaying the detection period and error information of each data source.

    - **Parameter Table**: Display the parameter configurations used in the analysis (including auto-mode analysis parameters, simulation parameters, etc.) in a table format, which is convenient for users to view the configuration information of the analysis.

    - Custom Table Styles: Support styles such as borderless tables and three-line tables, and can set attributes such as table row height, column width, and cell margins.

3. **Content Organization**

    - Document Title Setting: Support custom report titles, which are displayed centered with font styles set.

    - Bookmark Addition: Add bookmarks to each image group to facilitate quick positioning of document content.

    - Detailed Description Addition: Add detailed description text of period detection to each group, including period values, errors, detection result descriptions, etc.

### 2.4 Data Processing Module

This module is responsible for organizing and processing analysis data, providing structured data for report generation:

1. **Period Data Reorganization**: The `reorganize_period_data_list` function reorganizes the original period detection data into structured data suitable for table display, converting the detection results of multiple periods into a multi-column table format.

2. **Label Generation**: The `get_labels` function extracts detailed information of period detection from the original data to generate readable description text, which is used to display the period detection details of each data source in the report.

3. **Simulated Data Accuracy Analysis**: For the analysis results of simulated data, functions such as `analyze_period_accuracy` are used to analyze the accuracy of period detection, generating a performance analysis report including statistical indicators such as detection rate, false positive rate, and accuracy rate.

## 3. Usage

### 3.1 Real Data Report Generation

Call the `save2docx` function to generate an analysis report for real data, and the following parameters need to be specified:

- `data_path`: The storage path of the analysis result data, including running state files and image files.

- `state_dict_filename`: The name of the running state file (without suffix).

- `json_params_filename`: The name of the parameter configuration file (without suffix).

- `title`: The title of the report, the default is "Report on the Results of the Quasi Periodic Analysis Program for Fermi Data".

- `docx_output_path`: The output path of the Word document, the default is the current directory.

- Other optional parameters: Image width, table row height, table cell width, etc., used to customize the document layout.

### 3.2 Simulated Data Report Generation

Call the `save2docx_sim` function to generate an analysis report for simulated data. This function will additionally generate a performance analysis report. The parameters are similar to those for real data report generation, and it will also add statistical content of detection accuracy of simulated data in the report, including file statistics, period detection results, performance indicators, and other information.

## 4. Output Document Structure

The generated Word report document includes the following content structure:

1. **Report Title**: The main title of the report displayed centered, which can be customized.

2. **Result Table**: Display the period detection results of all data sources in a three-line table format, including data source names, detection periods, period errors, and other information.

3. **Parameter Table**: Display the parameter configurations used in the analysis, including auto-mode analysis parameters, simulation parameters, etc.

4. **Image Groups**: Display visual charts of different algorithms by group. Each group displays the charts of the four algorithms LSP, DCF, JV, and WWZ in a 2×2 grid layout, and adds group titles and bookmarks.

5. **Detailed Descriptions**: Add detailed description text of period detection to each group, displaying the value, error, and detection result description of each period.

6. **Performance Analysis (Simulated Data Report Only)**: Display the detection performance statistics of simulated data, including indicators such as detection rate, false positive rate, and accuracy rate.

## 5. Dependencies

The following Python libraries need to be installed to run this script:

1. `python-docx`: Used to create and edit Word documents.

2. `pandas`: Used for data processing and table generation.

3. `Pillow (PIL)`: Used for image processing and placeholder image generation.

4. `json`: Used for reading and writing state files.

5. Built-in Python libraries such as `os`, `re`, and `datetime`: Used for file operations, regular matching, date processing, etc.
> （注：文档部分内容可能由 AI 生成）
