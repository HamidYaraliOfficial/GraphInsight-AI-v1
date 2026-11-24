"""Run the full pipeline on the sample charts and write complete example outputs to ./sample_outputs
(Word / Excel / PDF in Persian and English, CSV, JSON, PNG, SVG, TXT, ZIP).

Usage:  python scripts/make_sample_outputs.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analysis.mathematical_analysis import analyze_chart  # noqa: E402
from config.settings import ExtractionSettings  # noqa: E402
from core.image_loader import load_image  # noqa: E402
from core.pipeline import analyze_image  # noqa: E402
from exporters.export_manager import export_all  # noqa: E402

JOBS = [
    # (sample file, project name, folder, formats FA, formats EN)
    ("13_force_four_curves.png", "force_four_curves", "force_four_curves",
     ["docx", "xlsx", "pdf", "csv", "json", "png", "svg", "txt", "zip"], ["docx", "pdf"]),
    ("05_error_bars.png", "error_bars", "error_bars", ["xlsx", "csv", "png", "txt"], ["docx"]),
    ("06_log_log.png", "log_log", "log_log", ["xlsx", "png"], []),
]


def main() -> None:
    out_root = ROOT / "sample_outputs"
    if out_root.exists():
        shutil.rmtree(out_root)
    for sample, name, folder, f_fa, f_en in JOBS:
        out = analyze_image(load_image(ROOT / "sample_charts" / sample), ExtractionSettings(), project_name=name)
        out.state.is_sample = True
        for ch in out.state.charts:
            analyze_chart(ch)
        d = out_root / folder
        export_all(out.state, d, f_fa, "fa", out.original, out.processed)
        if f_en:
            export_all(out.state, d, f_en, "en", out.original, out.processed)
        print(sample, "->", d, len(list(d.glob("*"))), "files")


if __name__ == "__main__":
    main()
