"""PDF handling: page listing, rasterisation and direct extraction of vector curves.

Vector extraction (pypdfium2 raw API) returns the exact vertices of stroked paths, so data can be
recovered without image tracing when the PDF was produced by a plotting program.
"""
from __future__ import annotations

import ctypes
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image

from config.logging_config import get_logger

log = get_logger("pdf")


def _pdfium():
    try:
        import pypdfium2 as pdfium
        return pdfium
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("PDF support requires 'pypdfium2' (pip install pypdfium2).") from exc


def count_pages(data: bytes) -> int:
    pdfium = _pdfium()
    return len(pdfium.PdfDocument(data))


def render_pdf_page_bytes(data: bytes, page: int = 0, scale: float = 3.0) -> np.ndarray:
    pdfium = _pdfium()
    doc = pdfium.PdfDocument(data)
    if not 0 <= page < len(doc):
        raise ValueError(f"PDF has {len(doc)} pages; page {page + 1} requested.")
    pil = doc[page].render(scale=scale).to_pil().convert("RGB")
    return np.asarray(pil)


def render_thumbnails(data: bytes, max_pages: int = 24, scale: float = 0.4) -> list[Image.Image]:
    pdfium = _pdfium()
    doc = pdfium.PdfDocument(data)
    return [doc[i].render(scale=scale).to_pil().convert("RGB") for i in range(min(len(doc), max_pages))]


@dataclass
class VectorPath:
    color: tuple            # (r, g, b)
    points: np.ndarray      # N x 2 in rendered-pixel coordinates (origin top-left)
    n_segments: int
    closed_fill: bool = False


def extract_vector_paths(data: bytes, page: int = 0, scale: float = 3.0,
                         min_segments: int = 6) -> list[VectorPath]:
    """Return stroked polylines (curves) of a PDF page in pixel coordinates of ``render_pdf_page_bytes``."""
    pdfium = _pdfium()
    raw = pdfium.raw
    doc = pdfium.PdfDocument(data)
    pg = doc[page]
    _, height = pg.get_size()
    out: list[VectorPath] = []
    try:
        objs = list(pg.get_objects(max_depth=4))
    except Exception as exc:  # noqa: BLE001
        log.warning("Cannot enumerate PDF objects: %s", exc)
        return out
    for obj in objs:
        if obj.type != raw.FPDF_PAGEOBJ_PATH:
            continue
        cnt = raw.FPDFPath_CountSegments(obj.raw)
        if cnt < min_segments:
            continue
        r, g, b, a = (ctypes.c_uint() for _ in range(4))
        if not raw.FPDFPageObj_GetStrokeColor(obj.raw, r, g, b, a) or a.value == 0:
            continue
        m = raw.FS_MATRIX()
        has_m = raw.FPDFPageObj_GetMatrix(obj.raw, m)
        pts = []
        for i in range(cnt):
            seg = raw.FPDFPath_GetPathSegment(obj.raw, i)
            x, y = ctypes.c_float(), ctypes.c_float()
            if not raw.FPDFPathSegment_GetPoint(seg, x, y):
                continue
            px, py = x.value, y.value
            if has_m:
                px, py = m.a * x.value + m.c * y.value + m.e, m.b * x.value + m.d * y.value + m.f
            pts.append((px * scale, (height - py) * scale))
        if len(pts) >= min_segments:
            out.append(VectorPath((r.value, g.value, b.value), np.asarray(pts, float), cnt))
    log.info("Extracted %d candidate vector paths from PDF page %d", len(out), page + 1)
    return out
