"""Page 2 - New Analysis (upload, preview, extraction settings, automatic analysis)."""
from __future__ import annotations

import io
from pathlib import Path

import streamlit as st
from PIL import Image

from config import constants as C
from config import settings as cfg
from core.image_loader import ImageLoadError, load_image, load_image_bytes
from core.pdf_processor import count_pages, render_thumbnails
from dashboard.components import ui
from dashboard.i18n import t
from dashboard.session import run_analysis
from models.chart_types import chart_keys, chart_label

SCALES = ["auto", "linear", "log10", "log2", "ln"]


def _settings_form(app) -> None:
    s = app.settings
    with st.expander(t("settings"), expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            s.ocr_lang = st.text_input("OCR language (Tesseract, e.g. eng or eng+fas)", s.ocr_lang, key="set_ocr_lang")
            s.denoise = st.checkbox("Denoise", s.denoise, key="set_denoise")
            s.deskew = st.checkbox("Deskew / rotation fix", s.deskew, key="set_deskew")
            s.enhance_contrast = st.checkbox("Contrast / background correction", s.enhance_contrast, key="set_contrast")
            s.upscale_small = st.checkbox("Upscale small images", s.upscale_small, key="set_upscale")
        with c2:
            s.detect_panels = st.checkbox("Detect multiple panels", s.detect_panels, key="set_panels")
            s.remove_grid = st.checkbox("Remove grid lines", s.remove_grid, key="set_grid")
            s.detect_error_bars = st.checkbox("Detect error bars", s.detect_error_bars, key="set_err")
            s.detect_bands = st.checkbox("Detect shaded bands", s.detect_bands, key="set_band")
            s.dense_mode = st.checkbox("Dense curve digitization", s.dense_mode, key="set_dense")
        with c3:
            s.n_points = int(st.number_input(t("n_points"), 10, 5000, int(s.n_points), 10, key="set_npts"))
            s.sampling = st.selectbox(t("sampling"), ["adaptive", "uniform_x", "uniform_arc"], ["adaptive", "uniform_x", "uniform_arc"].index(s.sampling), key="set_sampling")
            s.color_tolerance = float(st.slider("Colour tolerance (Lab ΔE)", 8.0, 50.0, float(s.color_tolerance), 1.0, key="set_tol"))
            s.max_gap_px = int(st.number_input("Max gap bridged (px)", 0, 200, int(s.max_gap_px), key="set_gap"))
            s.curve_mode = st.selectbox("Curve mode", ["auto", "function", "parametric", "step"], ["auto", "function", "parametric", "step"].index(s.curve_mode), key="set_cmode")
        c4, c5, c6 = st.columns(3)
        with c4:
            keys = ["auto"] + chart_keys()
            s.chart_type = st.selectbox(t("override_type"), keys, keys.index(s.chart_type) if s.chart_type in keys else 0,
                                        format_func=lambda k: "auto" if k == "auto" else chart_label(k, "fa" if st.session_state.get("lang", "fa") == "fa" else "en"), key="set_ctype")
        with c5:
            s.x_scale = st.selectbox("X scale", SCALES, SCALES.index(s.x_scale) if s.x_scale in SCALES else 0, key="set_xs")
        with c6:
            s.y_scale = st.selectbox("Y scale", SCALES, SCALES.index(s.y_scale) if s.y_scale in SCALES else 0, key="set_ys")


def _show_result(app) -> None:
    ch = app.chart
    ui.ok(t("done"))
    st.write(f"**{app.state.name}** — {ch.chart_type} — {len(ch.series)} {t('series_count')} — "
             f"{sum(len(s.points) for s in ch.series)} {t('points_count')}")
    for w in ch.warnings:
        ui.warn(w)


def render(app) -> None:
    st.title(t("nav_new").split("(")[0])
    ui.ocr_banner(app.settings.ocr_lang)
    tab_up, tab_sample = st.tabs([t("upload_files").split("(")[0], t("try_sample")])
    with tab_up:
        files = st.file_uploader(t("upload_files"), type=[e.lstrip(".") for e in C.SUPPORTED_EXT], accept_multiple_files=True,
                                 help=t("drag_hint"), key="uploader")
        pdf_pages: dict[str, int] = {}
        if files:
            cols = st.columns(min(len(files), 4))
            for i, f in enumerate(files):
                data = f.getvalue()
                with cols[i % len(cols)]:
                    try:
                        if f.name.lower().endswith(".pdf"):
                            n = count_pages(data)
                            pdf_pages[f.name] = int(st.number_input(f"{f.name} — {t('pdf_page')} (1–{n})", 1, max(n, 1), 1, key=f"pdfpage_{i}")) - 1
                            thumbs = render_thumbnails(data, max_pages=min(n, 6), scale=0.3)
                            ui.image(thumbs[min(pdf_pages[f.name], len(thumbs) - 1)], f.name)
                        elif f.name.lower().endswith(".svg"):
                            li = load_image_bytes(data, f.name)
                            ui.image(li.rgb, f.name)
                        else:
                            with Image.open(io.BytesIO(data)) as _im:
                                ui.image(_im.copy(), f"{f.name} ({len(data) // 1024} KB)")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"{f.name}: {exc}")
        _settings_form(app)
        if st.button(t("start_analysis"), type="primary", disabled=not files, key="start_btn"):
            st.caption(t("cancel_hint"))
            rows = []
            for f in files:
                try:
                    data = f.getvalue()
                    page = pdf_pages.get(f.name, 0)
                    li = load_image_bytes(data, f.name, pdf_page=page)
                    pdfb = data if f.name.lower().endswith(".pdf") else None
                    name = f.name if not pdfb else f"{Path(f.name).stem}_p{page + 1}.pdf"
                    state = run_analysis(app, li, name=name, pdf_bytes=pdfb, pdf_page=page, source_bytes=data)
                    rows.append((state.name, state.chart.chart_type if state.chart else "-", sum(len(s.points) for c in state.charts for s in c.series)))
                except ImageLoadError as exc:
                    st.error(f"{f.name}: {exc}")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"{f.name}: {t('failed')}: {exc}")
                    st.caption("See data/logs/graphinsight.log for technical details. Try different settings or a cleaner image.")
            if app.state is not None:
                _show_result(app)
    with tab_sample:
        st.caption(t("sample_note"))
        samples = sorted([p for p in cfg.SAMPLE_DIR.glob("*") if p.suffix.lower() in C.SUPPORTED_EXT]) if cfg.SAMPLE_DIR.exists() else []
        if not samples:
            st.info(t("no_data"))
        else:
            sel = st.selectbox(t("try_sample"), samples, format_func=lambda p: p.name, key="sample_sel")
            ui.sample_badge()
            if sel.suffix.lower() != ".pdf":
                with Image.open(sel) as _im:
                    ui.image(_im.copy(), sel.name)
            if st.button(t("start_analysis"), key="sample_btn", type="primary"):
                data = sel.read_bytes()
                li = load_image(sel)
                run_analysis(app, li, name=sel.name, pdf_bytes=data if sel.suffix.lower() == ".pdf" else None, source_bytes=data, is_sample=True)
                _show_result(app)
