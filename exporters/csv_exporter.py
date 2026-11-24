"""CSV export: one file per series + one combined file."""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from models.data_models import ChartResult


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]+", "_", name).strip("_") or "series"


def combined_frame(chart: ChartResult) -> pd.DataFrame:
    frames = []
    for s in chart.series:
        d = s.sorted_points().copy()
        d.insert(0, "series", s.name)
        d.insert(1, "color", s.hex_color)
        d["axis"] = s.axis
        frames.append(d)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def export_csv(chart: ChartResult, outdir: Path, prefix: str = "") -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    made = {}
    comb = combined_frame(chart)
    p = outdir / f"{prefix}all_series.csv"
    comb.to_csv(p, index=False, encoding="utf-8-sig")
    made["all_series.csv"] = str(p)
    for s in chart.series:
        p = outdir / f"{prefix}series_{safe_name(s.name)}.csv"
        d = s.sorted_points()
        d.to_csv(p, index=False, encoding="utf-8-sig")
        made[p.name] = str(p)
    if chart.bars is not None and len(chart.bars):
        p = outdir / f"{prefix}bars.csv"
        chart.bars.to_csv(p, index=False, encoding="utf-8-sig")
        made[p.name] = str(p)
    if chart.pie is not None and len(chart.pie):
        p = outdir / f"{prefix}pie_sectors.csv"
        chart.pie.to_csv(p, index=False, encoding="utf-8-sig")
        made[p.name] = str(p)
    return made
