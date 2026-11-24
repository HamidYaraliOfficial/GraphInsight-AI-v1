"""Page 9 - Reports: generate and download Word / Excel / PDF / CSV / JSON / PNG / SVG / TXT / ZIP."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.components import ui
from dashboard.i18n import t
from dashboard.session import commit, progress_cb
from exporters.export_manager import ALL_FORMATS, export_all

MIME = {".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".pdf": "application/pdf", ".csv": "text/csv",
        ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml", ".txt": "text/plain", ".zip": "application/zip"}


def render(app) -> None:
    st.title(t("nav_reports").split("(")[0])
    if not ui.need_project(app):
        return
    c1, c2 = st.columns([1, 2])
    lang = c1.radio(t("language_report"), ["fa", "en"], index=0 if app.settings.report_lang == "fa" else 1, horizontal=True, key="rp_lang")
    app.settings.report_lang = lang
    fmts = c2.multiselect(t("formats"), ALL_FORMATS, default=["docx", "xlsx", "pdf", "csv", "json", "png", "zip"], key="rp_fmts")
    st.caption("Word, Excel, PDF, CSV, JSON, PNG/SVG, TXT and ZIP. Persian PDF needs arabic-reshaper + python-bidi (installed by requirements.txt) "
               "or LibreOffice; otherwise an English PDF is produced.")
    if st.button(t("generate"), type="primary", key="rp_go"):
        cb, bar = progress_cb()
        outdir = app.pm.outputs_dir(app.state.project_id)
        made = export_all(app.state, outdir, fmts, lang, app.original, app.processed, progress=cb)
        bar.empty()
        commit(app, "reports generated: " + ", ".join(fmts))
        app.pm.db.add_event(app.state.project_id, "export", ", ".join(fmts))
        err = made.pop("_errors", None)
        st.session_state["rp_made"] = made
        if err:
            ui.warn(err)
        else:
            ui.ok(t("done"))
    made = st.session_state.get("rp_made") or {}
    if made:
        zips = [p for k, p in made.items() if k.endswith("all_outputs.zip")]
        if zips:
            st.download_button("⬇ " + t("download_all"), Path(zips[0]).read_bytes(), file_name=Path(zips[0]).name, mime="application/zip", key="rp_dl_zip")
        for i, (label, p) in enumerate(sorted(made.items())):
            p = Path(p)
            if not p.exists() or p.suffix == ".zip":
                continue
            c1, c2 = st.columns([4, 1])
            c1.write(f"📄 {p.name}  ({p.stat().st_size // 1024} KB)")
            c2.download_button(t("download"), p.read_bytes(), file_name=p.name, mime=MIME.get(p.suffix, "application/octet-stream"), key=f"rp_dl_{i}")
