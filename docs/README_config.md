# Parameter Introduction

### `gen_light_plot`

- **Type**: Boolean

- **Default value**: `false`

- **Description**: Controls whether to generate a lightweight light curve plot. When set to `true`, a simplified visualization chart will be generated; when set to `false`, no chart will be generated.

### `gen_result_table` (Old version, not recommended)

- **Type**: Object

- **Description**: Controls the generation configuration of the result table, including the following sub-parameters:

    - `plot`

        - **Type**: Boolean

        - **Default value**: `false`

        - **Description**: Controls whether to output the result table. `true` means generate, `false` means not generate. And if it is true, the calculation program will not run, and the program will end directly after generating the table.

    - `quantity`

        - **Type**: Integer

        - **Default value**: `15`

        - **Description**: Sets the number of data entries displayed per page in the result table, that is, a maximum of 15 result data will be displayed.

## `global` Global Configuration

### `mode`

- **Type**: String

- **Default value**: `"auto"`

- **Description**: Sets the running mode. The optional values are `"auto"` (auto mode) or `"customize"` (custom mode). In auto mode, the parameters in the `auto` configuration item will be used; in custom mode, the parameters in the `customize` configuration item will be used.

> [!Tip]
> The auto mode uses the PVP algorithm proposed by me (see [Algorithm Description Document](README_algorithms_ZH.md)), and the effect varies from person to person.
> 
> 

### `file_numbers`

- **Type**: Integer

- **Default value**: `-1`

- **Description**: Sets the number of files to process. `-1` means process all eligible files; when set to a positive integer, only the files with the specified numbers will be processed. For example, "1-30" means process files numbered 1 to 30 (inclusive), and "1,5,9" means process the three files numbered 1, 5, and 9.

### `rerun`

- **Type**: Boolean

- **Default value**: `false`

- **Description**: Controls whether to re-run the task. `true` means ignore the previous running state and re-execute all processing steps; `false` means continue execution based on the previous state or skip completed steps.

### `folder_path`

- **Type**: String

- **Default value**: `"S:\\example\\data"`

- **Description**: Specifies the storage path of the input data files. The program will read the data files to be processed from this path.

### `output_path`

- **Type**: String

- **Default value**: `"S:\\example\\result"`

- **Description**: Specifies the output path of the processing results. The program will save all generated result files to this path.

### `state_filename`

- **Type**: String

- **Default value**: `"state"`

- **Description**: Specifies the name of the running state file. The program will use this file to record the running state of the task, which is used for functions such as breakpoint resumption.

### `file_type`

- **Type**: String

- **Default value**: `"txt"`

- **Description**: Specifies the type of input data files. Currently, text data files in `"txt"`/`"csv"` format are supported.

> [!Note]
> See  for the output data format.
> 
> 

## `customize` Custom Configuration

### Algorithm Switch Parameters

These parameters control whether to enable the corresponding algorithm functions:

- `DCF`

    - **Type**: Boolean

    - **Default value**: `false`

    - **Description**: Controls whether to enable the DCF (Discrete Correlation Function) algorithm.

- `DCF_Plot`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to generate a visualization chart for the DCF algorithm.

- `Jurkevich`

    - **Type**: Boolean

    - **Default value**: `false`

    - **Description**: Controls whether to enable the Jurkevich algorithm.

- `JV_Plot`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to generate a visualization chart for the Jurkevich algorithm.

- `LSP`

    - **Type**: Boolean

    - **Default value**: `false`

    - **Description**: Controls whether to enable the LSP (Lomb-Scargle Periodogram) algorithm.

- `LSP_Plot`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to generate a visualization chart for the LSP algorithm.

- `WWZ`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to enable the WWZ (Weighted Wavelet Z-transform) algorithm.

- `WWZ_Plot`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to generate a visualization chart for the WWZ algorithm.

### `jv_params` Jurkevich Algorithm Parameters

- `test_periods_start`

    - **Type**: Integer

    - **Default value**: `100`

    - **Description**: Sets the start value of the test period for the Jurkevich algorithm.

- `test_periods_end`

    - **Type**: Integer

    - **Default value**: `3000`

    - **Description**: Sets the end value of the test period for the Jurkevich algorithm.

- `test_periods_step`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: Sets the step size of the test period for the Jurkevich algorithm, that is, the value by which the period increases each time.

- `m_bins`

    - **Type**: Integer

    - **Default value**: `2`

    - **Description**: Sets the number of bins in the Jurkevich algorithm.

### `dcf_params` DCF Algorithm Parameters

- `delta_tau`

    - **Type**: Integer

    - **Default value**: `30`

    - **Description**: Sets the time delay increment in the DCF algorithm.

- `c`

    - **Type**: Integer

    - **Default value**: `40`

    - **Description**: Sets the smoothing parameter of the DCF algorithm.

