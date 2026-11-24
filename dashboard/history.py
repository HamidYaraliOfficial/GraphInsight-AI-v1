"""Page 10 - Project History: list / open / copy / delete / ZIP export and import."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.components import ui
from dashboard.i18n import t
from dashboard.session import open_project


def render(app) -> None:
    st.title(t("nav_history").split("(")[0])
    q = st.text_input(t("search_projects"), key="hs_q")
    projects = app.pm.list(q or None)
    if projects:
        df = pd.DataFrame([dict(name=p["name"], image=p["image_name"], chart=p["chart_type"], series=p["n_series"], points=p["n_points"],
                                quality=p["quality"], sample=bool(p["is_sample"]), created=p["created"], updated=p["updated"], id=p["id"]) for p in projects])
        ui.table(df, key="hs_table")
        names = {p["id"]: f"{p['name']} — {p['updated']}" for p in projects}
        pid = st.selectbox(t("open"), list(names), format_func=lambda k: names[k], key="hs_sel")
        c1, c2, c3, c4 = st.columns(4)
        if c1.button(t("open"), key="hs_open", type="primary"):
            open_project(app, pid)
            st.toast(t("ok_saved"))
            st.rerun()
        if c2.button(t("copy"), key="hs_copy"):
            app.pm.copy(pid)
            st.rerun()
        if c3.button(t("delete"), key="hs_del"):
            app.pm.delete(pid)
            if app.state is not None and app.state.project_id == pid:
                app.state = None
            st.rerun()
        with tempfile.TemporaryDirectory() as td:
            z = app.pm.export_zip(pid, Path(td) / f"{pid}.zip")
            c4.download_button("⬇ " + t("export_zip"), Path(z).read_bytes(), file_name=f"graphinsight_{pid}.zip", mime="application/zip", key="hs_zip")
        st.subheader("Log")
        ev = app.pm.db.list_events(pid, 50)
        if ev:
            ui.table(pd.DataFrame(ev)[["ts", "kind", "detail"]], key="hs_events")
        p = app.pm.db.get_project(pid)
        if p and app.state is not None and app.state.project_id == pid:
            with st.expander("Processing log"):
                st.code("\n".join(app.state.processing_log[-200:]))
    else:
        st.info(t("no_data"))
    st.divider()
    st.subheader(t("import_zip"))
    up = st.file_uploader("ZIP", type=["zip"], key="hs_import")
    if up is not None and st.button(t("import_zip"), key="hs_import_btn"):
        with tempfile.TemporaryDirectory() as td:
            zp = Path(td) / "in.zip"
            zp.write_bytes(up.getvalue())
            try:
                new = app.pm.import_zip(zp)
                open_project(app, new)
                ui.ok(t("done"))
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))
