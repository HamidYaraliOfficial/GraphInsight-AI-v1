"""Marker (data point symbol) detection inside a single-colour series mask."""
from __future__ import annotations

import cv2
import numpy as np
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.morphology import skeletonize

from .curve_detector import component_stats


def fill_small_holes(mask: np.ndarray, max_area: float) -> np.ndarray:
    filled = ndi.binary_fill_holes(mask > 0)
    holes = filled & (mask == 0)
    n, lab, st, _ = component_stats(holes.astype(np.uint8))
    out = mask.copy().astype(np.uint8)
    for i in range(1, n):
        if st[i][4] <= max_area:
            out[lab == i] = 1
    return out


def estimate_line_radius(mask: np.ndarray) -> float:
    m = (mask > 0).astype(np.uint8)
    if m.sum() < 10:
        return 0.0
    dt = cv2.distanceTransform(m, cv2.DIST_L2, 5)
    sk = skeletonize(m > 0)
    vals = dt[sk]
    return float(np.median(vals)) if vals.size else 0.0


def detect_markers(mask: np.ndarray, plot_w: int, plot_h: int) -> dict:
    """Return dict(markers=[(cx, cy, r)], line_radius, marker_only)."""
    m = (mask > 0).astype(np.uint8)
    if m.sum() < 12:
        return dict(markers=[], line_radius=0.0, marker_only=False)
    rmax = 0.055 * min(plot_w, plot_h)
    filled = fill_small_holes(m, np.pi * rmax ** 2)
    dt_f = cv2.distanceTransform(filled, cv2.DIST_L2, 5)
    n, lab, st, cen = component_stats(m)
    long_comps = [i for i in range(1, n) if max(st[i][2], st[i][3]) >= 0.12 * min(plot_w, plot_h) * 1.0
                  and (st[i][4] / max(st[i][2] * st[i][3], 1)) < 0.6]
    marker_only = len(long_comps) == 0
    r_line = 0.0 if marker_only else estimate_line_radius(m)
    thr = 1.5 if marker_only else max(2.0, 1.55 * r_line + 0.5)
    blobs = (dt_f > (0.0 if marker_only else thr)).astype(np.uint8) if not marker_only else filled
    bn, blab, bst, bcen = component_stats(blobs)
    cands = []
    for i in range(1, bn):
        sel = blab == i
        r = float(dt_f[sel].max())
        area = int(bst[i][4])
        if r < 2.0 or r > rmax or area < 8:
            continue
        cands.append((i, r, area))
    if not cands:
        return dict(markers=[], line_radius=r_line, marker_only=marker_only)
    med_area = float(np.median([c[2] for c in cands]))
    out = []
    for i, r, area in cands:
        sel = blab == i
        if area > 1.8 * med_area and len(cands) >= 3 or (marker_only and area > 2.2 * med_area and len(cands) >= 3):
            sub = np.where(sel, dt_f, 0)
            md = max(2, int(0.8 * np.sqrt(med_area / np.pi)))
            pk = peak_local_max(sub, min_distance=md, threshold_abs=max(1.5, 0.6 * r), exclude_border=False)
            if len(pk) >= 2:
                for py, px in pk:
                    out.append((float(px), float(py), float(sub[py, px])))
                continue
        ys, xs = np.nonzero(sel)
        w = dt_f[ys, xs]
        out.append((float((xs * w).sum() / w.sum()), float((ys * w).sum() / w.sum()), r))
    if not marker_only and len(out) < 2 and not any(c[1] > 2.2 * max(r_line, 1) for c in cands):
        out = []
    out.sort()
    return dict(markers=out, line_radius=r_line, marker_only=marker_only)
