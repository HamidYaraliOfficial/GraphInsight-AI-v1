"""One entry point that writes every requested output format for a project."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from analysis.mathematical_analysis import analyze_chart
from config.logging_config import get_logger
from models.data_models import ProjectState
from . import chart_exporter, csv_exporter, json_exporter, txt_exporter, zip_exporter

log = get_logger("export")
ALL_FORMATS = ["docx", "xlsx", "pdf", "csv", "json", "png", "svg", "txt", "zip"]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]+", "_", name).strip("_") or "project"


def ensure_analysis(state: ProjectState, opts: dict | None = None, progress=None) -> None:
    for ch in state.charts:
        if not ch.analysis and ch.series:
            analyze_chart(ch, opts, progress)


def export_all(state: ProjectState, outdir: Path, formats: list[str], lang: str = "fa", original: np.ndarray | None = None,
               processed: np.ndarray | None = None, analysis_opts: dict | None = None, progress=None) -> dict:
    """Write the requested formats; returns {label: path}. Failures of one format never block the others."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ensure_analysis(state, analysis_opts)
    base = _safe(state.name)
    made: dict[str, str] = {}
    errors: dict[str, str] = {}

    def step(fmt, fn):
        if fmt not in formats and "zip" not in formats:
            return
        try:
            made.update(fn())
        except Exception as exc:  # noqa: BLE001
            log.exception("export %s failed", fmt)
            errors[fmt] = str(exc)

    for i, fmt in enumerate([f for f in ALL_FORMATS if f not in ("zip", "svg")]):
        if progress:
            progress(i / len(ALL_FORMATS), f"exporting {fmt}")
        if fmt == "docx":
            from .word_exporter import export_word
            step(fmt, lambda: {"report.docx": export_word(state, outdir / f"{base}_report_{lang}.docx", original, processed, lang)})
        elif fmt == "xlsx":
            from .excel_exporter import export_excel
            step(fmt, lambda: {"data.xlsx": export_excel(state, outdir / f"{base}_data.xlsx", lang)})
        elif fmt == "pdf":
            from .pdf_exporter import export_pdf
            step(fmt, lambda: {"report.pdf": export_pdf(state, outdir / f"{base}_report_{lang}.pdf", original, processed, lang)})
        elif fmt == "csv":
            def _csv():
                r = {}
                for ch in state.charts:
                    r.update({(f"P{ch.panel_index + 1}_" + k): v for k, v in csv_exporter.export_csv(ch, outdir, f"{base}_p{ch.panel_index + 1}_").items()})
                return r
            step(fmt, _csv)
        elif fmt == "json":
            step(fmt, lambda: {"project.json": json_exporter.export_json(state, outdir / f"{base}_project.json")})
        elif fmt == "png":
            if not ({"png", "svg"} & set(formats)) and "zip" not in formats:
                continue
            def _fig():
                r = {}
                for ch in state.charts:
                    got = chart_exporter.export_figures(ch, processed, outdir, f"{base}_p{ch.panel_index + 1}_", svg=True)
                    r.update({f"P{ch.panel_index + 1}_{k}": v for k, v in got.items()})
                return r
            try:
                made.update(_fig())
            except Exception as exc:  # noqa: BLE001
                log.exception("figure export failed")
                errors["png/svg"] = str(exc)
        elif fmt == "txt":
            step(fmt, lambda: {"summary.txt": txt_exporter.export_txt(state, outdir / f"{base}_summary_{lang}.txt", lang)})
    if "zip" in formats:
        z = zip_exporter.make_zip({k: v for k, v in made.items()}, outdir / f"{base}_all_outputs.zip",
                                  {"README.txt": "GraphInsight AI export bundle\nDeveloper: Hamid Yarali\n"})
        made["all_outputs.zip"] = z
    if errors:
        made["_errors"] = "; ".join(f"{k}: {v}" for k, v in errors.items())
    if progress:
        progress(1.0, "export finished")
    return made
