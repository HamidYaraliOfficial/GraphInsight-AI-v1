"""Registry of chart types, their categories and extraction support level.

support levels
--------------
full      : data can be digitised by a dedicated extraction strategy
partial   : recognised, generic curve / region extraction possible, manual review advised
classify  : recognised (or selectable) only; automatic numeric extraction is not implemented
"""
from __future__ import annotations

from enum import Enum

# key, English name, Persian name, category, support, strategy
_REGISTRY = [
    # 2D
    ("line", "Line Chart", "نمودار خطی", "2d", "full", "curve"),
    ("scatter", "Scatter Plot", "نمودار پراکندگی", "2d", "full", "curve"),
    ("smooth_curve", "Smooth Curve", "منحنی هموار", "2d", "full", "curve"),
    ("bar", "Bar Chart", "نمودار میله‌ای", "2d", "full", "bars"),
    ("hbar", "Horizontal Bar Chart", "میله‌ای افقی", "2d", "full", "bars"),
    ("grouped_bar", "Grouped Bar Chart", "میله‌ای گروهی", "2d", "full", "bars"),
    ("stacked_bar", "Stacked Bar Chart", "میله‌ای انباشته", "2d", "full", "bars"),
    ("area", "Area Chart", "نمودار ناحیه‌ای", "2d", "full", "curve"),
    ("stacked_area", "Stacked Area Chart", "ناحیه‌ای انباشته", "2d", "partial", "curve"),
    ("step", "Step Chart", "نمودار پله‌ای", "2d", "full", "step"),
    ("error_bar", "Error Bar Chart", "نمودار با نوار خطا", "2d", "full", "curve"),
    ("scientific_curve", "Scientific Curve Plot", "منحنی علمی", "2d", "full", "curve"),
    ("time_series", "Time Series", "سری زمانی", "2d", "full", "curve"),
    ("multi_series", "Multiple Series Plot", "نمودار چندسری", "2d", "full", "curve"),
    ("dual_y", "Dual Y-Axis Chart", "نمودار دو محور Y", "2d", "full", "curve"),
    ("multi_axes", "Multiple Axes Chart", "نمودار چندمحوره", "2d", "partial", "curve"),
    ("piecewise", "Piecewise Curve", "منحنی چندبخشی", "2d", "full", "curve"),
    ("parametric", "Parametric Plot", "نمودار پارامتریک", "2d", "partial", "parametric"),
    # statistical
    ("histogram", "Histogram", "هیستوگرام", "stat", "full", "bars"),
    ("box", "Box Plot", "نمودار جعبه‌ای", "stat", "classify", "none"),
    ("violin", "Violin Plot", "نمودار ویولن", "stat", "classify", "none"),
    ("density", "Density Plot", "نمودار چگالی", "stat", "full", "curve"),
    ("kde", "KDE Plot", "نمودار KDE", "stat", "full", "curve"),
    ("ecdf", "ECDF", "تابع توزیع تجربی", "stat", "full", "step"),
    ("qq", "Q-Q Plot", "نمودار Q-Q", "stat", "full", "curve"),
    ("regression", "Regression Plot", "نمودار رگرسیون", "stat", "full", "curve"),
    ("residual", "Residual Plot", "نمودار باقیمانده", "stat", "full", "curve"),
    ("roc", "ROC Curve", "منحنی ROC", "stat", "full", "curve"),
    ("pr", "Precision-Recall Curve", "منحنی دقت-بازخوانی", "stat", "full", "curve"),
    ("confusion_matrix", "Confusion Matrix", "ماتریس درهم‌ریختگی", "stat", "classify", "none"),
    ("forest", "Forest Plot", "نمودار جنگلی", "stat", "classify", "none"),
    ("survival", "Survival Curve", "منحنی بقا", "stat", "full", "step"),
    ("kaplan_meier", "Kaplan-Meier Plot", "کاپلان-مایر", "stat", "full", "step"),
    ("bland_altman", "Bland-Altman Plot", "بلاند-آلتمن", "stat", "full", "curve"),
    # scientific / engineering
    ("stress_strain", "Stress-Strain Curve", "منحنی تنش-کرنش", "eng", "full", "curve"),
    ("force_displacement", "Force-Displacement Curve", "منحنی نیرو-جابجایی", "eng", "full", "curve"),
    ("force_elongation", "Force-Elongation Curve", "منحنی نیرو-ازدیاد طول", "eng", "full", "curve"),
    ("load_deformation", "Load-Deformation Curve", "منحنی بار-تغییرشکل", "eng", "full", "curve"),
    ("tensile", "Tensile Test Graph", "نمودار آزمون کشش", "eng", "full", "curve"),
    ("compression", "Compression Test Graph", "نمودار آزمون فشار", "eng", "full", "curve"),
    ("rheology", "Rheological Curves", "منحنی‌های رئولوژی", "eng", "full", "curve"),
    ("frequency_response", "Frequency Response", "پاسخ فرکانسی", "eng", "full", "curve"),
    ("bode", "Bode Plot", "نمودار بود", "eng", "full", "curve"),
    ("nyquist", "Nyquist Plot", "نمودار نایکوییست", "eng", "partial", "parametric"),
    ("polar", "Polar Plot", "نمودار قطبی", "eng", "classify", "none"),
    ("impedance", "Impedance Plot", "نمودار امپدانس", "eng", "partial", "parametric"),
    ("spectral", "Spectral Curves", "منحنی‌های طیفی", "eng", "full", "curve"),
    ("absorption", "Absorption / Transmission Spectra", "طیف جذب/عبور", "eng", "full", "curve"),
    ("sensor", "Sensor Measurements", "اندازه‌گیری حسگر", "eng", "full", "curve"),
    ("experimental", "Experimental Curves", "منحنی‌های آزمایشگاهی", "eng", "full", "curve"),
    ("calibration", "Calibration Curves", "منحنی کالیبراسیون", "eng", "full", "curve"),
    ("material_characterization", "Material Characterization Graphs", "نمودار مشخصه‌یابی مواد", "eng", "full", "curve"),
    # multi-dimensional
    ("scatter3d", "3D Scatter Plot", "پراکندگی سه‌بعدی", "nd", "classify", "none"),
    ("line3d", "3D Line Plot", "خطی سه‌بعدی", "nd", "classify", "none"),
    ("surface3d", "3D Surface Plot", "سطح سه‌بعدی", "nd", "classify", "none"),
    ("mesh", "Mesh Plot", "نمودار مش", "nd", "classify", "none"),
    ("contour", "Contour Plot", "نمودار کانتور", "nd", "classify", "none"),
    ("heatmap", "Heatmap", "نقشه حرارتی", "nd", "classify", "none"),
    ("ternary", "Ternary Plot", "نمودار سه‌تایی", "nd", "classify", "none"),
    ("radar", "Radar Chart", "نمودار راداری", "nd", "classify", "none"),
    ("parallel", "Parallel Coordinates", "مختصات موازی", "nd", "classify", "none"),
    ("bubble", "Bubble Chart", "نمودار حبابی", "nd", "partial", "curve"),
    # special
    ("pie", "Pie Chart", "نمودار دایره‌ای", "special", "full", "pie"),
    ("donut", "Donut Chart", "نمودار دونات", "special", "full", "pie"),
    ("treemap", "Treemap", "تری‌مپ", "special", "classify", "none"),
    ("sankey", "Sankey Diagram", "نمودار سانکی", "special", "classify", "none"),
    ("waterfall", "Waterfall Chart", "نمودار آبشاری", "special", "partial", "bars"),
    ("funnel", "Funnel Chart", "نمودار قیفی", "special", "classify", "none"),
    ("network", "Network Graph", "نمودار شبکه", "special", "classify", "none"),
    ("gantt", "Gantt Chart", "نمودار گانت", "special", "classify", "none"),
    ("candlestick", "Candlestick Chart", "نمودار شمعی", "special", "classify", "none"),
    ("financial", "Financial Charts", "نمودارهای مالی", "special", "partial", "curve"),
    ("multi_panel", "Multi-panel Scientific Figure", "شکل چندپنلی", "special", "full", "curve"),
    ("generic", "Generic / Unknown", "عمومی / نامشخص", "special", "partial", "curve"),
]

ChartType = Enum("ChartType", {k.upper(): k for k, *_ in _REGISTRY}, type=str)

CHART_INFO = {k: dict(key=k, en=en, fa=fa, category=cat, support=sup, strategy=strat)
              for k, en, fa, cat, sup, strat in _REGISTRY}

CATEGORY_NAMES = {
    "2d": ("2D charts", "نمودارهای دوبعدی"),
    "stat": ("Statistical charts", "نمودارهای آماری"),
    "eng": ("Scientific & engineering", "علمی و مهندسی"),
    "nd": ("Multi-dimensional", "چندبعدی"),
    "special": ("Combined & special", "ترکیبی و خاص"),
}


def chart_keys() -> list[str]:
    return [k for k, *_ in _REGISTRY]


def chart_label(key: str, lang: str = "en") -> str:
    info = CHART_INFO.get(key) or CHART_INFO["generic"]
    return info["fa" if lang == "fa" else "en"]


def chart_strategy(key: str) -> str:
    return (CHART_INFO.get(key) or CHART_INFO["generic"])["strategy"]


def chart_support(key: str) -> str:
    return (CHART_INFO.get(key) or CHART_INFO["generic"])["support"]
