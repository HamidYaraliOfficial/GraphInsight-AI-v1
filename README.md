<div align="center">

<img src="assets/logo/logo.svg" width="110" alt="GraphInsight AI logo"/>

# GraphInsight AI

### Turn chart images into numbers, equations, statistics and scientific reports — fully offline

**Developer: Hamid Yarali (حمید یارعلی)**

[English](README.md) · [فارسی](README_FA.md)

</div>

---

## Contents

1. [What is GraphInsight AI?](#1-what-is-graphinsight-ai)
2. [Visual tour (real output of the engine)](#2-visual-tour-real-output-of-the-engine)
3. [Features](#3-features)
4. [Quick start](#4-quick-start)
5. [User guide](#5-user-guide)
6. [Supported chart types](#6-supported-chart-types)
7. [Outputs: Excel, Word, PDF, CSV, JSON, images, ZIP](#7-outputs)
8. [Accuracy: validation results](#8-accuracy-validation-results)
9. [Sample charts and the *Force (N)* test chart](#9-sample-charts-and-the-force-n-test-chart)
10. [Architecture and folder structure](#10-architecture-and-folder-structure)
11. [Using the engine from Python](#11-using-the-engine-from-python)
12. [Troubleshooting](#12-troubleshooting)
13. [Scientific and technical limitations](#13-scientific-and-technical-limitations)
14. [Tests and testing status](#14-tests-and-testing-status)
15. [Privacy and security](#15-privacy-and-security)
16. [License and credits](#16-license-and-credits)

---

## 1. What is GraphInsight AI?

GraphInsight AI is a **local, offline** application (Python + Streamlit) that converts the *picture of a chart* — a scanned figure, a screenshot, a figure inside a PDF — back into **numerical data** that can be used in research:

* tables of X / Y points for every curve, with pixel coordinates, **confidence** and **provenance** of each point,
* approximate **mathematical models** (equations in text, LaTeX, Python and Excel form) with R², RMSE, MAE, AIC, BIC, cross-validation and parameter uncertainty,
* **derivatives, integrals, areas between curves, extrema, inflection points, intersections**,
* **statistics** and comparisons between curves,
* a **scientific report** in Word / PDF (Persian *or* English, RTL supported), a multi-sheet **Excel** workbook with real tables, formulas and charts, CSV, JSON, PNG/SVG and a ZIP bundle.

Design principles (from the project brief):

* **Accuracy and scientific validity come first.** Anything that cannot be recovered is reported as *unknown*; nothing is invented — no axis title, unit, error type or equation is guessed.
* **Provenance is explicit.** Every point is labelled `marker` (a real marker in the image), `reconstructed` (from the curve centre-line), `interpolated` (gap fill), `vector_vertex` (exact vertex of a vector PDF path) or `manual`. Reconstructed points are never presented as original measurements.
* **Everything is local.** No cloud service, no API key, no telemetry.
* **Humans stay in the loop.** Every automatic step (plot area, calibration, colours, points) can be corrected manually with undo / redo.

<div align="center">
<img src="docs/images/architecture.png" width="900" alt="architecture"/>
</div>

---

## 2. Visual tour (real output of the engine)

> All pictures in this README were produced by the real engine from the synthetic charts in `sample_charts/` (labelled **Sample Data**). They are not mock-ups. The scripts that create them are `scripts/make_readme_assets.py` and `scripts/make_sample_outputs.py`.

### 2.1 From a picture to data — the pipeline

The *Force (N)* sample with four curves (`PAM`, `PAMCZ3%`, `PAMCZ1%`, `PA`): original → detected plot area and ticks → colour clusters → sub-pixel centre-lines → reconstruction → analysis results. The horizontal axis has **no title** in this sample, so the software records it as *unknown* instead of inventing one.

<div align="center">
<img src="docs/images/pipeline_stages.png" width="100%" alt="pipeline stages"/>
</div>

### 2.2 Extraction overlay, reconstruction, model fit, derivatives, comparison

<table>
<tr>
<td width="50%"><img src="docs/images/force_overlay.png" alt="overlay"/><br/><sub><b>Extraction overlay</b> — green: plot area, pink: ticks, dots: extracted points</sub></td>
<td width="50%"><img src="docs/images/force_reconstruction.png" alt="reconstruction"/><br/><sub><b>Chart reconstructed from the extracted data</b></sub></td>
</tr>
<tr>
<td><img src="docs/images/force_fit_PAM.png" alt="fit"/><br/><sub><b>Model comparison + residuals</b> (an approximate model, not the true law)</sub></td>
<td><img src="docs/images/force_derivative_PAM.png" alt="derivative"/><br/><sub><b>Derivatives</b> (noise-adaptive smoothing spline) and inflection points</sub></td>
</tr>
<tr>
<td colspan="2" align="center"><img src="docs/images/force_comparison.png" width="60%" alt="comparison"/><br/><sub><b>Shape comparison</b> of the four curves (min–max normalised); dotted lines = crossings</sub></td>
</tr>
</table>

### 2.3 Special cases

<table>
<tr>
<td width="50%"><img src="docs/images/multi_panel.png" alt="multi panel"/><br/><sub><b>Multi-panel figure</b> — each panel is calibrated and digitised independently</sub></td>
<td width="50%"><img src="docs/images/error_bars.png" alt="error bars"/><br/><sub><b>Markers and error bars</b> (error type is reported as <i>unspecified</i>)</sub></td>
</tr>
<tr>
<td><img src="docs/images/log_log_reconstruction.png" alt="log"/><br/><sub><b>Log–log axes</b> (superscript tick labels such as 10³ are read correctly)</sub></td>
<td><img src="docs/images/dual_axis_reconstruction.png" alt="dual axis"/><br/><sub><b>Dual Y-axis</b> — series assigned to the axis whose colour they share</sub></td>
</tr>
<tr>
<td><img src="docs/images/band_reconstruction.png" alt="band"/><br/><sub><b>Shaded confidence band</b> around a curve</sub></td>
<td><img src="docs/images/sample_charts_grid.png" alt="samples"/><br/><sub>Some of the 17 synthetic test charts</sub></td>
</tr>
</table>

### 2.4 Generated reports

<table>
<tr>
<td width="25%"><img src="docs/images/word_fa_1.png" alt="Word FA 1"/><br/><sub>Word (Persian, RTL): title page</sub></td>
<td width="25%"><img src="docs/images/word_fa_2.png" alt="Word FA 2"/><br/><sub>image information + overlay</sub></td>
<td width="25%"><img src="docs/images/word_fa_3.png" alt="Word FA 3"/><br/><sub>equations, parameters, metrics</sub></td>
<td width="25%"><img src="docs/images/word_fa_4.png" alt="Word FA 4"/><br/><sub>interpretation, quality, limits</sub></td>
</tr>
<tr>
<td><img src="docs/images/word_en_1.png" alt="Word EN 1"/><br/><sub>Word (English): title page</sub></td>
<td><img src="docs/images/word_en_2.png" alt="Word EN 2"/></td>
<td><img src="docs/images/word_en_3.png" alt="Word EN 3"/></td>
<td><img src="docs/images/word_en_4.png" alt="Word EN 4"/></td>
</tr>
<tr>
<td><img src="docs/images/excel_1.png" alt="Excel 1"/><br/><sub>Excel: <code>Overview</code> sheet with native chart</sub></td>
<td><img src="docs/images/excel_2.png" alt="Excel 2"/><br/><sub>Excel: next sheet</sub></td>
<td><img src="docs/images/pdf_en_1.png" alt="PDF 1"/><br/><sub>PDF report</sub></td>
<td><img src="docs/images/pdf_en_2.png" alt="PDF 2"/></td>
</tr>
</table>

> **Dashboard screenshots.** Streamlit could not be installed in the environment where this release was assembled (no network), so no real screenshots of the browser UI are included — and none were faked. After installing, run `streamlit run app.py`, then `pip install playwright && playwright install chromium && python scripts/capture_screenshots.py` to save screenshots of all ten pages into `docs/images/ui_*.png`.

---

## 3. Features

| # | Capability | Where |
|---|---|---|
| 1 | Chart-type detection with transparent scores and manual override | `core/chart_detector.py` |
| 2 | Plot-area, axis-line and tick detection; multi-panel figures | `core/plot_area_detector.py`, `core/axis_detector.py` |
| 3 | OCR of tick labels (incl. minus sign, thousands separators, 10ⁿ superscripts), axis titles, units, chart title, legend | `core/ocr_engine.py` |
| 4 | Axis calibration: linear, log10 / log2 / ln, reversed, non-uniform (piecewise), categorical, date-time; ≥3 ticks cross-checked, RANSAC outlier rejection | `core/coordinate_transform.py`, `core/axis_calibration.py` |
| 5 | Colour-cluster series separation, grid-line removal, legend swatch removal and legend ↔ series matching | `core/curve_detector.py`, `core/legend_detector.py` |
| 6 | Sub-pixel centre-line tracing (dynamic programming through crossings), skeleton tracing for non-function curves, step curves | `core/curve_digitizer.py` |
| 7 | Two extraction modes: **main points** (real markers) and **dense digitisation** with curvature-adaptive sampling (`adaptive`, `uniform_x`, `uniform_arc`; user-set number of points) | `core/marker_detector.py`, `core/curve_digitizer.py` |
| 8 | Error bars (±, caps), shaded bands, dual Y axes, bars / histograms / stacked / grouped bars, pie / donut charts | `core/error_bar_detector.py`, `core/bar_extractor.py` |
| 9 | Vector PDF: exact vertices of the plotted paths | `core/pdf_processor.py` |
| 10 | Confidence for every point, series and calibration + a **Quality Assessment** (resolution, calibration, OCR, curve separation, coverage) | `core/confidence_estimator.py` |
| 11 | 20 model families (linear … polynomial, exponential, logarithmic, power, logistic, sigmoid, Gaussian, sinusoidal, rational, saturation, Michaelis–Menten, piecewise-linear, smoothing spline, **custom expression**) with R², adj. R², RMSE, MAE, MSE, MAPE, SSE, AIC, BIC, AICc, k-fold CV error, residual analysis and parameter confidence intervals; Occam-style model selection | `analysis/curve_fitting.py` |
| 12 | Derivatives (1st/2nd), max/min slope, inflection points, curvature, integrals (trapezoid, Simpson, cumulative), area between curves, extrema, plateaus, monotonicity, convexity, zero crossings, intersections | `analysis/*.py` |
| 13 | Descriptive statistics, Pearson / Spearman / Kendall, regression, comparison and ranking of curves — with an honest **significance flag** (dense points are *not* independent observations) | `analysis/statistical_analysis.py`, `analysis/correlation_analysis.py` |
| 14 | Data-driven scientific description (Persian / English) and explicit limitations | `analysis/scientific_interpretation.py` |
| 15 | Streamlit dashboard: 10 pages, RTL Persian UI, dark / light mode, progress bars, undo / redo, project history | `dashboard/`, `app.py` |
| 16 | Local persistence in SQLite + project folders; project copy / delete / ZIP export / restore on another computer | `storage/` |
| 17 | Export: Word, Excel, PDF, CSV, JSON, PNG, SVG, TXT, ZIP | `exporters/` |

---

## 4. Quick start

### 4.1 Requirements

* **Python 3.8 or newer** (3.10 – 3.12 recommended). `pip` automatically installs the newest package versions that support *your* Python — on Python 3.8 / 3.9 these are the older NumPy 1.x / SciPy / pandas 2.0 releases; the code contains compatibility helpers for both generations (see §14 for what was and was not verified on old Python versions).
* **Tesseract OCR** (recommended — reads the axis numbers automatically; without it you type the axis values yourself).
  * Windows: <https://github.com/UB-Mannheim/tesseract/wiki> (installer; the default path is detected automatically, otherwise set `TESSERACT_CMD` in `.env`).
  * Ubuntu / Debian: `sudo apt install tesseract-ocr`   ·   macOS: `brew install tesseract`
  * Optional Persian OCR pack: `tesseract-ocr-fas`, then set *OCR language* to `eng+fas` in the settings.
* Internet **only for the first installation** of the Python packages. Afterwards the program works completely offline.
* Optional: **LibreOffice** (only used to build a Persian PDF when `arabic-reshaper` / `python-bidi` are unavailable) and the **Vazirmatn** font in `assets/fonts/`.

### 4.2 Windows

```text
1. Unzip GraphInsight-AI.zip
2. (optional) double-click  install.bat   – creates .venv and installs the packages
3. double-click  run.bat
4. The browser opens at  http://127.0.0.1:8501
```

`run.bat` checks Python (≥ 3.8), creates `.venv` if needed, installs the packages **only when `requirements.txt` changed** (a SHA-256 of the file is stored in `.venv`), warns if Tesseract is missing, prints the local address and **keeps the window open if anything fails** so you can read the message. The scripts work from any folder (paths come from the location of the script).

### 4.3 Linux and macOS

```bash
unzip GraphInsight-AI.zip && cd GraphInsight-AI
chmod +x run.sh install.sh      # only if the executable bit was lost
./install.sh                    # optional: create .venv, install packages  (--force to reinstall, --check to only verify)
./run.sh                        # start the dashboard -> http://127.0.0.1:8501
```

### 4.4 Manual installation (any OS)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

`requirements.txt` contains compatible version ranges; `requirements-lock.txt` lists the exact versions with which the engine and the 70 automated tests were executed.

---

## 5. User guide

### 5.1 Uploading images — *New Analysis*

1. Open **New Analysis**. Drag & drop one or more files (PNG, JPG/JPEG, TIFF, BMP, WEBP, SVG, PDF). Files are validated by extension, magic bytes and size (≤ 60 MB) and are **never executed**.
2. For a **PDF** choose the page; vector PDFs give exact data (`vector_vertex`), scanned PDFs are analysed as images.
3. Open **Extraction settings** if needed (OCR language, denoise, de-skew, colour tolerance, number of points, sampling, curve mode, forced chart type, axis scales).
4. Press **Start automatic analysis**. A progress bar shows the stage; to cancel click any other button. The result page lists warnings (low resolution, missing OCR, unreadable ticks, …).
5. The tab **Try a sample** runs the synthetic charts (always labelled *Sample Data*).

### 5.2 Calibration — *Image Processing*

The page shows the original and the processed image, the detected **plot area** (green) and the **ticks** (pink) on a zoomable / pannable plot.

* **Plot area** – if the box is wrong, type its corners (and an optional rotation) and press *Apply and re-extract*.
* **Calibration** – the table lists every detected tick (pixel position and OCR value). Edit / add rows (≥ 2, **≥ 3 recommended** so the fit can be verified), choose the **scale** (`auto`, `linear`, `log10`, `log2`, `ln`, `piecewise` for non-uniform axes, `categorical`, `datetime`) and re-extract. Alternatively give the values at the plot-area edges. The *calibration confidence* and fit error (px) are displayed.
* **Axis titles and units** – type them if OCR could not read them; otherwise they stay **unknown** in all reports.

### 5.3 Extracting and correcting points — *Chart Digitization*

* Choose a series; its points are drawn on the image. Rename it, change its colour, or **re-extract it from a colour** you pick (for same-coloured / ambiguous curves).
* Settings: number of points, sampling (`adaptive` puts more points where the curve bends, `uniform_x`, `uniform_arc`), curvature weight, colour tolerance, dense mode. *Re-extract with these settings* rebuilds the series and keeps the calibration.
* **Table editing**: change X/Y, add or delete rows. Edited / added points get the status `manual` and confidence 1.0; pixel positions are recomputed from the calibration.
* **Undo / Redo** are in the sidebar; every edit is a snapshot and is stored in the project log.

### 5.4 Data Explorer

Interactive table of all points with search, status / series filters, column selection, sorting, **Copy** (tab-separated) and **CSV / Excel** download.

### 5.5 Mathematical Analysis

Select the model families (or type a **custom model**, e.g. `a*x**2 + b*sin(c*x)` — parsed safely with SymPy, no code is executed), the fit source (`markers` / `dense` / `auto`) and the derivative method, then press *Run analysis*. For every series you get the model table (R², adj. R², RMSE, MAE, AIC, BIC, CV-RMSE), an overlay of any models you pick, **equations as LaTeX / text / Python / Excel**, parameters with standard errors and 95 % CI, residual plot, derivative curves, the definite integral on a range you choose, critical points, convex / concave segments and plateaus.

> **Important:** a fitted function is an *approximate description* of the digitised points. With a limited number of points several model families fit equally well; the program never claims to have found the "true" law. The selection rule is: *the simplest model whose RMSE is within 15 % (or 0.25 % of the y-range) of the best*; ties are broken by BIC.

### 5.6 Statistical Analysis, Visualization, Reports, History

* **Statistical Analysis** – descriptive statistics, histogram, correlation (Pearson / Spearman / Kendall), regression, series comparison, ranking, intersections, uncertainty estimates and the Quality Assessment chart. p-values for dense reconstructed points are flagged as **not meaningful**.
* **Visualization** – rebuild the original chart or make a new one from the data: colours, titles, axes, legend, ranges, log scales; download PNG / SVG / PDF.
* **Reports** – choose the report language (Persian / English) and the formats, press *Generate*, download files individually or as one ZIP.
* **Project History** – all projects are stored in `data/projects/<id>/`. Open, copy, delete, export a project as ZIP, or restore it on another computer.

### 5.7 Excel output (`*_data.xlsx`)

Sheets: `Overview`, `Original_Metadata`, `Axis_Calibration`, `Extracted_Data`, `Series_1 … Series_N` (one per curve — created dynamically), `Curve_Fitting`, `Model_Parameters`, `Statistical_Analysis`, `Derivatives`, `Integrals`, `Intersections`, `Error_Analysis`, `Confidence`, `Processing_Log`.
Real Excel *tables* with filters, frozen header rows, native Excel charts, and **live formulas** in the series sheets (finite-difference slope, cumulative trapezoid integral, the best-fit curve computed from the parameter cells of `Model_Parameters`, residuals). The sample workbook was recalculated with LibreOffice: **0 formula errors in 3 276 formulas**.

### 5.8 Word output (`*_report_fa.docx` / `*_report_en.docx`)

Title page, image information, chart information (axes, units, scales, ranges, legend), original image, extraction overlay, reconstructed chart, numerical tables (complete point tables with status and confidence), equations (rendered, LaTeX, Python, Excel), parameters with confidence intervals, fit metrics, model ranking, residual / derivative / comparison figures, integrals, critical points, statistics, a data-driven scientific description, the Quality Assessment, the list of data sources (direct extraction / mathematical computation / statistical fit / interpolation / manual input) and the limitations. Persian reports are right-to-left.

---

## 6. Supported chart types

The registry (`models/chart_types.py`) contains **74** chart types. *Automatic classification* is rule-based and conservative (it recognises line, scatter, multi-series, dual-axis, error-bar, step, area, bar / grouped / stacked / histogram, pie / donut, multi-panel and a few engineering types from axis titles); every type can also be **chosen manually**. Support levels:

* ✅ **full** – a dedicated extraction strategy exists and was validated;
* 🟡 **partial** – generic extraction works but needs manual review;
* ⚪ **recognised only** – the type is listed / selectable, but automatic numeric extraction is **not** implemented (3-D plots, heat-maps, box / violin, Sankey, treemap, network, Gantt, candlestick, radar, ternary, …). For such figures use the generic curve extraction or digitise points manually.

**2D charts**

| Chart type | Support | Strategy |
|---|---|---|
| Line Chart | ✅ full | `curve` |
| Scatter Plot | ✅ full | `curve` |
| Smooth Curve | ✅ full | `curve` |
| Bar Chart | ✅ full | `bars` |
| Horizontal Bar Chart | ✅ full | `bars` |
| Grouped Bar Chart | ✅ full | `bars` |
| Stacked Bar Chart | ✅ full | `bars` |
| Area Chart | ✅ full | `curve` |
| Stacked Area Chart | 🟡 partial | `curve` |
| Step Chart | ✅ full | `step` |
| Error Bar Chart | ✅ full | `curve` |
| Scientific Curve Plot | ✅ full | `curve` |
| Time Series | ✅ full | `curve` |
| Multiple Series Plot | ✅ full | `curve` |
| Dual Y-Axis Chart | ✅ full | `curve` |
| Multiple Axes Chart | 🟡 partial | `curve` |
| Piecewise Curve | ✅ full | `curve` |
| Parametric Plot | 🟡 partial | `parametric` |

**Statistical charts**

| Chart type | Support | Strategy |
|---|---|---|
| Histogram | ✅ full | `bars` |
| Box Plot | ⚪ recognised only | `none` |
| Violin Plot | ⚪ recognised only | `none` |
| Density Plot | ✅ full | `curve` |
| KDE Plot | ✅ full | `curve` |
| ECDF | ✅ full | `step` |
| Q-Q Plot | ✅ full | `curve` |
| Regression Plot | ✅ full | `curve` |
| Residual Plot | ✅ full | `curve` |
| ROC Curve | ✅ full | `curve` |
| Precision-Recall Curve | ✅ full | `curve` |
| Confusion Matrix | ⚪ recognised only | `none` |
| Forest Plot | ⚪ recognised only | `none` |
| Survival Curve | ✅ full | `step` |
| Kaplan-Meier Plot | ✅ full | `step` |
| Bland-Altman Plot | ✅ full | `curve` |

**Scientific & engineering**

| Chart type | Support | Strategy |
|---|---|---|
| Stress-Strain Curve | ✅ full | `curve` |
| Force-Displacement Curve | ✅ full | `curve` |
| Force-Elongation Curve | ✅ full | `curve` |
| Load-Deformation Curve | ✅ full | `curve` |
| Tensile Test Graph | ✅ full | `curve` |
| Compression Test Graph | ✅ full | `curve` |
| Rheological Curves | ✅ full | `curve` |
| Frequency Response | ✅ full | `curve` |
| Bode Plot | ✅ full | `curve` |
| Nyquist Plot | 🟡 partial | `parametric` |
| Polar Plot | ⚪ recognised only | `none` |
| Impedance Plot | 🟡 partial | `parametric` |
| Spectral Curves | ✅ full | `curve` |
| Absorption / Transmission Spectra | ✅ full | `curve` |
| Sensor Measurements | ✅ full | `curve` |
| Experimental Curves | ✅ full | `curve` |
| Calibration Curves | ✅ full | `curve` |
| Material Characterization Graphs | ✅ full | `curve` |

**Multi-dimensional**

| Chart type | Support | Strategy |
|---|---|---|
| 3D Scatter Plot | ⚪ recognised only | `none` |
| 3D Line Plot | ⚪ recognised only | `none` |
| 3D Surface Plot | ⚪ recognised only | `none` |
| Mesh Plot | ⚪ recognised only | `none` |
| Contour Plot | ⚪ recognised only | `none` |
| Heatmap | ⚪ recognised only | `none` |
| Ternary Plot | ⚪ recognised only | `none` |
| Radar Chart | ⚪ recognised only | `none` |
| Parallel Coordinates | ⚪ recognised only | `none` |
| Bubble Chart | 🟡 partial | `curve` |

**Combined & special**

| Chart type | Support | Strategy |
|---|---|---|
| Pie Chart | ✅ full | `pie` |
| Donut Chart | ✅ full | `pie` |
| Treemap | ⚪ recognised only | `none` |
| Sankey Diagram | ⚪ recognised only | `none` |
| Waterfall Chart | 🟡 partial | `bars` |
| Funnel Chart | ⚪ recognised only | `none` |
| Network Graph | ⚪ recognised only | `none` |
| Gantt Chart | ⚪ recognised only | `none` |
| Candlestick Chart | ⚪ recognised only | `none` |
| Financial Charts | 🟡 partial | `curve` |
| Multi-panel Scientific Figure | ✅ full | `curve` |
| Generic / Unknown | 🟡 partial | `curve` |

---

## 7. Outputs

| Format | File | Content |
|---|---|---|
| Word | `*_report_<fa|en>.docx` | complete scientific report (editable, RTL for Persian) |
| Excel | `*_data.xlsx` | 15+ sheets, tables, formulas, native charts |
| PDF | `*_report_<fa|en>.pdf` | printable report (English natively; Persian with `arabic-reshaper`+`python-bidi`+font, or via LibreOffice) |
| CSV | `*_series_<name>.csv`, `*_all_series.csv` | one file per series + combined (UTF-8 with BOM for Excel) |
| JSON | `*_project.json` | **everything**: settings, calibration, series, points, analysis, log — the project can be reloaded |
| PNG / SVG | `reconstructed_chart`, `extraction_overlay`, `fit_*`, `derivative_*`, `series_comparison` | reconstructed charts and analytic figures |
| TXT | `*_summary_<fa|en>.txt` | plain-text summary |
| ZIP | `*_all_outputs.zip` | all generated files + `manifest.json` |

Ready-made examples (generated from the *Force (N)* sample) are in **`sample_outputs/`**.

---

## 8. Accuracy: validation results

`scripts/run_validation.py` runs the whole pipeline on synthetic charts with known ground truth and compares extracted and true data.
Metrics: **MAE / RMSE** (as % of the true value range of the curve), **coordinate error** (mean distance of an extracted point to the true polyline, % of the plot size), **axis-calibration error** (error of the calibrated value at the plot-area corners, % of the axis range), **point-detection precision / recall** (markers: matched within 3 % of the plot size; curves: precision = fraction of points within 1 %, recall = covered fraction of the x-range) and **extraction coverage**.

<div align="center"><img src="docs/images/validation_summary.png" width="85%" alt="validation summary"/></div>

| Sample (synthetic, ground truth known) | Detected type | Series found/expected | MAE % | RMSE % | Coord. error % | Axis-calib. error % | Point precision | Point recall | Coverage |
|---|---|---|---|---|---|---|---|---|---|
| 01_single_linear | line | 1/1 | 0.253 | 0.258 | 0.179 | 0.078 | 1.000 | 1.000 | 1.000 |
| 02_multi_curve | multi_series | 3/3 | 0.270 | 0.306 | 0.167 | 0.039 | 1.000 | 1.000 | 1.000 |
| 03_exponential | line | 1/1 | 0.269 | 0.273 | 0.198 | 0.055 | 1.000 | 1.000 | 1.000 |
| 04_markers | line | 1/1 | 0.573 | 0.716 | 0.354 | 0.055 | 1.000 | 1.000 | 1.000 |
| 05_error_bars | error_bar | 1/1 | 0.247 | 0.284 | 0.181 | 0.059 | 1.000 | 1.000 | 1.000 |
| 06_log_log | multi_series | 2/2 | 0.392 | 0.544 | 0.171 | 0.042 | 1.000 | 0.935 | 0.935 |
| 07_unconventional_axes | line | 1/1 | 0.280 | 0.351 | 0.135 | 0.079 | 1.000 | 1.000 | 1.000 |
| 08_multi_panel | line | 2/2 | 0.184 | 0.216 | 0.071 | 0.020 | 1.000 | 1.000 | 1.000 |
| 09_low_quality | line | 1/1 | needs manual axis values (OCR rejected) | | | | | | |
| 09_low_quality (manual axis edges) | line | 1/1 | 0.470 | 0.555 | 0.222 | – | 1.000 | 1.000 | 1.000 |
| 10_grid_lines | multi_series | 2/2 | 0.237 | 0.285 | 0.100 | 0.057 | 1.000 | 1.000 | 1.000 |
| 11_close_curves | multi_series | 3/3 | 0.711 | 0.778 | 0.341 | 0.057 | 1.000 | 1.000 | 1.000 |
| 12_dual_axis | dual_y | 2/2 | 0.171 | 0.179 | 0.113 | 0.020 | 1.000 | 0.975 | 0.975 |
| 13_force_four_curves | force_displacement | 4/4 | 0.263 | 0.412 | 0.111 | 0.064 | 1.000 | 0.991 | 0.991 |
| 14_bar_chart | bar | 1/– | 0.041 | 0.052 | – | – | 1.000 | 1.000 | 1.000 |
| 15_pie_chart | pie | 4/– | 0.191 | 0.199 | – | – | 1.000 | 1.000 | 1.000 |
| 16_confidence_band | line | 1/1 | 0.397 | 0.408 | 0.248 | 0.064 | 1.000 | 1.000 | 1.000 |
| 17_vector_chart (PDF vector paths) | multi_series | 2/2 | 0.101 | – | – | – | – | – | – |

How to read this table honestly:

* The charts are **synthetic and mostly clean** (matplotlib, 100–110 dpi); results on real scans will be worse. `09_low_quality` (blur + noise + JPEG quality 38 + 1.2° rotation) shows the intended behaviour: the OCR values were *inconsistent*, so the software **rejected the calibration and asked for manual axis values** instead of producing wrong numbers. With axis values entered manually the MAE is below 0.5 % of the range.
* Typical error is **0.2–0.7 % of the value range**, i.e. 1–3 pixels; this is the physical resolution limit of a raster image, not something an algorithm can remove.
* Error-bar half-lengths have ≈1.4 % relative error; the *type* of the error (SD / SE / CI) is always reported as **unspecified**.
* Pie sectors are measured to ≈0.2 percentage points; bar heights to ≈0.04 % of the largest bar.
* Recall is slightly below 1 for the charts whose curves touch the axes (`06`, `12`, `13`): the start of a curve is hidden under the axis lines (≈1 % of the x-range).
* Timing: 2–4 s per chart on a laptop CPU (OCR dominates).

Run it yourself: `python scripts/run_validation.py` → `data/outputs/validation/`.

---

## 9. Sample charts and the *Force (N)* test chart

`sample_charts/` contains 17 synthetic charts (+ `.json` ground truth): linear, multi-curve, exponential, markers, error bars, log–log, reversed axes, multi-panel, low quality, dark grid, close / crossing curves, dual Y axis, **force–displacement with four curves**, bar chart, pie chart, confidence band and a vector PDF. They are regenerated by `python scripts/generate_samples.py` and are always marked **Sample Data**.

**About the user's own test image.** The project brief mentions a chart with a *Force (N)* axis and four curves `PAM`, `PAMCZ3%`, `PAMCZ1%`, `PA`. That image file was **not part of the delivered material**, so `13_force_four_curves.png` is a *synthetic imitation* (same labels, `Force (N)` axis title and **no title on the horizontal axis**, to exercise the "unknown, never invented" rule). To evaluate your original image: copy it into `sample_charts/` (e.g. `force_user.png`) and either load it from the **New Analysis → Try a sample** tab or run

```bash
python scripts/make_sample_outputs.py     # adapt JOBS at the top of the file to your file name
```

---

## 10. Architecture and folder structure

```text
GraphInsight-AI/
├── .streamlit/
│   └── config.toml
├── analysis/
│   ├── __init__.py
│   ├── _compat.py
│   ├── correlation_analysis.py
│   ├── curve_fitting.py
│   ├── data_cleaning.py
│   ├── derivative_analysis.py
│   ├── integral_analysis.py
│   ├── intersection_analysis.py
│   ├── mathematical_analysis.py
│   ├── scientific_interpretation.py
│   ├── statistical_analysis.py
│   └── uncertainty_analysis.py
├── assets/
│   ├── fonts/
│   ├── logo/
│   └── styles/
├── config/
│   ├── __init__.py
│   ├── constants.py
│   ├── logging_config.py
│   └── settings.py
├── core/
│   ├── __init__.py
│   ├── axis_calibration.py
│   ├── axis_detector.py
│   ├── bar_extractor.py
│   ├── chart_detector.py
│   ├── confidence_estimator.py
│   ├── coordinate_transform.py
│   ├── curve_detector.py
│   ├── curve_digitizer.py
│   ├── error_bar_detector.py
│   ├── image_loader.py
│   ├── image_preprocessor.py
│   ├── legend_detector.py
│   ├── manual_edit.py
│   ├── marker_detector.py
│   ├── ocr_engine.py
│   ├── pdf_processor.py
│   ├── pipeline.py
│   └── plot_area_detector.py
├── dashboard/
│   ├── components/
│   ├── __init__.py
│   ├── data_explorer.py
│   ├── digitization.py
│   ├── history.py
│   ├── home.py
│   ├── i18n.py
│   ├── image_processing.py
│   ├── mathematical_analysis.py
│   ├── reports.py
│   ├── session.py
│   ├── statistical_analysis.py
│   ├── theme.py
│   ├── upload.py
│   └── visualization.py
├── data/
├── docs/
│   ├── images/   (26 files)
│   ├── validation_results.json
│   └── validation_results.md
├── exporters/
│   ├── __init__.py
│   ├── chart_exporter.py
│   ├── csv_exporter.py
│   ├── excel_exporter.py
│   ├── export_manager.py
│   ├── json_exporter.py
│   ├── pdf_exporter.py
│   ├── report_text.py
│   ├── txt_exporter.py
│   ├── word_exporter.py
│   └── zip_exporter.py
├── models/
│   ├── __init__.py
│   ├── analysis_models.py
│   ├── chart_types.py
│   └── data_models.py
├── sample_charts/   (35 files)
├── sample_outputs/   (4 files)
├── scripts/
│   ├── capture_screenshots.py
│   ├── generate_samples.py
│   ├── make_readme_assets.py
│   ├── make_sample_outputs.py
│   └── run_validation.py
├── storage/
│   ├── __init__.py
│   ├── database.py
│   ├── history_manager.py
│   └── project_manager.py
├── tests/
│   ├── __init__.py
│   ├── common.py
│   ├── fake_streamlit.py
│   ├── test_axis_calibration.py
│   ├── test_curve_fitting.py
│   ├── test_dashboard_smoke.py
│   ├── test_digitization.py
│   ├── test_exporters.py
│   ├── test_image_processing.py
│   └── test_statistics.py
├── .env.example
├── .gitignore
├── LICENSE
├── README.md
├── README_FA.md
├── app.py
├── install.bat
├── install.sh
├── requirements-dev.txt
├── requirements-lock.txt
├── requirements.txt
├── run.bat
└── run.sh
```

Key rule: **image-processing logic (`core/`, `analysis/`, `exporters/`) never imports the UI**; the dashboard only calls these modules. OCR is a plug-in (`core.ocr_engine.register_backend`), so an alternative engine (e.g. EasyOCR) can be added without touching the pipeline.

---

## 11. Using the engine from Python

```python
from core.image_loader import load_image
from core.pipeline import analyze_image
from config.settings import ExtractionSettings
from analysis.mathematical_analysis import analyze_chart
from exporters.export_manager import export_all

out = analyze_image(load_image("sample_charts/13_force_four_curves.png"),
                    ExtractionSettings(n_points=300, sampling="adaptive"))
chart = out.state.charts[0]
print(chart.chart_type, [s.name for s in chart.series])

analyze_chart(chart)                                   # fits, derivatives, integrals, statistics ...
print(chart.series[0].points.head())                   # x, y, px, py, status, confidence, method
export_all(out.state, "my_outputs", ["xlsx", "docx", "csv", "json"], lang="en",
           original=out.original, processed=out.processed)

# manual axis information (e.g. when OCR is unavailable):
manual = {"panels": {"0": {"x_edges": [0, 10], "y_edges": [0, 100]}}}   # values at the plot-area edges
out = analyze_image(load_image("figure.png"), manual=manual)
```

---

## 12. Troubleshooting

| Symptom | Cause / solution |
|---|---|
| *"Tesseract OCR not installed"* banner | Install Tesseract (see 4.1). Without it, enter tick values in **Image Processing → Calibration**. If it is installed but not found, set `TESSERACT_CMD` in `.env`. |
| *"OCR tick values are mutually inconsistent … calibration rejected"* | The image is too small / blurry. Use a higher-resolution image, or type the tick values (≥ 3 ticks) or the edge values manually. |
| Plot area is wrong / *"axes lines not found"* | Faint or missing axes: correct the box manually (Image Processing → Plot area). |
| A curve is missing or two curves are merged | Same / very similar colours: use *re-extract from colour*, lower the colour tolerance, or add points manually. |
| Legend names appear as `Series 1` | The legend text was not readable: rename the series in *Chart Digitization*. |
| Log axis labelled `10²` read as `102` | Handled automatically for superscripts; if it fails choose the scale `log10` and type the ticks. |
| `run.bat` closes immediately | It does not — on errors it pauses; read the message. Typical causes: Python < 3.8, no internet during the first installation. |
| `pip install` fails | Check the internet connection / proxy. On very old (3.8) or very new Python versions some packages may lack wheels: use Python 3.10 – 3.12. |
| Persian PDF is English | Install `arabic-reshaper` + `python-bidi` (in `requirements.txt`) and put `Vazirmatn-Regular.ttf` in `assets/fonts/`, or install LibreOffice. The Word report is always Persian-capable. |
| Port 8501 is busy | `streamlit run app.py --server.port 8502` |
| Technical details | `data/logs/graphinsight.log` |

---

## 13. Scientific and technical limitations

* **A raster image has a finite resolution.** Typical uncertainty is ±1–2 px, converted to data units in the *Error_Analysis* sheet. Points reconstructed from a line are *not* the experimenter's original measurements; interpolated points even less so.
* **Fitted equations are approximations.** Few points cannot identify the generating function; the program reports the *selected approximate model* and the alternatives.
* **Derivatives amplify noise**; integrals are numerical estimates. Methods are named in every output.
* **Statistical tests need independent observations.** Dense points sampled along a line are dependent: p-values are shown but flagged as meaningless; use real markers (`markers` source) for inference.
* **Error bars / shaded regions** – the type (SD, SE, CI, range) is *not* determined unless you state it.
* **Automatic coverage** – the strategies listed as ✅ in §6. Not implemented: 3-D / surface / contour / heat-map value extraction, box & violin statistics, polar plots, Sankey / treemap / network, candlesticks, ternary, radar. Nyquist / parametric curves use skeleton tracing (partial).
* **Axes** – automatic calibration handles axes that lie at the left / bottom of the plot with numeric labels. Date-time, categorical and non-uniform axes need the scale selected manually; offset labels such as "×10³", rotated tick labels, axes crossing in the middle of the plot and broken axes are not read automatically.
* **Curves** – single-valued curves are traced by dynamic programming; overlapping curves of the same colour cannot be separated (a warning is raised); thin marker shapes (`x`, `+`) are not detected as markers; about 1 % of the x-range may be lost where a curve touches the axes.
* **OCR** – numbers were read correctly on the clean test images; blurry, very small text (sample `09`) was not. Titles / legends depend on Tesseract and may be misread (`mg` → `ma`) — check them. Persian chart text needs the `fas` language pack.
* **Language of figures** – matplotlib figures in reports use English labels (the Persian report text itself is Persian).
* The dashboard keeps the active project in the browser session; long operations run on the main script thread (cancel = click another button).

---

## 14. Tests and testing status

```bash
python -m unittest discover -s tests -t .      # or:  pytest tests
```

70 automated tests (≈ 85 s): image loading / validation, de-skew, plot-area detection, calibration mathematics, OCR-based axis detection, curve / marker / error-bar / bar / pie / band / dual-axis / multi-panel extraction against ground truth, vector PDF, curve fitting (incl. rejection of unsafe custom expressions), derivatives / integrals / statistics / intersections, all exporters (Excel structure and formulas, Word, PDF, CSV, JSON round-trip, ZIP), SQLite project storage, undo / redo, ZIP-slip protection and a smoke test of all 10 dashboard pages.

**Honest status of this release**

* The extraction engine, analysis modules and exporters were executed and verified with the test-suite and the validation script described above (Python 3.12, Tesseract 5).
* **Python 3.8 – 3.11:** the source was audited statically for 3.8 compatibility (syntax checked with `ast.parse(feature_version=(3, 8))`, no use of newer standard-library APIs, no runtime use of `X | None` / `list[int]`, NumPy 2-only and new-SciPy-only calls replaced by helpers in `analysis/_compat.py`). The test-suite itself could only be **executed on Python 3.12**; if you find a problem on an older Python, please report the traceback.
* The **Streamlit / Plotly user interface could not be launched in the build environment** (no network to install Streamlit). All ten dashboard modules were executed against a faithful stand-in (`tests/fake_streamlit.py`) which checks the Python code paths, but the visual layout in a real browser was **not** inspected. If you meet a UI problem on first launch, please report it with the traceback from the terminal / `data/logs`.
* The Persian PDF path through `arabic-reshaper` / `python-bidi` could not be run here; the LibreOffice-based Persian PDF and the Persian Word report were run and inspected.
* `requirements.txt` ranges for Streamlit and Plotly are not pinned to a tested version for this reason.

---

## 15. Privacy and security

* Nothing leaves your computer: no cloud API, no telemetry (`gatherUsageStats = false`), server bound to `127.0.0.1`.
* Uploaded files are validated (extension, magic bytes, size) and only decoded as images — never executed. Custom model expressions are whitelist-checked and parsed by SymPy (no `eval` of user text). ZIP import is protected against path traversal.
* Projects, uploads, outputs, logs and the SQLite database live in `data/` (change with `GI_DATA_DIR`).

---

## 16. License and credits

* **Developer: Hamid Yarali (حمید یارعلی)**
* MIT License — see [`LICENSE`](LICENSE).
* Built on open-source libraries: OpenCV, scikit-image, NumPy, SciPy, pandas, SymPy, scikit-learn, Matplotlib, Plotly, Streamlit, Tesseract / pytesseract, pypdfium2, XlsxWriter, openpyxl, python-docx, ReportLab, arabic-reshaper, python-bidi.
