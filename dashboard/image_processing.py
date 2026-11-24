"""Page 3 - Image Processing: original / processed image, plot area, axis calibration, manual correction."""
from __future__ import annotations

import copy

import pandas as pd
import streamlit as st

from core import manual_edit as ME
from dashboard.components import plots, ui
from dashboard.i18n import t
from dashboard.session import checkpoint, commit, rerun_manual

SCALES = ["auto", "linear", "log10", "log2", "ln", "piecewise", "categorical"]


def _manual_panel(app, idx: int) -> dict:
    m = copy.deepcopy(app.manual) if app.manual else {}
    m.setdefault("panels", {}).setdefault(str(idx), {})
    return m


def _tick_table(ax, key: str):
    rows = [dict(pixel=round(tk.pixel, 2), value=tk.value) for tk in (ax.ticks if ax else [])]
    df = pd.DataFrame(rows or [dict(pixel=None, value=None)])
    return ui.editor(df, key=key, num_rows="dynamic")


def render(app) -> None:
    st.title(t("nav_imgproc").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    idx = ch.panel_index
    dark = st.session_state.get("dark", False)
    tab_img, tab_area, tab_cal, tab_info = st.tabs([f"{t('original')} / {t('processed')}", t("plot_area"), t("calibration"), t("axis_info")])
    with tab_img:
        a, b = st.columns(2)
        with a:
            ui.image(app.original, t("original"))
        with b:
            ui.image(app.processed, t("processed"))
        pre = app.state.preprocess
        st.caption(" • ".join(pre.get("steps", [])) or "no pre-processing changes")
        for w in pre.get("warnings", []):
            ui.warn(w)
    with tab_area:
        ui.plot(plots.overlay_figure(app.processed, ch, show_points=st.checkbox("points", True, key="ov_pts"), dark=dark), key="overlay_fig", scroll_zoom=True)
        st.caption("Zoom with the mouse wheel / pan by dragging. Green = plot area, pink = detected ticks.")
        b = ch.box
        c1, c2, c3, c4, c5 = st.columns(5)
        x0 = c1.number_input("x0", value=float(b["x0"]), key="box_x0")
        y0 = c2.number_input("y0", value=float(b["y0"]), key="box_y0")
        x1 = c3.number_input("x1", value=float(b["x1"]), key="box_x1")
        y1 = c4.number_input("y1 (x-axis row)", value=float(b["y1"]), key="box_y1")
        rot = c5.number_input(t("rotation"), value=float((app.manual or {}).get("rotation", 0.0)), step=0.25, key="rot_in")
        if st.button(t("apply_rerun"), key="apply_box", type="primary"):
            m = _manual_panel(app, idx)
            m["panels"][str(idx)]["box"] = [x0, y0, x1, y1]
            m["rotation"] = rot
            rerun_manual(app, m)
            st.rerun()
        if ch.box and ch.box.get("method") == "fallback-margins":
            ui.warn("Plot area was guessed. Please correct it above.")
    with tab_cal:
        for w in ch.warnings:
            if "calibration" in w.lower() or "tick" in w.lower():
                ui.warn(w)
        m = _manual_panel(app, idx)
        pm_ = m["panels"][str(idx)]
        for axname, ax, label in (("x", ch.x_axis, "X"), ("y", ch.y_axis, "Y"), ("y2", ch.y2_axis, "Y2")):
            if ax is None:
                continue
            st.markdown(f"#### {label}")
            cal = ax.calibration
            if cal:
                st.caption(f"{cal.scale} | rmse={cal.rmse_px:.2f}px | confidence={cal.confidence:.2f} | source={cal.source} | ticks used={len(cal.refs)}")
            else:
                ui.warn(t("needs_calib"))
            c1, c2 = st.columns([3, 2])
            with c1:
                edited = _tick_table(ax, f"ticks_{axname}_{idx}")
            with c2:
                cur = (pm_.get(f"{axname}_scale") or "auto")
                sc = st.selectbox(t("scale_type"), SCALES, SCALES.index(cur) if cur in SCALES else 0, key=f"scale_{axname}_{idx}")
                st.caption("Or give the data values at the plot-area edges:")
                e1 = st.number_input("value at low edge" if axname == "x" else "value at bottom edge", value=0.0, key=f"edge1_{axname}_{idx}")
                e2 = st.number_input("value at high edge" if axname == "x" else "value at top edge", value=1.0, key=f"edge2_{axname}_{idx}")
                use_edges = st.checkbox("use edge values instead of ticks", False, key=f"useedge_{axname}_{idx}")
            pm_[f"{axname}_scale"] = None if sc == "auto" else sc
            valid = edited.dropna(subset=["pixel", "value"]) if edited is not None else pd.DataFrame()
            if sc == "datetime":
                txt = st.text_area("pixel; ISO date (one per line, e.g.  120; 2025-01-01)", "", key=f"dt_{axname}_{idx}")
                rows = [ln.split(";") for ln in txt.splitlines() if ";" in ln]
                if len(rows) >= 2:
                    pm_[f"{axname}_ticks"] = [[float(a), b.strip()] for a, b in rows]
                    valid = pd.DataFrame()
            if sc == "categorical":
                cats = st.text_input("categories left → right (comma separated)", "", key=f"cat_{axname}_{idx}")
                if cats.strip():
                    pm_[f"{axname}_categories"] = [c.strip() for c in cats.split(",") if c.strip()]
            if use_edges:
                pm_[f"{axname}_edges"] = [e1, e2]
                pm_.pop(f"{axname}_ticks", None)
            elif len(valid) >= 2:
                pm_[f"{axname}_ticks"] = [[float(a), float(b)] for a, b in zip(valid.pixel, valid.value)]
                pm_.pop(f"{axname}_edges", None)
        if st.button(t("apply_rerun"), key=f"apply_cal_{idx}", type="primary"):
            rerun_manual(app, m)
            st.rerun()
    with tab_info:
        for axname, ax in (("x", ch.x_axis), ("y", ch.y_axis), ("y2", ch.y2_axis)):
            if ax is None:
                continue
            c1, c2 = st.columns(2)
            ti = c1.text_input(f"{axname.upper()} title", ax.title or "", key=f"ti_{axname}_{idx}")
            un = c2.text_input(f"{axname.upper()} unit", ax.unit or "", key=f"un_{axname}_{idx}")
            if (ti or None) != ax.title or (un or None) != ax.unit:
                if st.button(f"{t('apply')} {axname.upper()}", key=f"apply_info_{axname}_{idx}"):
                    checkpoint(app, f"axis {axname} info")
                    ME.set_axis_info(app.state, ch, axname, ti, un)
                    commit(app, f"axis {axname} title/unit edited")
                    st.rerun()
        st.caption("Unknown titles / units stay 'unknown' in reports unless you enter them here - nothing is guessed.")
