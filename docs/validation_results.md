# Validation results / نتایج اعتبارسنجی

Synthetic charts with ground truth (Sample Data). Columns: MAE/RMSE in % of the true value range; coordinate error in % of the plot size; calibration error in % of the axis range. Reproduce with `python scripts/run_validation.py`.

| sample | detected_type | series_found | series_expected | mae_pct | rmse_pct | coord_error_pct | cal_error_pct | point_precision | point_recall | coverage | error_bar_mae_pct_of_value | band_mae_pct | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01_single_linear | line | 1 | 1 | 0.253 | 0.258 | 0.179 | 0.078 | 1.000 | 1.000 | 1.000 | - | - | 1.920 |
| 02_multi_curve | multi_series | 3 | 3 | 0.270 | 0.306 | 0.167 | 0.039 | 1.000 | 1.000 | 1.000 | - | - | 3.230 |
| 03_exponential | line | 1 | 1 | 0.269 | 0.273 | 0.198 | 0.055 | 1.000 | 1.000 | 1.000 | - | - | 2.510 |
| 04_markers | line | 1 | 1 | 0.573 | 0.716 | 0.354 | 0.055 | 1.000 | 1.000 | 1.000 | - | - | 2.060 |
| 05_error_bars | error_bar | 1 | 1 | 0.247 | 0.284 | 0.181 | 0.059 | 1.000 | 1.000 | 1.000 | 1.388 | - | 2.180 |
| 06_log_log | multi_series | 2 | 2 | 0.392 | 0.544 | 0.171 | 0.042 | 1.000 | 0.935 | 0.935 | - | - | 3.170 |
| 07_unconventional_axes | line | 1 | 1 | 0.280 | 0.351 | 0.135 | 0.079 | 1.000 | 1.000 | 1.000 | - | - | 2.080 |
| 08_multi_panel | line | 2 | 2 | 0.184 | 0.216 | 0.071 | 0.020 | 1.000 | 1.000 | 1.000 | - | - | 3.580 |
| 09_low_quality | line | 1 | 1 | - | - | - | - | - | - | - | - | - | 3.530 |
| 09_low_quality (manual axis edges) | line | 1 | 1 | 0.470 | 0.555 | 0.222 | - | 1.000 | 1.000 | 1.000 | - | - | 3.080 |
| 10_grid_lines | multi_series | 2 | 2 | 0.237 | 0.285 | 0.100 | 0.057 | 1.000 | 1.000 | 1.000 | - | - | 2.260 |
| 11_close_curves | multi_series | 3 | 3 | 0.711 | 0.778 | 0.341 | 0.057 | 1.000 | 1.000 | 1.000 | - | - | 3.630 |
| 12_dual_axis | dual_y | 2 | 2 | 0.171 | 0.179 | 0.113 | 0.020 | 1.000 | 0.975 | 0.975 | - | - | 3.610 |
| 13_force_four_curves | force_displacement | 4 | 4 | 0.263 | 0.412 | 0.111 | 0.064 | 1.000 | 0.991 | 0.991 | - | - | 4.260 |
| 14_bar_chart | bar | 1 | 0 | 0.041 | 0.052 | - | - | 1.000 | 1.000 | 1.000 | - | - | 4.250 |
| 15_pie_chart | pie | 4 | 0 | 0.191 | 0.199 | - | - | 1.000 | 1.000 | 1.000 | - | - | 0.490 |
| 16_confidence_band | line | 1 | 1 | 0.397 | 0.408 | 0.248 | 0.064 | 1.000 | 1.000 | 1.000 | - | 0.165 | 2.830 |
| 17_vector_chart (PDF vector paths) | multi_series | 2 | 2 | 0.101 | - | - | - | - | - | - | - | - | - |
