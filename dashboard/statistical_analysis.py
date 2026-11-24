"""Page 7 - Statistical Analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from analysis import data_cleaning as DC
from analysis.mathematical_analysis import analyze_chart
from dashboard.components import plots, ui
from dashboard.i18n import t
from dashboard.session import commit


def render(app) -> None:
    st.title(t("nav_stats").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    dark = st.session_state.get("dark", False)
    if not ch.analysis:
        if st.button(t("run_analysis"), type="primary", key="sa_run"):
            analyze_chart(ch, dict(quick=True))
            commit(app, "analysis")
            st.rerun()
        st.info("Press 'Run analysis' (quick mode) or use the Mathematical Analysis page for the full run.")
        return
    an = ch.analysis["series"]
    rows = {}
    for s in ch.series:
        st_ = (an.get(s.name) or {}).get("stats")
        if st_:
            for k, v in st_["y"].items():
                rows.setdefault(k, {})[s.name] = v
    if rows:
        st.subheader("Descriptive statistics (Y)")
        ui.table(pd.DataFrame(rows).T.reset_index().rename(columns={"index": "statistic"}), key="sa_desc")
    c1, c2 = st.columns(2)
    names = [s.name for s in ch.series if s.kind not in ("pie",)]
    if names:
        pick = c1.selectbox(t("select_series"), names, key="sa_pick")
        s = ch.series_by_name(pick)
        sel, _ = DC.select_points(s.points)
        ui.plot(plots.histogram_figure(sel.y.to_numpy(), f"{pick}: Y distribution", dark), key="sa_hist")
        xy = (an.get(pick) or {}).get("stats", {}).get("xy", {})
        with c2:
            if xy.get("pearson_r") is not None:
                st.metric("Pearson r", f"{xy['pearson_r']:.4f}")
                st.metric("Spearman ρ", f"{xy['spearman_rho']:.4f}")
                st.metric("Kendall τ", f"{xy['kendall_tau']:.4f}")
                lr = xy["linear_regression"]
                st.write(f"linear regression: y = {lr['slope']:.5g}·x + {lr['intercept']:.5g}  (R² = {lr['r2']:.4f}; slope 95% CI [{lr['slope_ci95'][0]:.4g}, {lr['slope_ci95'][1]:.4g}])")
                (ui.warn(t("not_independent")) if not xy.get("independent_observations") else st.caption(xy.get("significance_note", "")))
    comp = next(iter((ch.analysis.get("comparison") or {}).values()), None)
    if comp and len(comp.get("per_series", {})) >= 2:
        st.subheader("Series comparison")
        ui.table(pd.DataFrame(comp["per_series"]).T.reset_index().rename(columns={"index": "series"}), key="sa_per")
        pairs = [p for p in comp["pairs"] if p.get("common_range")]
        if pairs:
            ui.table(pd.DataFrame(pairs).drop(columns=["common_range"], errors="ignore"), key="sa_pairs")
            nm = sorted({p["a"] for p in pairs} | {p["b"] for p in pairs})
            mat = pd.DataFrame(np.eye(len(nm)), index=nm, columns=nm)
            for p in pairs:
                if "pearson_r" in p:
                    mat.loc[p["a"], p["b"]] = mat.loc[p["b"], p["a"]] = p["pearson_r"]
            ui.plot(plots.heatmap_figure(mat, "Pearson correlation between series (common x-range)", dark), key="sa_heat")
        st.caption(comp["note"])
        for k, v in comp["ranking"].items():
            st.write(f"ranking by **{k}**: " + " > ".join(v))
    ix = ch.analysis.get("intersections") or []
    st.subheader("Intersections")
    (ui.table(pd.DataFrame(ix), key="sa_ix") if ix else st.caption(t("no_data")))
    st.subheader(t("quality"))
    q = ch.quality or {}
    if q.get("parts"):
        c1, c2 = st.columns([2, 1])
        with c1:
            ui.plot(plots.quality_figure(q["parts"], dark), key="sa_q")
        with c2:
            ui.card(t("quality"), q.get("overall"), q.get("grade"))
    un = ch.analysis.get("uncertainty") or []
    if un:
        ui.table(pd.DataFrame(un), key="sa_unc")
