# gen_simulated_data.py  Guide 

## Script Overview

`gen_simulated_data.py` is a Python script for generating simulated time series data, with main functions including:

- Generate positive-valued simulated time series, supporting missing values and Fermi measurement errors

- Support three signal types: random signal, periodic signal, quasi-periodic signal

- Batch generate and save datasets

- Provide period detection accuracy analysis function

> [!Tip]
> The principle of simulating data generation can be found in the algorithm document [ZH](README.algorithms_ZH.md)

## Dependencies

The following Python libraries need to be installed:

- numpy

- matplotlib

- os

- re

- json (for analysis functions)

You can install the dependencies with the following command:

```bash

pip install numpy matplotlib
```

## Main Function Descriptions

### 1. generate_positive_signal

Generate positive-valued simulated time series, supporting missing values and Fermi measurement errors

#### Parameter Description

|Parameter Name|Type|Default Value|Description|
|---|---|---|---|
|length|int|1000|Number of data points|
|noise_level|float|0.5|Noise intensity (0-1)|
|signal_type|str|'random'|Signal type: 'periodic', 'quasi-periodic', 'random'|
|period_days|float|None|Period length of periodic signal (in days), must be specified for periodic and quasi-periodic signals|
|amplitude|float|1.0|Main signal amplitude|
|freq_variation|float|0.1|Frequency variation intensity of quasi-periodic signal|
|missing_rate|float|0.0|Missing value ratio (0-1)|
|baseline_error|float|0.1|Baseline measurement error|
|time_start|float|54682.0|Start time (Fermi MJD time format)|
|time_step|float|7.0|Time step|
|exposure|float|1e10|Exposure parameter|
|sys_error|float|0.05|Systematic error ratio|
#### Return Values

- time: Time array (may contain NaN)

- values: Data array (contains missing values NaN, all values > 0)

- errors: Error array (corresponding to each data point)

### 2. save_to_txt

Save time series to text file in the specified format

#### Parameter Description

|Parameter Name|Type|Description|
|---|---|---|
|filename|str|Output file name|
|time|np.array|Time array|
|values|np.array|Data array|
|errors|np.array|Error array|
|signal_type|str|Signal type label|
|params|dict|Parameter dictionary (optional)|
|period_days|float|Period length in days (optional)|
### 3. parse_period_from_filename

Parse period information from file name

#### Parameter Description

|Parameter Name|Type|Description|
|---|---|---|
|filename|str|File name|
#### Return Value

- float: Parsed period length, returns None if parsing fails

### 4. generate_and_save_dataset

Batch generate and save three types of time series to text files

#### Parameter Description

|Parameter Name|Type|Default Value|Description|
|---|---|---|---|
|output_dir|str|"simulated_data"|Output directory|
|num_random_type|int|5|Number of random signal samples|
|num_periodic_type|int|5|Number of periodic signal samples|
|num_quasi_periodic_type|int|5|Number of quasi-periodic signal samples|
|length|int|500|Length of each sample|
|amplitude|float|1.5|Signal amplitude|
|freq_variation|float|0.2|Frequency variation intensity|
|missing_rate|float|0.1|Missing value ratio|
|baseline_error|float|0.1|Baseline error|
|time_start|float|54682.0|Start time (MJD format)|
|time_step|float|7|Time step|
|period_min|float|30.0|Minimum period length (in days)|
|period_max|float|300.0|Maximum period length (in days)|
### 5. extract_true_periods

Extract all true period values from source string

#### Parameter Description

|Parameter Name|Type|Description|
|---|---|---|
|source_str|str|String containing period information|
#### Return Value

- list: List of extracted period values, returns empty list for random signals

### 6. is_period_detected

Check if the true period is detected (within error range)

#### Parameter Description

|Parameter Name|Type|Default Value|Description|
|---|---|---|---|
|true_period|float|-|True period value|
|detected_periods|list|-|List of detected periods|
|detected_errors|list|-|List of detected period errors|
|tolerance|float|1.0|Error tolerance coefficient|
#### Return Values

- bool: Whether the period is detected

