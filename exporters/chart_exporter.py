"""Matplotlib figures (reconstructed charts, overlays, fits, derivatives) and PNG / SVG export."""
from __future__ import annotations

import io
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from config import constants as C  # noqa: E402
from models.data_models import ChartResult  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.grid": True, "grid.alpha": 0.25, "figure.dpi": 100,
                     "axes.spines.top": False, "axes.spines.right": False})


def _label(ax_info, fallback):
    if ax_info is None:
        return fallback
    n = ax_info.display_name
    return n if n and n != "unknown" else fallback


def _reversed(cal, is_x: bool) -> bool:
    if cal is None or cal.scale == "piecewise":
        return False
    return (cal.a < 0) if is_x else (cal.a > 0)


def fig_reconstruction(chart: ChartResult, title: str | None = None, figsize=(8, 5), show_interp=True, opts: dict | None = None) -> plt.Figure:
    """Chart rebuilt from the extracted data. ``opts`` (all optional): title, xlabel, ylabel, y2label, colors{name:hex},
    visible[names], lw, ms, legend(bool), legend_loc, xlim, ylim, logx, logy, grid, dark, figsize."""
    o = opts or {}
    figsize = o.get("figsize", figsize)
    dark = o.get("dark", False)
    if dark:
        plt.style.use("dark_background")
    fig, ax = plt.subplots(figsize=figsize)
    ax2 = ax.twinx() if (chart.y2_axis is not None and any(s.axis == "y2" for s in chart.series)) else None
    lw, ms = o.get("lw", 1.8), o.get("ms", 5)
    for s in chart.series:
        if o.get("visible") is not None and s.name not in o["visible"]:
            continue
        a = ax2 if (s.axis == "y2" and ax2 is not None) else ax
        p = s.points.dropna(subset=["x", "y"]).sort_values("x")
        if p.empty or s.kind == "pie":
            continue
        col = (o.get("colors") or {}).get(s.name, s.hex_color)
        mk = p[p.status == C.ST_MARKER]
        dense = p[p.status != C.ST_MARKER]
        if s.kind == "bars":
            a.bar(p.x, p.y, color=col, alpha=0.85, label=s.name, width=0.6 if len(p) < 30 else None)
            continue
        if len(dense) and s.kind != "markers":
            if not show_interp:
                dense = dense[dense.status != C.ST_INTERP]
            a.plot(dense.x, dense.y, "-", color=col, lw=lw, label=s.name)
        if len(mk):
            lab = None if (len(dense) and s.kind != "markers") else s.name
            er = s.errors.dropna(subset=["y_plus", "y_minus"]) if (s.errors is not None and len(s.errors)) else None
            if er is not None and len(er):
                m2 = s.points[s.points.idx.isin(er.idx)].sort_values("x")
                er = er.set_index("idx").loc[m2.idx]
                a.errorbar(m2.x, m2.y, yerr=[er.y_minus.values, er.y_plus.values], fmt="o", color=col, capsize=3, ms=ms, label=lab)
            else:
                a.plot(mk.x, mk.y, "o", color=col, ms=ms, label=lab)
        if s.band is not None and len(s.band):
            a.fill_between(s.band.x, s.band.y_low, s.band.y_high, color=col, alpha=0.2, lw=0)
    cx = chart.x_axis.calibration if chart.x_axis else None
    cy = chart.y_axis.calibration if chart.y_axis else None
    if o.get("logx", bool(cx and cx.scale in ("log10", "log2", "ln"))):
        ax.set_xscale("log")
    if o.get("logy", bool(cy and cy.scale in ("log10", "log2", "ln"))):
        ax.set_yscale("log")
    if _reversed(cx, True):
        ax.invert_xaxis()
    if _reversed(cy, False):
        ax.invert_yaxis()
    if o.get("xlim"):
        ax.set_xlim(*o["xlim"])
    if o.get("ylim"):
        ax.set_ylim(*o["ylim"])
    ax.set_xlabel(o.get("xlabel") or _label(chart.x_axis, "X (axis title unknown)"))
    ax.set_ylabel(o.get("ylabel") or _label(chart.y_axis, "Y (axis title unknown)"))
    ax.grid(o.get("grid", True), alpha=0.25)
    if ax2 is not None:
        ax2.set_ylabel(o.get("y2label") or _label(chart.y2_axis, "Y2"))
        ax2.grid(False)
        ax2.spines["right"].set_visible(True)
    ax.set_title(o.get("title") or title or chart.title or "Reconstructed from extracted data")
    h, l = ax.get_legend_handles_labels()
    if ax2 is not None:
        h2, l2 = ax2.get_legend_handles_labels()
        h, l = h + h2, l + l2
    if h and o.get("legend", True):
        ax.legend(h, l, loc=o.get("legend_loc", "best"), fontsize=8)
    fig.text(0.99, 0.01, "reconstructed by GraphInsight AI", ha="right", va="bottom", fontsize=6, color="#888888")
    fig.tight_layout()
    if dark:
        plt.style.use("default")
        plt.rcParams.update({"axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False, "axes.spines.right": False})
    return fig


def fig_overlay(processed: np.ndarray, chart: ChartResult, figsize=(9, 6)) -> plt.Figure:
    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(processed)
    ax.grid(False)
    b = chart.box
    if b:
        ax.add_patch(plt.Rectangle((b["x0"], b["y0"]), b["x1"] - b["x0"], b["y1"] - b["y0"], fill=False, ec="#00a86b", lw=1.6, ls="--"))
    for axinfo, c in ((chart.x_axis, "#e91e63"), (chart.y_axis, "#e91e63"), (chart.y2_axis, "#9c27b0")):
        if axinfo is None:
            continue
        for t in axinfo.ticks:
            if axinfo.orientation == "x":
                ax.plot([t.pixel] * 2, [axinfo.line_pos, axinfo.line_pos + 14], color=c, lw=1.2)
            else:
                dx = 14 if axinfo.side == "right" else -14
                ax.plot([axinfo.line_pos, axinfo.line_pos + dx], [t.pixel] * 2, color=c, lw=1.2)
    for s in chart.series:
        p = s.points
        mk, dn = p[p.status == C.ST_MARKER], p[p.status != C.ST_MARKER]
        if len(dn):
            ax.plot(dn.px, dn.py, ".", ms=2.5, color=s.hex_color, mec="black", mew=0.15)
        if len(mk):
            ax.plot(mk.px, mk.py, "o", ms=6, mfc="none", mec="black", mew=1.2)
    ax.set_axis_off()
    fig.tight_layout()
    return fig


def fig_fit(chart: ChartResult, name: str, figsize=(8, 6)) -> plt.Figure | None:
    a = (chart.analysis.get("series") or {}).get(name) if chart.analysis else None
    s = chart.series_by_name(name)
    if not a or not s or not a.get("fits") or not a["fits"].get("models"):
        return None
    from analysis import data_cleaning as DC
    sel, _ = DC.select_points(s.points)
    x, y, _ = DC.clean_xy(sel)
    best = next(m for m in a["fits"]["models"] if m["name"] == a["fits"]["best"])
    fig, (ax, ar) = plt.subplots(2, 1, figsize=figsize, gridspec_kw=dict(height_ratios=[3, 1]), sharex=True)
    ax.plot(x, y, ".", ms=3, color=s.hex_color, alpha=0.6, label="extracted data")
    others = [m for m in a["fits"]["models"] if m["x_fit"] and m["name"] != best["name"]][:2]
    for m in others:
        ax.plot(m["x_fit"], m["y_fit"], "--", lw=1, alpha=0.7, label=f"{m['name']} (R²={m['metrics']['r2']:.4f})")
    ax.plot(best["x_fit"], best["y_fit"], "-", color="black", lw=1.8, label=f"BEST: {best['name']} (R²={best['metrics']['r2']:.4f})")
    ax.set_ylabel(_label(chart.y_axis, "Y"))
    ax.set_title(f"{name}: model fit (approximate model)")
    ax.legend(fontsize=7)
    yhat = np.interp(x, best["x_fit"], best["y_fit"])
    ar.plot(x, y - yhat, ".", ms=3, color="#555555")
    ar.axhline(0, color="black", lw=0.8)
    ar.set_ylabel("residual")
    ar.set_xlabel(_label(chart.x_axis, "X"))
    fig.tight_layout()
    return fig


def fig_derivative(chart: ChartResult, name: str, figsize=(8, 5)) -> plt.Figure | None:
    a = (chart.analysis.get("series") or {}).get(name) if chart.analysis else None
    if not a or not a.get("derivative"):
        return None
    d = a["derivative"]
    fig, axs = plt.subplots(3, 1, figsize=figsize, sharex=True)
    axs[0].plot(d["x"], d["y_smooth"], color="#1f77b4"); axs[0].set_ylabel("y (smoothed)")
    axs[1].plot(d["x"], d["d1"], color="#d62728"); axs[1].set_ylabel("dy/dx")
    axs[2].plot(d["x"], d["d2"], color="#2ca02c"); axs[2].set_ylabel("d²y/dx²")
    for p in d.get("inflection_points", []):
        for ax in axs:
            ax.axvline(p["x"], color="gray", ls=":", lw=0.8)
    axs[2].set_xlabel(_label(chart.x_axis, "X"))
    axs[0].set_title(f"{name}: derivatives ({d['method'][:48]}...)", fontsize=9)
    fig.tight_layout()
    return fig


def fig_comparison(chart: ChartResult, figsize=(8, 4.5)) -> plt.Figure | None:
    if len([s for s in chart.series if s.kind not in ("pie", "bars")]) < 2:
        return None
    fig, ax = plt.subplots(figsize=figsize)
    for s in chart.series:
        p = s.points.dropna(subset=["x", "y"]).sort_values("x")
        if len(p) < 3 or s.kind in ("pie", "bars"):
            continue
        y = p.y.to_numpy()
        ax.plot(p.x, (y - y.min()) / (np.ptp(y) or 1), color=s.hex_color, label=s.name, lw=1.6)
    for r in (chart.analysis or {}).get("intersections", [])[:20]:
        ax.axvline(r["x"], color="gray", lw=0.6, ls=":")
    ax.set_title("Shape comparison (each curve min-max normalised) ; dotted = crossings")
    ax.set_xlabel(_label(chart.x_axis, "X"))
    ax.set_ylabel("normalised value")
    ax.legend(fontsize=8)
    fig.tight_layout()
    return fig


def fig_bytes(fig: plt.Figure, fmt: str = "png", dpi: int = 160) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format=fmt, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def equation_png(latex: str, fallback_text: str, fontsize: int = 14) -> bytes:
    """Render a LaTeX equation with matplotlib mathtext; falls back to the plain-text form."""
    for txt in (f"${latex.replace(chr(92) + 'dfrac', chr(92) + 'frac')}$", fallback_text):
        try:
            fig = plt.figure(figsize=(0.1, 0.1))
            fig.text(0, 0, txt, fontsize=fontsize)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=200, bbox_inches="tight", pad_inches=0.08)
            plt.close(fig)
            return buf.getvalue()
        except Exception:  # noqa: BLE001
            plt.close("all")
    return b""


def export_figures(chart: ChartResult, processed: np.ndarray | None, outdir: Path, prefix: str = "", svg: bool = True) -> dict:
    """Write PNG (+SVG) files of reconstruction, overlay, fits, derivatives. Returns {name: path}."""
    outdir.mkdir(parents=True, exist_ok=True)
    made = {}

    def save(fig, stem):
        if fig is None:
            return
        for fmt in (("png", "svg") if svg else ("png",)):
            p = outdir / f"{prefix}{stem}.{fmt}"
            fig.savefig(p, format=fmt, dpi=160 if fmt == "png" else None, bbox_inches="tight")
            made[f"{stem}.{fmt}"] = str(p)
        plt.close(fig)
    save(fig_reconstruction(chart), "reconstructed_chart")
    if processed is not None:
        save(fig_overlay(processed, chart), "extraction_overlay")
    save(fig_comparison(chart), "series_comparison")
    for s in chart.series:
        safe = "".join(c if c.isalnum() else "_" for c in s.name)
        save(fig_fit(chart, s.name), f"fit_{safe}")
        save(fig_derivative(chart, s.name), f"derivative_{safe}")
    return made
