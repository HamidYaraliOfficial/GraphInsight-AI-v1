"""GraphInsight AI - Streamlit entry point.

Run:  streamlit run app.py      (or use run.bat / run.sh)
Developer: Hamid Yarali (حمید یارعلی)
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st  # noqa: E402

from config import constants as C  # noqa: E402
from config.logging_config import setup_logging  # noqa: E402
from config.settings import ensure_dirs  # noqa: E402

st.set_page_config(page_title=f"{C.APP_NAME}", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
ensure_dirs()
setup_logging()

from dashboard import (data_explorer, digitization, history, home, image_processing, mathematical_analysis,  # noqa: E402
                       reports, statistical_analysis, upload, visualization)
from dashboard.i18n import PAGES, t  # noqa: E402
from dashboard.session import get_app, redo, undo  # noqa: E402
from dashboard.theme import apply_theme, logo_svg  # noqa: E402

PAGE_FUNCS = {"overview": home.render, "new": upload.render, "imgproc": image_processing.render, "digitize": digitization.render,
              "explorer": data_explorer.render, "math": mathematical_analysis.render, "stats": statistical_analysis.render,
              "viz": visualization.render, "reports": reports.render, "history": history.render}


def main() -> None:
    app = get_app()
    st.session_state.setdefault("lang", "fa")
    st.session_state.setdefault("dark", False)
    with st.sidebar:
        st.markdown(f"<div style='display:flex;align-items:center;gap:10px'>{logo_svg(st.session_state['dark'])}"
                    f"<div><b style='font-size:1.25rem'>{C.APP_NAME}</b><br><span style='font-size:.8rem;opacity:.75'>v{C.APP_VERSION}</span></div></div>",
                    unsafe_allow_html=True)
        lang_label = st.radio(t("language"), ["فارسی", "English"], index=0 if st.session_state["lang"] == "fa" else 1, horizontal=True, key="lang_radio")
        st.session_state["lang"] = "fa" if lang_label == "فارسی" else "en"
        st.session_state["dark"] = st.toggle(t("theme_dark"), value=st.session_state["dark"], key="dark_toggle")
        choice = st.radio("nav", PAGES, format_func=lambda k: t("nav_" + {"overview": "overview", "new": "new", "imgproc": "imgproc", "digitize": "digitize",
                                                                          "explorer": "explorer", "math": "math", "stats": "stats", "viz": "viz",
                                                                          "reports": "reports", "history": "history"}[k]),
                          label_visibility="collapsed", key="nav_choice")
        st.divider()
        if app.state is not None:
            st.caption(f"{t('active_project')}: **{app.state.name}**")
            if app.state.is_sample:
                st.markdown(f"<span class='gi-sample'>{t('sample_data')}</span>", unsafe_allow_html=True)
        else:
            st.caption(t("no_project"))
        u1, u2 = st.columns(2)
        if u1.button(t("undo"), disabled=not app.history.can_undo, key="btn_undo"):
            lab = undo(app)
            st.toast(f"{t('undo_done')}: {lab}" if lab else t("nothing_undo"))
            st.rerun()
        if u2.button(t("redo"), disabled=not app.history.can_redo, key="btn_redo"):
            lab = redo(app)
            st.toast(f"{t('redo_done')}: {lab}" if lab else "")
            st.rerun()
        st.divider()
        st.caption(f"{t('created_by')}  ·  {C.DEFAULT_URL}")
    apply_theme(rtl=st.session_state["lang"] == "fa", dark=st.session_state["dark"])
    try:
        PAGE_FUNCS[choice](app)
    except Exception as exc:  # noqa: BLE001 - show a readable message instead of a stack trace
        from config.logging_config import get_logger
        get_logger("app").exception("page %s failed", choice)
        st.error(f"{t('failed')}: {exc}")
        st.caption("Technical details were written to data/logs/graphinsight.log. You can retry, change the settings or correct the image manually.")


main()