- `max_tau`

    - **Type**: Integer

    - **Default value**: `3000`

    - **Description**: Sets the maximum time delay value of the DCF algorithm.

- `normalize`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Controls whether to normalize the results of the DCF algorithm.

- `height`

    - **Type**: Float

    - **Default value**: `0.20`

    - **Description**: Sets the height threshold of the peak in the peak-finding algorithm for the DCF algorithm results.

- `distance`

    - **Type**: Integer

    - **Default value**: `5`

    - **Description**: Sets the minimum distance threshold between peaks in the peak-finding algorithm for the DCF algorithm results.

### `lsp_params` LSP Algorithm Parameters

- `M`

    - **Type**: Integer

    - **Default value**: `10000`

    - **Description**: Sets the number of Monte Carlo simulations in the LSP algorithm.

- `n_jobs`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: To reduce computation time, sets the number of parallel tasks used when running the LSP algorithm, which can be determined according to your own situation.

- `multiple_freq_max`

    - **Type**: Integer

    - **Default value**: `100`

    - **Description**: Sets the maximum value for multi-frequency detection in the LSP algorithm.

- `divide_freq_step`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: Sets the number of frequency step divisions in the LSP algorithm.

- `MC`

    - **Type**: String

    - **Default value**: `"true"`

    - **Description**: Controls whether to use the Monte Carlo method for significance testing in the LSP algorithm. `"true"` means enable, `"false"` means disable.

### `wwz_params` WWZ Algorithm Parameters

- `c`

    - **Type**: Float

    - **Default value**: `0.0125`

    - **Description**: Sets the wavelet coefficient of the WWZ algorithm.

- `freq_min`

    - **Type**: Float

    - **Default value**: `0.0002`

    - **Description**: Sets the minimum detection frequency of the WWZ algorithm.

- `freq_max`

    - **Type**: Float

    - **Default value**: `0.004`

    - **Description**: Sets the maximum detection frequency of the WWZ algorithm.

- `freq_step`

    - **Type**: Float

    - **Default value**: `0.0001`

    - **Description**: Sets the frequency step size of the WWZ algorithm.

- `tau_number`

    - **Type**: Integer

    - **Default value**: `200`

    - **Description**: Sets the number of time delay sampling points in the WWZ algorithm.

- `z_height`

    - **Type**: Integer

    - **Default value**: `20000`

    - **Description**: Sets the Z-value height threshold of the WWZ algorithm.

## `auto` Auto Mode Configuration

### `lsp_params` Auto Mode LSP Algorithm Parameters

- `M`

    - **Type**: Integer

    - **Default value**: `10000`

    - **Description**: The number of Monte Carlo simulations for the LSP algorithm in auto mode.

- `n_jobs`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: The number of parallel tasks used when running the LSP algorithm in auto mode.

- `multiple_freq_max`

    - **Type**: Integer

    - **Default value**: `100`

    - **Description**: The maximum value for multi-frequency detection in the LSP algorithm in auto mode.

- `divide_freq_step`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: The number of frequency step divisions in the LSP algorithm in auto mode.

### `lsp_filter` Auto Mode LSP Algorithm Filter Parameters

- `height`

    - **Type**: Float

    - **Default value**: `0.1`

    - **Description**: The peak height threshold of the LSP algorithm results in auto mode.

- `min_prominence_rate`

    - **Type**: Float

    - **Default value**: `0.5`

    - **Description**: The minimum prominence rate threshold of the LSP algorithm results in auto mode.

- `self_harmonic`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to filter self-harmonics in the LSP algorithm results in auto mode.

- `reverse`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to reverse the filtering logic of the LSP algorithm in auto mode. That is, whether to retain higher-order or lower-order harmonics, which determines whether to treat the "large period" or "small period" as the fundamental wave first. When set to true, the largest period will be marked as the "fundamental wave" first. Subsequently, smaller, proportional periods will be marked as "harmonics" and eliminated.

- `n_harmonics`

    - **Type**: Integer

    - **Default value**: `2`

    - **Description**: The number of harmonics retained in the LSP algorithm in auto mode.

- `sigma_threshold`

    - **Type**: Float

    - **Default value**: `2.0`

    - **Description**: The sigma threshold for harmonic determination in auto mode, used for significance judgment.

- `peak_width_factor`

    - **Type**: Float

    - **Default value**: `0.1`

    - **Description**: The peak width factor of the LSP algorithm results in auto mode.

- `snr_threshold`

    - **Type**: Float

    - **Default value**: `5.0`

    - **Description**: The signal-to-noise ratio threshold of the LSP algorithm in auto mode.

- `fap_threshold`

    - **Type**: Float

    - **Default value**: `0.001`

    - **Description**: The False Alarm Probability (FAP) threshold of the LSP algorithm in auto mode.

### `dcf_params` Auto Mode DCF Algorithm Parameters

