"""Page 8 - Visualization: rebuild the original chart / create new charts from the extracted data."""
from __future__ import annotations

import streamlit as st

from dashboard.components import plots, ui
from dashboard.i18n import t
from exporters import chart_exporter as CE


def render(app) -> None:
    st.title(t("nav_viz").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    dark = st.session_state.get("dark", False)
    names = [s.name for s in ch.series]
    if not names:
        st.info(t("no_data"))
        return
    left, right = st.columns([3, 2])
    with right:
        o: dict = {}
        o["title"] = st.text_input("Title", ch.title or "", key="vz_title") or None
        o["xlabel"] = st.text_input("X label", ch.x_axis.display_name if ch.x_axis else "X", key="vz_xl")
        o["ylabel"] = st.text_input("Y label", ch.y_axis.display_name if ch.y_axis else "Y", key="vz_yl")
        if ch.y2_axis is not None:
            o["y2label"] = st.text_input("Y2 label", ch.y2_axis.display_name, key="vz_y2l")
        o["visible"] = st.multiselect(t("series"), names, default=names, key="vz_vis")
        with st.expander(t("color")):
            o["colors"] = {n: st.color_picker(n, ch.series_by_name(n).hex_color, key=f"vz_col_{n}") for n in names}
        c1, c2 = st.columns(2)
        o["lw"] = c1.slider("line width", 0.5, 6.0, 2.0, 0.5, key="vz_lw")
        o["ms"] = c2.slider("marker size", 2, 16, 6, key="vz_ms")
        o["legend"] = st.checkbox("legend", True, key="vz_leg")
        o["grid"] = st.checkbox("grid", True, key="vz_grid")
        c3, c4 = st.columns(2)
        cx = ch.x_axis.calibration if ch.x_axis else None
        cy = ch.y_axis.calibration if ch.y_axis else None
        o["logx"] = c3.checkbox("log X", bool(cx and cx.scale in ("log10", "log2", "ln")), key="vz_lx")
        o["logy"] = c4.checkbox("log Y", bool(cy and cy.scale in ("log10", "log2", "ln")), key="vz_ly")
        if st.checkbox("custom axis ranges", False, key="vz_rng"):
            xs = [v for s in ch.series for v in s.points.x.dropna()]
            ys = [v for s in ch.series for v in s.points.y.dropna()]
            if xs and ys:
                a, b = st.slider("X range", float(min(xs)), float(max(xs)), (float(min(xs)), float(max(xs))), key="vz_xr")
                c, d = st.slider("Y range", float(min(ys)), float(max(ys)), (float(min(ys)), float(max(ys))), key="vz_yr")
                o["xlim"], o["ylim"] = [a, b], [c, d]
        o["dark"] = dark
    with left:
        ui.plot(plots.reconstruction_figure(ch, o, dark), key="vz_fig")
        st.caption("Points: lines = reconstructed centre-line, circles = real markers. Fully editable via the options on the side.")
    st.subheader(t("download"))
    mo = {k: v for k, v in o.items() if k != "dark"}
    mo["dark"] = dark
    d1, d2, d3 = st.columns(3)
    for col, fmt in ((d1, "png"), (d2, "svg"), (d3, "pdf")):
        fig = CE.fig_reconstruction(ch, opts=mo)
        col.download_button(f"⬇ {fmt.upper()}", CE.fig_bytes(fig, fmt, 200), file_name=f"{app.state.name}_chart.{fmt}", mime={"png": "image/png", "svg": "image/svg+xml", "pdf": "application/pdf"}[fmt], key=f"vz_dl_{fmt}")
