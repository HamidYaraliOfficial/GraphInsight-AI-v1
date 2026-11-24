"""Application-wide constants."""
from __future__ import annotations

APP_NAME = "GraphInsight AI"
APP_NAME_FA = "گراف‌اینسایت ای‌آی"
APP_VERSION = "1.0.0"
AUTHOR = "Hamid Yarali"
AUTHOR_FA = "حمید یارعلی"
DEFAULT_URL = "http://127.0.0.1:8501"

SUPPORTED_IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp")
SUPPORTED_EXT = SUPPORTED_IMAGE_EXT + (".svg", ".pdf")
MAX_FILE_MB = 60
MAX_IMAGE_SIDE = 6000          # larger images are down-scaled stepwise
MIN_IMAGE_SIDE = 400           # smaller images are up-sampled for OCR / tracing

# Point provenance (status)
ST_MARKER = "marker"                 # real marker found in the image
ST_RECON = "reconstructed"           # point reconstructed from the line centre-line
ST_INTERP = "interpolated"           # gap filled by interpolation
ST_MANUAL = "manual"                 # entered / edited by the user
ST_VECTOR = "vector_vertex"          # exact vertex of a vector (PDF/SVG) path
POINT_STATUSES = (ST_MARKER, ST_RECON, ST_INTERP, ST_MANUAL, ST_VECTOR)

# Data sources shown in reports
SRC_IMAGE = "direct image extraction"
SRC_MATH = "mathematical computation"
SRC_FIT = "statistical fit"
SRC_INTERP = "interpolation"
SRC_MANUAL = "manual user input"

SCALES = ("linear", "log10", "log2", "ln", "datetime", "categorical", "piecewise")

SERIES_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd",
                  "#8c564b", "#e377c2", "#17becf", "#bcbd22", "#7f7f7f"]
