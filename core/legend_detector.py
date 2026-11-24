"""Legend detection: finds colour swatches next to text, reads the names, erases them from series masks."""
from __future__ import annotations

import re

import cv2
import numpy as np

from config.logging_config import get_logger
from .curve_detector import ColorCluster, CropInfo, component_stats, rgb_to_lab
from .ocr_engine import OCRBackend, read_text
from .plot_area_detector import PlotBox

log = get_logger("legend")


def clean_legend_text(t: str) -> str:
    t = re.sub(r"^[\s\-–—_=|~.:]+", "", t.strip())
    t = re.sub(r"[\s|~]+$", "", t)
    return " ".join(t.split())


def _row_runs(profile: np.ndarray):
    idx = np.flatnonzero(profile)
    if idx.size == 0:
        return []
    br = np.flatnonzero(np.diff(idx) > 2)
    s = np.r_[idx[0], idx[br + 1]]
    e = np.r_[idx[br], idx[-1]]
    return list(zip(s, e))


def _find_entry(mask: np.ndarray, gray: np.ndarray, lab: np.ndarray, region_w: int, region_h: int,
                backend: OCRBackend, lang: str, plot_w: int, plot_h: int):
    """Search one region for a swatch component followed by dark text. Returns entry dict (region coords) or None."""
    n, labimg, st, _ = component_stats(mask)
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    text_ink = (gray < 140) & (chroma < 40)
    cands = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        line_like = 0.012 * plot_w <= w <= 0.18 * plot_w and h <= max(0.045 * plot_h, 16) and w >= 1.7 * h
        patch_like = 6 <= w <= 0.05 * plot_w and 6 <= h <= 0.05 * plot_h and 0.6 <= w / max(h, 1) <= 1.7 and area >= 0.6 * w * h
        if line_like or patch_like:
            cands.append((x, y, w, h, i))
    best = None
    for x, y, w, h, i in sorted(cands, key=lambda c: (c[1], c[0])):
        cy = y + h / 2.0
        half = max(10, int(0.018 * plot_h + 3))
        x0, x1 = x + w + 3, min(x + w + 3 + max(140, int(0.4 * plot_w)), region_w)
        y0, y1 = max(int(cy - half), 0), min(int(cy + half) + 1, region_h)
        if x1 - x0 < 8 or y1 <= y0:
            continue
        reg = text_ink[y0:y1, x0:x1]
        if reg.sum() < 12:
            continue
        runs = _row_runs(reg.any(axis=1))
        if not runs:
            continue
        # row run closest to the swatch centre
        r = min(runs, key=lambda ab: 0 if ab[0] <= cy - y0 <= ab[1] else min(abs(ab[0] - (cy - y0)), abs(ab[1] - (cy - y0))))
        ry0, ry1 = r
        th = ry1 - ry0 + 1
        if th < 5 or th > 2.2 * half:
            continue
        cols = reg[ry0:ry1 + 1].any(axis=0)
        idx = np.flatnonzero(cols)
        if idx.size == 0 or idx[0] > 0.06 * plot_w + 12:
            continue
        gap = max(8, int(1.2 * th))
        end = idx[0]
        for c in idx[1:]:
            if c - end > gap:
                break
            end = c
        tx0, tx1 = x0 + idx[0], x0 + end
        ty0, ty1 = y0 + ry0, y0 + ry1
        if tx1 - tx0 < 4:
            continue
        name, conf = ("", 0.0)
        if backend.available:
            crop = gray[max(ty0 - 3, 0): ty1 + 4, max(tx0 - 3, 0): tx1 + 4]
            name, conf = read_text(crop, backend, 7, lang)
            name = clean_legend_text(name)
            if not name or conf < 0.30:
                continue
        entry = dict(name=name or None, conf=float(conf), swatch=(x, y, x + w, y + h),
                     text=(tx0, ty0, tx1, ty1), comp=i)
        best = entry
        break
    return best


def detect_legend(rgb: np.ndarray, gray: np.ndarray, box: PlotBox, crop: CropInfo, clusters: list[ColorCluster],
                  backend: OCRBackend, lang: str = "eng", tol: float = 24.0) -> list[dict]:
    """Detect legend entries. Matching swatches/text are erased from the cluster masks (in place)."""
    entries: list[dict] = []
    gcrop = gray[crop.oy: crop.oy + crop.h, crop.ox: crop.ox + crop.w]
    H, W = gray.shape
    for cl in clusters:
        if cl.neutral and cl.pixels > 0.05 * crop.w * crop.h:
            continue
        found = _find_entry(cl.mask, gcrop, crop.lab, crop.w, crop.h, backend, lang, crop.w, crop.h)
        where = "inside"
        if found is None:                    # legend outside the axes (right of the plot)
            sx0 = int(box.x1) + 8
            if W - sx0 > 40:
                sy0, sy1 = max(int(box.y0) - 10, 0), min(int(box.y1) + 10, H)
                strip_rgb = rgb[sy0:sy1, sx0:W]
                lab = rgb_to_lab(strip_rgb)
                m = (np.linalg.norm(lab - cl.lab, axis=2) < tol).astype(np.uint8)
                found = _find_entry(m, gray[sy0:sy1, sx0:W], lab, W - sx0, sy1 - sy0, backend, lang, crop.w, crop.h)
                if found is not None:
                    where = "outside"
                    for k in ("swatch", "text"):
                        a, b, c, d = found[k]
                        found[k] = (a + sx0 - crop.ox, b + sy0 - crop.oy, c + sx0 - crop.ox, d + sy0 - crop.oy)
        if found is None:
            continue
        found.update(color=cl.rgb, where=where)
        sx0_, sy0_, sx1_, sy1_ = found["swatch"]
        tx0, ty0, tx1, ty1 = found["text"]
        # erase swatch + text from this cluster
        if where == "inside":
            cl.mask[max(sy0_ - 2, 0): sy1_ + 3, max(sx0_ - 2, 0): sx1_ + 3] = 0
            for other in clusters:
                other.mask[max(ty0 - 2, 0): ty1 + 3, max(tx0 - 2, 0): tx1 + 3] = 0
        cl.pixels = int(cl.mask.sum())
        cl.legend = dict(name=found["name"], conf=found["conf"])
        found["bbox_image"] = (sx0_ + crop.ox, sy0_ + crop.oy, tx1 + crop.ox, ty1 + crop.oy)
        entries.append({k: found[k] for k in ("name", "color", "conf", "where", "bbox_image")})
    log.info("Legend entries: %s", [e["name"] for e in entries])
    return entries
