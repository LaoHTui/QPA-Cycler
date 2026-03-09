# Data Processing Program Documentation

## Document Overview

This document describes two data processing programs, `get_csv_data.py` and `get_txt_data.py`, including program functions, input file format requirements, return value descriptions, and usage notes.

---

## `get_csv_data.py` Program Description

### Function

This program is used to read and process CSV format data files, extract Julian Dates, Photon Fluxes, and Photon Fluxes Error data, while handling abnormal data and extracting source names.

### Input File Format Requirements

1. **File Type**: Standard CSV format file with the suffix `.csv`

2. **Header Requirement**: The first line of the file must be the header line, and the program will read the first line as column names

3. **Data Column Requirements**:

    - The 2nd column (index 1) must be Julian Dates data

    - The 5th column (index 4) must be Photon Fluxes data. If this column is of string type, the program will filter out rows containing the `<` symbol

    - The 6th column (index 5) must be Photon Fluxes Error data

4. **Null Value Representation**: Null values in the file must be represented by `-`, which the program will recognize as missing values

5. **File Name Requirement**: The file name must be in the format `[SourceName1]_[SourceName2]_[SourceName3]_xxx.csv`. The program will split the first three parts of the file name by underscores as the source name

> [!Tip]
> You can adjust the index in the program to make the program match your program!

### Return Values

The program returns four values:

1. `source_name`: The extracted source name

2. `julian_dates`: The processed Julian Dates data array

3. `photon_fluxes`: The processed Photon Fluxes data array

4. `photon_fluxes_err`: The processed Photon Fluxes Error data array

---

## `get_txt_data.py` Program Description

### Function

This program is used to read and process TXT format data files, extract Julian Dates, Photon Fluxes, and Photon Fluxes Error data, while handling comment lines, blank lines, and abnormal data and extracting source names.

### Input File Format Requirements

1. **File Type**: Plain text format file with the suffix `.txt`

2. **Line Processing Rules**:

    - The first line will be skipped directly (regardless of whether it is a comment line)

    - Lines starting with `#` are treated as comment lines and will be skipped

    - Blank lines will be skipped

3. **Data Column Requirements**:

    - Each line must contain at least three columns of data, separated by spaces or tabs

    - The 1st column must be Julian Dates data (must be a value convertible to a float)

    - The 2nd column must be Photon Fluxes data (must be a value convertible to a float)

    - The 3rd column must be Photon Fluxes Error data (must be a value convertible to a float)

4. **File Name Requirement**: The file name must be in the format `[SourceName1]_[SourceName2]_[SourceName3]_xxx.txt`. The program will split the first three parts of the file name by underscores as the source name

### Return Values

The program returns four values:

1. `source_name`: The extracted source name

2. `julian_dates`: The processed Julian Dates data array

3. `photon_fluxes`: The processed Photon Fluxes data array

4. `photon_fluxes_err`: The processed Photon Fluxes Error data array

---

## Usage Notes

1. Both programs will automatically filter out abnormal data containing `nan`

2. The program will record the processed file names in the `processed_files` list of the passed `state` dictionary

3. If the CSV file is empty, the program will return an empty DataFrame and prompt that the file is empty and has been skipped

4. The file name format must meet the requirements, otherwise it may cause errors in source name extraction

5. Ensure that the column order and data type of the input file meet the requirements, otherwise it may cause program runtime errors
