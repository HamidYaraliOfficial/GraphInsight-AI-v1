"""Plotly figure builders for the dashboard."""
from __future__ import annotations

import cv2
import numpy as np
import plotly.graph_objects as go

from config import constants as C
from models.data_models import ChartResult


def _tmpl(dark: bool) -> str:
    return "plotly_dark" if dark else "plotly_white"


def overlay_figure(processed: np.ndarray, chart: ChartResult, show_points: bool = True, dark: bool = False, height: int = 560) -> go.Figure:
    H, W = processed.shape[:2]
    sc = min(1.0, 1300.0 / W)
    img = cv2.resize(processed, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA) if sc < 1 else processed
    fig = go.Figure(go.Image(z=img))
    b = chart.box
    if b:
        fig.add_shape(type="rect", x0=b["x0"] * sc, y0=b["y0"] * sc, x1=b["x1"] * sc, y1=b["y1"] * sc,
                      line=dict(color="#00A86B", width=2, dash="dash"))
    for ax, color in ((chart.x_axis, "#E91E63"), (chart.y_axis, "#E91E63"), (chart.y2_axis, "#9C27B0")):
        if ax is None:
            continue
        for tk in ax.ticks:
            if ax.orientation == "x":
                fig.add_shape(type="line", x0=tk.pixel * sc, x1=tk.pixel * sc, y0=ax.line_pos * sc, y1=(ax.line_pos + 14) * sc, line=dict(color=color, width=2))
            else:
                d = 14 if ax.side == "right" else -14
                fig.add_shape(type="line", y0=tk.pixel * sc, y1=tk.pixel * sc, x0=ax.line_pos * sc, x1=(ax.line_pos + d) * sc, line=dict(color=color, width=2))
    if show_points:
        for s in chart.series:
            p = s.points
            if p.empty:
                continue
            mk = p[p.status == C.ST_MARKER]
            dn = p[p.status != C.ST_MARKER]
            if len(dn):
                fig.add_trace(go.Scattergl(x=dn.px * sc, y=dn.py * sc, mode="markers", name=s.name,
                                           marker=dict(size=4, color=s.hex_color, line=dict(width=0.4, color="black")),
                                           hovertemplate="x=%{customdata[0]:.5g}<br>y=%{customdata[1]:.5g}<extra>" + s.name + "</extra>",
                                           customdata=np.c_[dn.x, dn.y]))
            if len(mk):
                fig.add_trace(go.Scattergl(x=mk.px * sc, y=mk.py * sc, mode="markers", name=s.name + " (markers)", showlegend=False,
                                           marker=dict(size=10, symbol="circle-open", color="black", line=dict(width=2))))
    fig.update_xaxes(visible=False, range=[0, img.shape[1]])
    fig.update_yaxes(visible=False, range=[img.shape[0], 0], scaleanchor="x")
    fig.update_layout(height=height, margin=dict(l=0, r=0, t=10, b=0), dragmode="pan", template=_tmpl(dark),
                      legend=dict(orientation="h", y=1.02))
    return fig


def reconstruction_figure(chart: ChartResult, opts: dict | None = None, dark: bool = False, height: int = 520) -> go.Figure:
    o = opts or {}
    fig = go.Figure()
    for s in chart.series:
        if o.get("visible") is not None and s.name not in o["visible"]:
            continue
        p = s.points.dropna(subset=["x", "y"]).sort_values("x")
        if p.empty or s.kind == "pie":
            continue
        col = (o.get("colors") or {}).get(s.name, s.hex_color)
        yaxis = "y2" if (s.axis == "y2" and chart.y2_axis is not None) else "y"
        if s.kind == "bars":
            fig.add_trace(go.Bar(x=p.x, y=p.y, name=s.name, marker_color=col, yaxis=yaxis))
            continue
        mk, dn = p[p.status == C.ST_MARKER], p[p.status != C.ST_MARKER]
        if len(dn) and s.kind != "markers":
            fig.add_trace(go.Scatter(x=dn.x, y=dn.y, mode="lines", name=s.name, line=dict(color=col, width=o.get("lw", 2)), yaxis=yaxis))
        if len(mk):
            err = None
            if s.errors is not None and len(s.errors):
                e = s.errors.set_index("idx").reindex(mk.idx)
                err = dict(type="data", symmetric=False, array=e.y_plus.fillna(0).to_numpy(), arrayminus=e.y_minus.fillna(0).to_numpy(), visible=True)
            fig.add_trace(go.Scatter(x=mk.x, y=mk.y, mode="markers", name=s.name, marker=dict(color=col, size=o.get("ms", 8)), error_y=err,
                                     showlegend=not (len(dn) and s.kind != "markers"), yaxis=yaxis))
        if s.band is not None and len(s.band):
            fig.add_trace(go.Scatter(x=list(s.band.x) + list(s.band.x[::-1]), y=list(s.band.y_high) + list(s.band.y_low[::-1]), fill="toself",
                                     fillcolor=col, opacity=0.2, line=dict(width=0), name=s.name + " band", showlegend=False, hoverinfo="skip"))
    cx = chart.x_axis.calibration if chart.x_axis else None
    cy = chart.y_axis.calibration if chart.y_axis else None
    xlab = o.get("xlabel") or (chart.x_axis.display_name if chart.x_axis else "X")
    ylab = o.get("ylabel") or (chart.y_axis.display_name if chart.y_axis else "Y")
    fig.update_layout(template=_tmpl(dark), height=o.get("height", height), title=o.get("title") or chart.title or "",
                      xaxis=dict(title=xlab, type="log" if o.get("logx", bool(cx and cx.scale in ("log10", "log2", "ln"))) else "linear",
                                 showgrid=o.get("grid", True), range=o.get("xlim")),
                      yaxis=dict(title=ylab, type="log" if o.get("logy", bool(cy and cy.scale in ("log10", "log2", "ln"))) else "linear",
                                 showgrid=o.get("grid", True), range=o.get("ylim")),
                      showlegend=o.get("legend", True), legend=dict(orientation="h", y=-0.2), margin=dict(l=40, r=20, t=50, b=40))
    if any(s.axis == "y2" for s in chart.series) and chart.y2_axis is not None:
        fig.update_layout(yaxis2=dict(title=o.get("y2label") or chart.y2_axis.display_name, overlaying="y", side="right", showgrid=False))
    return fig