- int: Index of the matched detected period (returns -1 if no match)

### 7. analyze_period_accuracy

Analyze period detection accuracy, including random signals and non-period detection situations

#### Parameter Description

|Parameter Name|Type|Default Value|Description|
|---|---|---|---|
|json_data|dict|-|JSON data containing detection results|
|tolerance|float|1.0|Error tolerance coefficient|
#### Return Value

- dict: Contains detailed analysis results and multiple accuracy indicators

## Usage Methods

### 1. Run the script directly

Running the script directly will generate a sample dataset:

```bash

python gen_simulated_data.py
```

The script will generate 2 random signals, 2 periodic signals, and 2 quasi-periodic signal text files in the specified directory (default `S:\\example\\data`).

### 2. Import as a module

You can import the script as a module and use its functions:

```python

import gen_simulated_data as gsd

# Generate a single time series
time, values, errors = gsd.generate_positive_signal(
    length=1000,
    noise_level=0.3,
    signal_type='periodic',
    period_days=100,
    amplitude=1.5,
    missing_rate=0.05
)

# Save data
gsd.save_to_txt('output.txt', time, values, errors, 'periodic', period_days=100)

# Batch generate dataset
gsd.generate_and_save_dataset(
    output_dir='./simulated_data',
    num_random_type=5,
    num_periodic_type=5,
    num_quasi_periodic_type=5,
    length=500,
    noise_level=0.3,
    amplitude=1.5,
    missing_rate=0.01,
    time_step=30,
    period_min=130.0,
    period_max=1500.0
)
```

## Examples

### Generate a single periodic signal

```python

import gen_simulated_data as gsd
import matplotlib.pyplot as plt

# Generate periodic signal
time, values, errors = gsd.generate_positive_signal(
    length=1000,
    noise_level=0.2,
    signal_type='periodic',
    period_days=100,
    amplitude=2.0,
    missing_rate=0.05
)

# Plot the signal
plt.figure(figsize=(12, 6))
plt.errorbar(time, values, yerr=errors, fmt='o', markersize=3, alpha=0.7)
plt.xlabel('Time (MJD)')
plt.ylabel('Flux')
plt.title('Simulated Periodic Signal')
plt.grid(True, alpha=0.3)
plt.show()
```

### Analyze period detection results

```python

import json
import gen_simulated_data as gsd

# Load detection result JSON file
with open('detection_results.json', 'r') as f:
    json_data = json.load(f)

# Analyze accuracy
analysis_result = gsd.analyze_period_accuracy(json_data, tolerance=1.0)

# Print analysis results
print(f"Total files: {analysis_result['total_files']}")
print(f"Periodic signal files: {analysis_result['periodic_files']}")
print(f"Random signal files: {analysis_result['random_files']}")
print(f"Strict accuracy: {analysis_result['strict_accuracy']:.2%}")
print(f"Relaxed accuracy: {analysis_result['relaxed_accuracy']:.2%}")
print(f"Random signal accuracy: {analysis_result['random_accuracy']:.2%}")
```

## Output Description

### Text File Format

The generated text file contains the following content:

1. File header information: Contains signal type, period information (if any), and parameter information

2. Data rows: Each row contains time, value, and error, with empty positions for missing values

Example file header:

```Plain

# Signal Type: periodic
# Period: 150.000 days
# length: 500
# amplitude: 1.5
# baseline_error: 0.1
# time_start: 54682.0
# noise_level: 0.24
# missing_rate: 0.08
# Time	Value	Error
54682.0000	2.345678	0.123456
54689.0000	1.876543	0.098765
54696.0000		0.112233
...
```

### Analysis Result Format

The analysis result returned by the `analyze_period_accuracy` function contains the following main indicators:

- total_files: Total number of files

- periodic_files: Number of periodic signal files

- random_files: Number of random signal files

- strict_accuracy: Strict accuracy (all true periods are detected and no false positives)

- relaxed_accuracy: Relaxed accuracy (at least one true period is detected)

- random_accuracy: Random signal accuracy (no period detected)

- false_positive_rate: False positive rate

- detection_rate: Detection rate
