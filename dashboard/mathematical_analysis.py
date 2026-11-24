"""Page 6 - Mathematical Analysis."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from analysis import curve_fitting as CF
from analysis import data_cleaning as DC
from analysis import integral_analysis as IA
from analysis.mathematical_analysis import analyze_chart
from dashboard.components import plots, ui
from dashboard.i18n import t
from dashboard.session import commit, progress_cb


def render(app) -> None:
    st.title(t("nav_math").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    dark = st.session_state.get("dark", False)
    fams = CF.DEFAULT_FAMILIES
    lib = CF.library()
    label = {f: (lib[f].name if f in lib else {"piecewise2": "Piecewise (2)", "piecewise3": "Piecewise (3)", "spline": "Spline"}.get(f, f)) for f in fams}
    with st.expander(t("settings"), expanded=not bool(ch.analysis)):
        c1, c2 = st.columns(2)
        with c1:
            chosen = st.multiselect(t("models"), fams, default=fams, format_func=lambda k: label[k], key="ma_fams")
            custom = st.text_input("Custom model in x (e.g.  a*x**2 + b*sin(c*x) )", "", key="ma_custom")
        with c2:
            src = st.selectbox("Fit source", ["auto", "markers", "dense"], key="ma_src")
            dm = st.selectbox("Derivative method", ["spline", "savgol", "finite"], key="ma_dm")
            interp_inc = st.checkbox("include interpolated points", False, key="ma_interp")
        if st.button(t("run_analysis"), type="primary", key="ma_run"):
            cb, bar = progress_cb()
            analyze_chart(ch, dict(families=chosen, custom=[custom] if custom.strip() else [], fit_source=src, deriv_method=dm, include_interpolated=interp_inc), cb)
            bar.empty()
            commit(app, "mathematical analysis")
            st.rerun()
    if not ch.analysis:
        st.info("Press 'Run analysis'.")
        return
    ui.warn(t("approx_note"))
    series = [s for s in ch.series if (ch.analysis["series"].get(s.name) or {}).get("fits")]
    if not series:
        st.info(t("no_data"))
        return
    tabs = st.tabs([s.name for s in series])
    for tab, s in zip(tabs, series):
        a = ch.analysis["series"][s.name]
        with tab:
            fm = a["fits"]
            st.caption(f"fit source: {a.get('fit_source')} — n = {a.get('n_used')}")
            rows = [dict(rank=i + 1, model=m["name"], k=m["n_params"], R2=m["metrics"]["r2"], adjR2=m["metrics"]["adj_r2"], RMSE=m["metrics"]["rmse"],
                         MAE=m["metrics"]["mae"], AIC=m["metrics"]["aic"], BIC=m["metrics"]["bic"], CV_RMSE=m["metrics"].get("cv_rmse"),
                         selected="✔" if m["name"] == fm["best"] else "") for i, m in enumerate(fm["models"])]
            ui.table(pd.DataFrame(rows), key=f"ma_models_{s.name}")
            for n in fm["notes"]:
                st.caption(n)
            names = [m["name"] for m in fm["models"]]
            pick = st.multiselect(t("compare_models"), names, default=[fm["best"]] + [n for n in names[:2] if n != fm["best"]], key=f"ma_pick_{s.name}")
            fig = plots.fit_figure(ch, s.name, pick, dark)
            if fig is not None:
                ui.plot(fig, key=f"ma_fit_{s.name}")
            best = next(m for m in fm["models"] if m["name"] == (pick[0] if pick else fm["best"]))
            st.markdown(f"**{t('equations')} — {best['name']}**")
            try:
                st.latex(best["equation"]["latex"])
            except Exception:  # noqa: BLE001
                st.code(best["equation"]["text"])
            st.code(best["equation"]["text"], language="text")
            c1, c2 = st.columns(2)
            c1.code(best["equation"]["python"], language="python")
            c2.code(best["equation"]["excel"], language="text")
            ui.table(pd.DataFrame([dict(parameter=k, value=v["value"], std_error=v.get("stderr"), ci95_low=v.get("ci_low"), ci95_high=v.get("ci_high"))
                                   for k, v in best["params"].items()]), key=f"ma_params_{s.name}")
            for w in best["warnings"]:
                st.caption("• " + w)
            sel, _ = DC.select_points(s.points, "auto")
            x, y, _ = DC.clean_xy(sel)
            if best["x_fit"]:
                yhat = np.interp(x, best["x_fit"], best["y_fit"])
                ui.plot(plots.residual_figure(x, y - yhat, dark), key=f"ma_res_{s.name}")
            st.markdown(f"**{t('derivative')}**")
            dfig = plots.derivative_figure(a, dark)
            if dfig is not None:
                ui.plot(dfig, key=f"ma_der_{s.name}")
                d = a["derivative"]
                infl = ", ".join("%.4g" % p["x"] for p in d["inflection_points"]) or "-"
                st.caption("max slope %.5g @ x=%.5g; min slope %.5g @ x=%.5g; inflection points: %s" % (
                    d["max_slope"]["value"], d["max_slope"]["x"], d["min_slope"]["value"], d["min_slope"]["x"], infl))
                st.caption(d["note"])
            st.markdown(f"**{t('integral')}**")
            lo, hi = float(x.min()), float(x.max())
            c1, c2 = st.columns(2)
            a_ = c1.number_input("from x", value=lo, key=f"ma_a_{s.name}", format="%.6g")
            b_ = c2.number_input("to x", value=hi, key=f"ma_b_{s.name}", format="%.6g")
            g = IA.integrate_series(x, y, a_, b_)
            if g.get("ok"):
                st.write(f"∫ y dx  =  **{g['trapezoid']:.6g}** (trapezoid), **{g['simpson']:.6g}** (Simpson); |area| = {g['abs_area']:.6g}")
            ft = a.get("features") or {}
            if ft:
                st.markdown("**" + t("equations").replace("معادلات", "نقاط بحرانی") + " / critical points**")
                tp = pd.DataFrame(ft.get("turning_points", []))
                if len(tp):
                    ui.table(tp, key=f"ma_tp_{s.name}")
                zc = ", ".join("%.4g" % v for v in ft.get("zero_crossings", [])) or "-"
                st.write("monotonicity: **%s**; plateaus: %d; zero crossings: %s" % (ft.get("monotonicity"), len(ft.get("plateaus", [])), zc))
                if ft.get("convexity_segments"):
                    ui.table(pd.DataFrame(ft["convexity_segments"]), key=f"ma_cv_{s.name}")
            mt = a.get("metrics") or {}
            if mt:
                st.json(mt, expanded=False)
