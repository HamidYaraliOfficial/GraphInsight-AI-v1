"""Page 4 - Chart Digitization: inspect and correct the extracted series and points."""
from __future__ import annotations

import numpy as np
import streamlit as st

from analysis import data_cleaning as DC
from config import constants as C
from core import manual_edit as ME
from core.pipeline import redigitize_chart, reextract_series_by_color
from dashboard.components import plots, ui
from dashboard.i18n import t
from dashboard.session import checkpoint, commit


def _hex_to_rgb(h: str) -> tuple:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def render(app) -> None:
    st.title(t("nav_digitize").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    dark = st.session_state.get("dark", False)
    if not ch.series:
        ui.warn(t("no_data"))
    left, right = st.columns([3, 2])
    with left:
        ui.plot(plots.overlay_figure(app.processed, ch, dark=dark, height=520), key="dig_overlay", scroll_zoom=True)
        for w in ch.warnings:
            ui.warn(w)
    names = [s.name for s in ch.series]
    with right:
        if not names:
            sel = None
        else:
            sel = st.selectbox(t("select_series"), names, key="dig_sel")
        s = ch.series_by_name(sel) if sel else None
        if s is not None:
            st.markdown(f"<span class='gi-badge'>{s.kind}</span><span class='gi-badge'>axis {s.axis}</span>"
                        f"<span class='gi-badge'>{t('quality')}: {s.confidence:.2f}</span>", unsafe_allow_html=True)
            st.caption(", ".join(f"{k}: {v}" for k, v in s.n_by_status().items()))
            for w in s.warnings:
                ui.warn(w)
            n1, n2 = st.columns(2)
            new_name = n1.text_input(t("rename"), s.name, key=f"rn_{sel}")
            new_col = n2.color_picker(t("color"), s.hex_color, key=f"col_{sel}")
            if st.button(f"{t('apply')} ({t('rename')} / {t('color')})", key=f"apply_name_{sel}"):
                checkpoint(app, f"rename/colour {sel}")
                if new_name != s.name:
                    ME.rename_series(app.state, ch, s.name, new_name)
                ME.set_series_color(app.state, ch, new_name if new_name != s.name else s.name, _hex_to_rgb(new_col))
                commit(app, "series renamed / recoloured")
                st.rerun()
            if ch.y2_axis is not None:
                ax_sel = st.radio("Y axis", ["y", "y2"], index=0 if s.axis == "y" else 1, horizontal=True, key=f"axsel_{sel}")
                if ax_sel != s.axis and st.button(t("apply"), key=f"axapply_{sel}"):
                    checkpoint(app, f"axis of {sel}")
                    ME.set_series_axis(app.state, ch, s.name, ax_sel)
                    commit(app, "series axis changed")
                    st.rerun()
            if st.button("🎯 " + t("redigitize").replace("با این تنظیمات", "") + " (" + t("color") + ")", key=f"recolor_{sel}"):
                checkpoint(app, f"re-extract colour {sel}")
                ok = reextract_series_by_color(app.state, app.processed, ch.panel_index, s.name, _hex_to_rgb(new_col), app.settings)
                (commit(app, "series re-extracted by colour") if ok else None)
                (st.rerun() if ok else ui.warn("No pixels found for this colour."))
    st.divider()
    st.subheader(t("settings"))
    c1, c2, c3, c4, c5 = st.columns(5)
    app.settings.n_points = int(c1.number_input(t("n_points"), 10, 5000, int(app.settings.n_points), 10, key="dg_npts"))
    app.settings.sampling = c2.selectbox(t("sampling"), ["adaptive", "uniform_x", "uniform_arc"], ["adaptive", "uniform_x", "uniform_arc"].index(app.settings.sampling), key="dg_samp")
    app.settings.curvature_weight = float(c3.slider("curvature weight", 0.0, 12.0, float(app.settings.curvature_weight), 0.5, key="dg_cw"))
    app.settings.color_tolerance = float(c4.slider("colour tolerance", 8.0, 50.0, float(app.settings.color_tolerance), 1.0, key="dg_tol"))
    app.settings.dense_mode = c5.checkbox("dense", app.settings.dense_mode, key="dg_dense")
    b1, b2 = st.columns(2)
    if b1.button(t("redigitize"), type="primary", key="dg_redo"):
        checkpoint(app, "re-digitise")
        redigitize_chart(app.state, app.processed, ch.panel_index, app.settings)
        commit(app, "re-digitised")
        st.rerun()
    if s is not None and b2.button("🧹 remove outlier points (robust z > 6)", key="dg_out"):
        sp = s.sorted_points().dropna(subset=["x", "y"])
        mask = DC.flag_outliers(sp.x.to_numpy(), sp.y.to_numpy())
        if mask.any():
            checkpoint(app, f"remove outliers {s.name}")
            ME.delete_points(app.state, ch, s.name, sp.idx[mask].tolist())
            commit(app, "outliers removed")
            st.rerun()
        else:
            st.info("No outliers found.")
    if s is None:
        return
    st.subheader(f"{s.name} — points")
    tab_edit, tab_add, tab_del = st.tabs([t("apply_edits"), t("add_point"), t("delete_points")])
    with tab_edit:
        st.caption("Edit X / Y cells or add rows; edited and new points get the status 'manual' (confidence 1.0).")
        df = s.sorted_points()
        edited = ui.editor(df, key=f"ped_{s.name}_{len(s.points)}", num_rows="dynamic", disabled=["px", "py", "status", "confidence", "method"])
        if st.button(t("apply_edits"), key=f"ped_apply_{s.name}", type="primary"):
            checkpoint(app, f"table edit {s.name}")
            res = ME.apply_table_edits(app.state, ch, s.name, edited)
            commit(app, "points edited")
            st.toast(f"{res}")
            st.rerun()
    with tab_add:
        a, b = st.columns(2)
        xv = a.number_input("X", value=0.0, format="%.6g", key=f"addx_{s.name}")
        yv = b.number_input("Y", value=0.0, format="%.6g", key=f"addy_{s.name}")
        if st.button(t("add_point"), key=f"addbtn_{s.name}"):
            checkpoint(app, f"add point {s.name}")
            ME.add_point(app.state, ch, s.name, xv, yv)
            commit(app, "point added")
            st.rerun()
    with tab_del:
        status_sel = st.multiselect(t("filter_status"), list(C.POINT_STATUSES), key=f"delst_{s.name}")
        cand = s.points[s.points.status.isin(status_sel)] if status_sel else s.points
        idxs = st.multiselect("idx", cand.idx.astype(int).tolist(), key=f"delidx_{s.name}")
        if st.button(t("delete_points"), key=f"delbtn_{s.name}", disabled=not idxs):
            checkpoint(app, f"delete points {s.name}")
            ME.delete_points(app.state, ch, s.name, [float(i) for i in idxs])
            commit(app, "points deleted")
            st.rerun()
