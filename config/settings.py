"""Runtime settings (paths, defaults, environment overrides)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("GI_DATA_DIR", ROOT_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
PROJECT_DIR = DATA_DIR / "projects"
OUTPUT_DIR = DATA_DIR / "outputs"
DB_PATH = DATA_DIR / "graphinsight.sqlite3"
LOG_DIR = DATA_DIR / "logs"
ASSETS_DIR = ROOT_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
SAMPLE_DIR = ROOT_DIR / "sample_charts"


def load_env_file(path: Path | None = None) -> None:
    """Minimal .env loader (no external dependency)."""
    path = path or (ROOT_DIR / ".env")
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env_file()


def ensure_dirs() -> None:
    for d in (DATA_DIR, UPLOAD_DIR, PROJECT_DIR, OUTPUT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)


@dataclass
class ExtractionSettings:
    """User-tunable extraction options (stored with every project)."""
    ocr_backend: str = "tesseract"          # tesseract | none
    ocr_lang: str = "eng"                   # e.g. "eng+fas" if the Persian pack is installed
    denoise: bool = True
    deskew: bool = True
    enhance_contrast: bool = True
    upscale_small: bool = True
    detect_panels: bool = True
    remove_grid: bool = True
    dense_mode: bool = True                 # also produce dense centre-line samples
    n_points: int = 200                     # points per series in dense mode
    sampling: str = "adaptive"              # adaptive | uniform_x | uniform_arc
    curvature_weight: float = 4.0
    max_gap_px: int = 25                    # largest gap that is bridged by interpolation
    color_tolerance: float = 24.0           # CIE-Lab distance for series masks
    min_series_pixels: int = 60
    curve_mode: str = "auto"                # auto | function | parametric | step
    detect_error_bars: bool = True
    detect_bands: bool = True
    use_vector_pdf: bool = True             # use exact vertices of vector PDF paths when available
    chart_type: str = "auto"                # auto or a ChartType key
    x_scale: str = "auto"                   # auto | linear | log10 | ...
    y_scale: str = "auto"
    report_lang: str = "fa"                 # fa | en
    manual_series_colors: list = field(default_factory=list)   # [[r,g,b], ...]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict | None) -> "ExtractionSettings":
        d = d or {}
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)