- `delta_tau`

    - **Type**: Integer

    - **Default value**: `30`

    - **Description**: The time delay increment of the DCF algorithm in auto mode.

- `c`

    - **Type**: Integer

    - **Default value**: `40`

    - **Description**: The smoothing parameter of the DCF algorithm in auto mode.

- `max_tau`

    - **Type**: Integer

    - **Default value**: `3000`

    - **Description**: The maximum time delay value of the DCF algorithm in auto mode.

- `normalize`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to normalize the results of the DCF algorithm in auto mode.

### `dcf_filter` Auto Mode DCF Algorithm Filter Parameters

- `height`

    - **Type**: Float

    - **Default value**: `0.15`

    - **Description**: The peak height threshold of the DCF algorithm results in auto mode.

- `prominence`

    - **Type**: Float

    - **Default value**: `0.3`

    - **Description**: The prominence threshold of the DCF algorithm results in auto mode.

- `snr_threshold`

    - **Type**: Float

    - **Default value**: `3.0`

    - **Description**: The signal-to-noise ratio threshold of the DCF algorithm in auto mode.

- `distance_rate`

    - **Type**: Integer

    - **Default value**: `4`

    - **Description**: The distance rate threshold between peaks in the DCF algorithm results in auto mode.

- `self_harmonic`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to filter self-harmonics in the DCF algorithm results in auto mode.

- `sigma_threshold`

    - **Type**: Float

    - **Default value**: `2.0`

    - **Description**: The sigma threshold of the DCF algorithm in auto mode, used for significance judgment.

- `reverse`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Same as `reverse` in lsp.

### `jv_params` Auto Mode Jurkevich Algorithm Parameters

- `test_periods_start`

    - **Type**: Integer

    - **Default value**: `100`

    - **Description**: The start value of the test period for the Jurkevich algorithm in auto mode.

- `test_periods_end`

    - **Type**: Integer

    - **Default value**: `3000`

    - **Description**: The end value of the test period for the Jurkevich algorithm in auto mode.

- `test_periods_step`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: The step size of the test period for the Jurkevich algorithm in auto mode.

- `m_bins`

    - **Type**: Integer

    - **Default value**: `2`

    - **Description**: The number of bins in the Jurkevich algorithm in auto mode.

### `jv_filter` Auto Mode Jurkevich Algorithm Filter Parameters

- `max_serise`

    - **Type**: Integer

    - **Default value**: `3000`

    - **Description**: The maximum sequence length processed by the Jurkevich algorithm in auto mode.

- `v2_threshold`

    - **Type**: Float

    - **Default value**: `0.2`

    - **Description**: The V2 value threshold of the Jurkevich algorithm in auto mode.

- `min_peak_distance`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: The minimum distance threshold between peaks in the Jurkevich algorithm results in auto mode.

- `prominence`

    - **Type**: Float

    - **Default value**: `0.1`

    - **Description**: The prominence threshold of the Jurkevich algorithm results in auto mode.

- `self_harmonic`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to filter self-harmonics in the Jurkevich algorithm results in auto mode.

- `sigma_threshold`

    - **Type**: Float

    - **Default value**: `2.0`

    - **Description**: The sigma threshold of the Jurkevich algorithm in auto mode, used for significance judgment.

- `reverse`

    - **Type**: Boolean

    - **Default value**: `true`

    - **Description**: Whether to reverse the filtering logic of the Jurkevich algorithm in auto mode, same as above.

### `wwz_params` Auto Mode WWZ Algorithm Parameters

- `c`

    - **Type**: Float

    - **Default value**: `0.0125`

    - **Description**: The wavelet coefficient of the WWZ algorithm in auto mode.

- `scan_range`

    - **Type**: Float

    - **Default value**: `0.8`

    - **Description**: The scan range ratio of the WWZ algorithm in auto mode.

- `freq_step`

    - **Type**: Float

    - **Default value**: `0.0001`

    - **Description**: The frequency step size of the WWZ algorithm in auto mode.

- `tau_number`

    - **Type**: Integer

    - **Default value**: `400`

    - **Description**: The number of time delay sampling points in the WWZ algorithm in auto mode.

- `z_height`

    - **Type**: Integer

    - **Default value**: `20000`

    - **Description**: The Z-value height threshold of the WWZ algorithm in auto mode.

### `wwz_filter` Auto Mode WWZ Algorithm Filter Parameters

- `min_size`

    - **Type**: Integer

    - **Default value**: `10`

    - **Description**: The minimum size of the valid region in the WWZ algorithm results in auto mode.

- `confidence`

    - **Type**: Float

    - **Default value**: `0.99`

    - **Description**: The confidence threshold of the WWZ algorithm results in auto mode.

- `peak_mode`

    - **Type**: String

    - **Default value**: `"peak"`

    - **Description**: The peak detection mode of the WWZ algorithm in auto mode. The optional value is `"peak"` (peak mode).
