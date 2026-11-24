"""Shared helpers for the test-suite."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "sample_charts"


def ensure_samples() -> None:
    if not (SAMPLES / "01_single_linear.png").exists():
        from scripts.generate_samples import main
        main(str(SAMPLES))


def gt(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def analyze(name: str, **kw):
    from config.settings import ExtractionSettings
    from core.image_loader import load_image
    from core.pipeline import analyze_image
    ensure_samples()
    return analyze_image(load_image(SAMPLES / name), kw.pop("settings", ExtractionSettings()), **kw)


def ocr_available() -> bool:
    from core.ocr_engine import ocr_status
    return ocr_status()["available"]
