"""Plain-text summary export."""
from __future__ import annotations

from pathlib import Path

from analysis.scientific_interpretation import interpret
from config import constants as C
from models.chart_types import chart_label
from models.data_models import ProjectState
from .report_text import fnum, series_summary_rows, tr


def export_txt(state: ProjectState, path: str | Path, lang: str = "en") -> str:
    T = tr(lang)
    L = "fa" if lang == "fa" else "en"
    out = [f"GraphInsight AI - {T['report_title']}", f"{T['project']}: {state.name}", f"{T['developer']}: Hamid Yarali", "=" * 72]
    if state.is_sample:
        out.append(T["sample"])
    for ch in state.charts:
        out += ["", f"[{T['panel']} {ch.panel_index + 1}] {chart_label(ch.chart_type, L)}",
                f"{T['x_axis']}: {ch.x_axis.display_name if ch.x_axis else '-'} | {T['y_axis']}: {ch.y_axis.display_name if ch.y_axis else '-'}"]
        for r in series_summary_rows(ch):
            out.append(f"  - {r['series']}: {r['points']} {T['pts']}; {T['start']} {r.get('start')}; {T['end']} {r.get('end')}; "
                       f"{T['maxv']} {r.get('maximum')}; {T['minv']} {r.get('minimum')}; {T['conf']} {r['confidence']}")
        an = (ch.analysis or {}).get("series", {})
        for s in ch.series:
            fm = (an.get(s.name) or {}).get("fits")
            if fm and fm.get("best"):
                b = next(m for m in fm["models"] if m["name"] == fm["best"])
                out.append(f"  {s.name}: {b['name']}  R2={fnum(b['metrics']['r2'], 6)} RMSE={fnum(b['metrics']['rmse'])}  {b['equation']['text']}")
        itp = interpret(ch, L)
        out += ["", T["s6"]] + itp["paragraphs"] + ["", T["limits"]] + ["- " + x for x in itp["limitations"]]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(out), encoding="utf-8")
    return str(path)
