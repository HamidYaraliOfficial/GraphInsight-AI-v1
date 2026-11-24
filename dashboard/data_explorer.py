"""Page 5 - Data Explorer: interactive table with search, filter, sort, column selection, copy, download."""
from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from config import constants as C
from dashboard.components import ui
from dashboard.i18n import t
from exporters.csv_exporter import combined_frame
from exporters.excel_exporter import export_excel


def render(app) -> None:
    st.title(t("nav_explorer").split("(")[0])
    if not ui.need_project(app):
        return
    ch = ui.chart_selector(app)
    df = combined_frame(ch)
    if df.empty:
        st.info(t("no_data"))
        return
    c1, c2, c3 = st.columns(3)
    q = c1.text_input(t("search"), key="dx_search")
    sers = c2.multiselect(t("series"), sorted(df.series.unique()), default=sorted(df.series.unique()), key="dx_series")
    stat = c3.multiselect(t("filter_status"), list(C.POINT_STATUSES), default=[s for s in C.POINT_STATUSES if s in set(df.status)], key="dx_status")
    cols = st.multiselect(t("columns"), list(df.columns), default=list(df.columns), key="dx_cols")
    f = df[df.series.isin(sers) & df.status.isin(stat)]
    if q:
        mask = f.astype(str).apply(lambda col: col.str.contains(q, case=False, regex=False)).any(axis=1)
        f = f[mask]
    f = f[cols] if cols else f
    st.caption(f"{len(f):,} / {len(df):,} rows — click the column headers to sort.")
    ui.table(f, height=460, key="dx_table")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ CSV", f.to_csv(index=False).encode("utf-8-sig"), file_name=f"{app.state.name}_data.csv", mime="text/csv", key="dx_csv")
    with tempfile.TemporaryDirectory() as td:
        xp = export_excel(app.state, Path(td) / "data.xlsx")
        d2.download_button("⬇ Excel", Path(xp).read_bytes(), file_name=f"{app.state.name}_data.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dx_xlsx")
    with d3.expander(t("copy_data")):
        st.code(f.head(500).to_csv(sep="\t", index=False), language="text")
    st.info("To change values use 'Chart Digitization' → table editing (changes are tracked with undo/redo and marked as manual).")
