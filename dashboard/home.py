"""Page 1 - Overview."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.components import ui
from dashboard.i18n import t
from dashboard.session import open_project


def render(app) -> None:
    st.title("GraphInsight AI")
    st.caption(t("app_tagline"))
    stats = app.pm.db.stats()
    c = st.columns(6)
    items = [(t("projects"), stats["projects"]), (t("images_done"), stats["projects"]), (t("charts_found"), stats["charts"]),
             (t("series_count"), stats["series"]), (t("points_count"), f"{stats['points']:,}"), (t("fits_count"), stats["fits"])]
    for col, (label, value) in zip(c, items):
        with col:
            ui.card(label, value)
    st.write("")
    left, right = st.columns([3, 2])
    with left:
        st.subheader(t("recent_projects"))
        projects = app.pm.list()[:10]
        if not projects:
            st.info(t("no_project"))
        else:
            df = pd.DataFrame([dict(name=p["name"], image=p["image_name"], chart=p["chart_type"], series=p["n_series"], points=p["n_points"],
                                    quality=p["quality"], updated=p["updated"]) for p in projects])
            ui.table(df, key="home_recent")
            names = {p["id"]: f"{p['name']}  ({p['updated']})" for p in projects}
            pid = st.selectbox(t("open"), list(names), format_func=lambda k: names[k], key="home_open_sel")
            if st.button(t("open"), key="home_open_btn"):
                open_project(app, pid)
                st.toast(t("ok_saved"))
                st.rerun()
    with right:
        st.subheader(t("last_events"))
        ev = app.pm.db.recent_events(10)
        if ev:
            ui.table(pd.DataFrame(ev), key="home_events")
        else:
            st.caption(t("no_data"))
    if app.state is not None and app.chart is not None:
        st.divider()
        ch = app.chart
        st.subheader(f"{t('active_project')}: {app.state.name}")
        q = ch.quality or {}
        a, b, c3 = st.columns(3)
        with a:
            ui.card(t("chart_type"), ch.chart_type, f"p = {ch.type_confidence:.2f}")
        with b:
            ui.card(t("series_count"), len(ch.series), ", ".join(s.name for s in ch.series)[:60])
        with c3:
            ui.card(t("quality"), q.get("overall", "—"), q.get("grade", ""))
        for w in ch.warnings:
            ui.warn(w)
