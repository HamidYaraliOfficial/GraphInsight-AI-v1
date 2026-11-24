"""Per-browser-session application state and long-running operations with progress reporting."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import streamlit as st

from config.logging_config import get_logger
from config.settings import ExtractionSettings
from core.image_loader import LoadedImage
from core.pipeline import analyze_image
from models.data_models import ProjectState
from storage.history_manager import HistoryManager
from storage.project_manager import ProjectManager

log = get_logger("session")


@dataclass
class AppSession:
    pm: ProjectManager = field(default_factory=ProjectManager)
    history: HistoryManager = field(default_factory=HistoryManager)
    state: ProjectState | None = None
    original: np.ndarray | None = None
    processed: np.ndarray | None = None
    settings: ExtractionSettings = field(default_factory=ExtractionSettings)
    manual: dict = field(default_factory=dict)
    pdf_bytes: bytes | None = None
    pdf_page: int = 0
    source_name: str | None = None

    @property
    def chart(self):
        return self.state.chart if self.state else None


def get_app() -> AppSession:
    if "app" not in st.session_state:
        st.session_state["app"] = AppSession()
    return st.session_state["app"]


def progress_cb(label: str = ""):
    """Return (callback, bar). The callback updates a Streamlit progress bar."""
    bar = st.progress(0.0, text=label or "…")

    def cb(frac: float, msg: str):
        bar.progress(min(max(float(frac), 0.0), 1.0), text=msg)
    return cb, bar


def run_analysis(app: AppSession, loaded: LoadedImage, name: str | None = None, pdf_bytes: bytes | None = None, pdf_page: int = 0,
                 source_bytes: bytes | None = None, is_sample: bool = False, manual: dict | None = None) -> ProjectState:
    """Run the full pipeline, create a project on disk and make it the active project."""
    cb, bar = progress_cb()
    out = analyze_image(loaded, app.settings, progress=cb, manual=manual or {}, pdf_bytes=pdf_bytes, pdf_page=pdf_page,
                        project_name=name or loaded.name)
    out.state.is_sample = is_sample
    out.state.settings = {**out.state.settings, "manual": manual or {}}
    bar.empty()
    app.pm.create(out.state, out.original, out.processed, loaded.name, source_bytes)
    app.state, app.original, app.processed = out.state, out.original, out.processed
    app.manual = manual or {}
    app.pdf_bytes, app.pdf_page, app.source_name = pdf_bytes, pdf_page, loaded.name
    app.history.clear()
    return out.state


def rerun_manual(app: AppSession, manual: dict) -> None:
    """Re-run the whole analysis of the active project with manual overrides (calibration, plot area, rotation)."""
    st_old = app.state
    app.history.push(st_old, "manual calibration / plot area")
    loaded = LoadedImage(rgb=app.original, name=st_old.image_meta.get("name", "image"), fmt=st_old.image_meta.get("format", "PNG"),
                         width=app.original.shape[1], height=app.original.shape[0])
    cb, bar = progress_cb()
    out = analyze_image(loaded, app.settings, progress=cb, manual=manual, pdf_bytes=app.pdf_bytes, pdf_page=app.pdf_page,
                        project_name=st_old.name)
    bar.empty()
    ns = out.state
    ns.project_id, ns.name, ns.created, ns.is_sample = st_old.project_id, st_old.name, st_old.created, st_old.is_sample
    ns.settings = {**ns.settings, "manual": manual}
    ns.processing_log = st_old.processing_log + ["--- re-analysed with manual settings ---"] + ns.processing_log
    app.state, app.processed, app.manual = ns, out.processed, manual
    app.pm.update_images(ns.project_id, None, out.processed)
    app.pm.save(ns, "re-analysed with manual overrides")


def checkpoint(app: AppSession, label: str) -> None:
    if app.state is not None:
        app.history.push(app.state, label)


def commit(app: AppSession, event: str) -> None:
    if app.state is not None:
        app.pm.save(app.state, event)


def open_project(app: AppSession, pid: str) -> None:
    state, orig, proc = app.pm.open(pid)
    app.state, app.original, app.processed = state, orig, proc
    app.manual = (state.settings or {}).get("manual", {}) or {}
    app.settings = ExtractionSettings.from_dict({k: v for k, v in (state.settings or {}).items() if k != "manual"})
    app.history.clear()


def undo(app: AppSession) -> str | None:
    if app.state is None:
        return None
    s, label = app.history.undo(app.state)
    if s is None:
        return None
    app.state = s
    commit(app, f"undo: {label}")
    return label


def redo(app: AppSession) -> str | None:
    if app.state is None:
        return None
    s, label = app.history.redo(app.state)
    if s is None:
        return None
    app.state = s
    commit(app, f"redo: {label}")
    return label