def fit_figure(chart: ChartResult, name: str, model_names: list[str], dark: bool = False) -> go.Figure | None:
    from analysis import data_cleaning as DC
    a = (chart.analysis.get("series") or {}).get(name) if chart.analysis else None
    s = chart.series_by_name(name)
    if not a or not a.get("fits") or s is None:
        return None
    sel, _ = DC.select_points(s.points)
    x, y, _ = DC.clean_xy(sel)
    fig = go.Figure(go.Scatter(x=x, y=y, mode="markers", name="data", marker=dict(size=4, color=s.hex_color, opacity=0.7)))
    for m in a["fits"]["models"]:
        if m["name"] in model_names and m["x_fit"]:
            fig.add_trace(go.Scatter(x=m["x_fit"], y=m["y_fit"], mode="lines", name=f"{m['name']} (R²={m['metrics']['r2']:.4f})",
                                     line=dict(width=3 if m["name"] == a["fits"]["best"] else 1.6)))
    fig.update_layout(template=_tmpl(dark), height=430, margin=dict(l=40, r=20, t=30, b=40), legend=dict(orientation="h", y=-0.25),
                      xaxis_title=chart.x_axis.display_name if chart.x_axis else "X", yaxis_title=chart.y_axis.display_name if chart.y_axis else "Y")
    return fig


def residual_figure(x, res, dark: bool = False) -> go.Figure:
    fig = go.Figure(go.Scatter(x=x, y=res, mode="markers", marker=dict(size=4)))
    fig.add_hline(y=0, line_dash="dash")
    fig.update_layout(template=_tmpl(dark), height=260, margin=dict(l=40, r=20, t=20, b=30), yaxis_title="residual")
    return fig


def derivative_figure(a: dict, dark: bool = False) -> go.Figure | None:
    d = (a or {}).get("derivative")
    if not d:
        return None
    from plotly.subplots import make_subplots
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=("y (smoothed)", "dy/dx", "d²y/dx²"))
    fig.add_trace(go.Scatter(x=d["x"], y=d["y_smooth"], line=dict(color="#1F77B4")), row=1, col=1)
    fig.add_trace(go.Scatter(x=d["x"], y=d["d1"], line=dict(color="#D62728")), row=2, col=1)
    fig.add_trace(go.Scatter(x=d["x"], y=d["d2"], line=dict(color="#2CA02C")), row=3, col=1)
    for p in d.get("inflection_points", []):
        fig.add_vline(x=p["x"], line_dash="dot", line_color="gray")
    fig.update_layout(template=_tmpl(dark), height=520, showlegend=False, margin=dict(l=40, r=20, t=40, b=30))
    return fig


def histogram_figure(values, name: str, dark: bool = False) -> go.Figure:
    fig = go.Figure(go.Histogram(x=values, nbinsx=30, marker_color="#1F6FEB"))
    fig.update_layout(template=_tmpl(dark), height=300, title=name, margin=dict(l=40, r=20, t=40, b=30), bargap=0.05)
    return fig


def heatmap_figure(df, title: str, dark: bool = False) -> go.Figure:
    fig = go.Figure(go.Heatmap(z=df.values, x=list(df.columns), y=list(df.index), zmin=-1, zmax=1, colorscale="RdBu", text=np.round(df.values, 3),
                               texttemplate="%{text}"))
    fig.update_layout(template=_tmpl(dark), height=360, title=title, margin=dict(l=40, r=20, t=50, b=30))
    return fig


def quality_figure(parts: dict, dark: bool = False) -> go.Figure:
    fig = go.Figure(go.Bar(x=list(parts.values()), y=list(parts.keys()), orientation="h", marker_color="#1F6FEB"))
    fig.update_layout(template=_tmpl(dark), height=300, xaxis=dict(range=[0, 1]), margin=dict(l=10, r=10, t=10, b=10))
    return fig
