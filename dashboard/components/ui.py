"""Small UI helpers (cards, tables, plot wrappers) that tolerate Streamlit API differences."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from core.ocr_engine import ocr_status
from dashboard.i18n import t


def plot(fig, key: str | None = None, scroll_zoom: bool = False) -> None:
    cfg = {"scrollZoom": scroll_zoom, "displaylogo": False, "responsive": True}
    try:
        st.plotly_chart(fig, width="stretch", config=cfg, key=key)
    except Exception:  # older Streamlit versions do not know width='stretch'
        st.plotly_chart(fig, use_container_width=True, config=cfg, key=key)


def table(df: pd.DataFrame, height: int | None = None, key: str | None = None) -> None:
    kw = dict(hide_index=True, key=key)
    if height:
        kw["height"] = height
    try:
        st.dataframe(df, width="stretch", **kw)
    except Exception:
        st.dataframe(df, use_container_width=True, **kw)


def editor(df: pd.DataFrame, key: str, **kw):
    try:
        return st.data_editor(df, width="stretch", key=key, **kw)
    except Exception:
        return st.data_editor(df, use_container_width=True, key=key, **kw)


def image(arr, caption: str | None = None) -> None:
    try:
        st.image(arr, caption=caption, width="stretch")
    except Exception:
        st.image(arr, caption=caption, use_container_width=True)


def card(label: str, value, sub: str = "") -> None:
    st.markdown(f'<div class="gi-card"><div class="l">{label}</div><div class="v">{value}</div><div class="l">{sub}</div></div>', unsafe_allow_html=True)


def warn(msg: str) -> None:
    st.markdown(f'<div class="gi-warn">⚠ {msg}</div>', unsafe_allow_html=True)


def ok(msg: str) -> None:
    st.markdown(f'<div class="gi-ok">✔ {msg}</div>', unsafe_allow_html=True)


def sample_badge() -> None:
    st.markdown(f'<span class="gi-sample">{t("sample_data")}</span>', unsafe_allow_html=True)


def ocr_banner(lang: str = "eng") -> None:
    s = ocr_status(lang)
    if not s["available"]:
        warn(t("ocr_missing"))
        st.code(s["hint"])


def need_project(app) -> bool:
    if app.state is None or not app.state.charts:
        st.info(t("no_project"))
        return False
    return True


def chart_selector(app, key: str = "panel_sel"):
    """Panel selector for multi-panel images; returns the active ChartResult."""
    st_ = app.state
    if len(st_.charts) > 1:
        labels = [f"{t('panel')} {c.panel_index + 1} — {c.chart_type}" for c in st_.charts]
        i = st.selectbox(t("panel"), range(len(st_.charts)), format_func=lambda k: labels[k], index=min(st_.active_chart, len(st_.charts) - 1), key=key)
        st_.active_chart = int(i)
    return st_.chart
