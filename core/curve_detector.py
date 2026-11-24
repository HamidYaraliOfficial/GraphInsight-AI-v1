"""Colour clustering of the plot area: finds series colours, builds per-series masks, removes grid lines."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from config.logging_config import get_logger
from .plot_area_detector import PlotBox

log = get_logger("curves")


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """RGB uint8 (..., 3) -> float32 Lab (L 0..100, a/b ~ -128..127)."""
    arr = np.ascontiguousarray(rgb, dtype=np.float32) / 255.0
    return cv2.cvtColor(arr.reshape(-1, 1, 3) if arr.ndim == 2 else arr, cv2.COLOR_RGB2Lab).reshape(arr.shape)


def lab_to_rgb(lab) -> tuple:
    arr = np.asarray(lab, np.float32).reshape(1, 1, 3)
    out = cv2.cvtColor(arr, cv2.COLOR_Lab2RGB).reshape(3)
    return tuple(int(round(float(v) * 255)) for v in np.clip(out, 0, 1))


@dataclass
class ColorCluster:
    rgb: tuple
    lab: np.ndarray
    mask: np.ndarray                    # uint8 {0,1} in plot-crop coordinates
    pixels: int
    neutral: bool
    offset: tuple = (0, 0)              # crop origin (x, y) in image coordinates
    legend: dict | None = None
    manual: bool = False
    dist: np.ndarray | None = None      # per-pixel Lab distance to the cluster colour (crop size)
    notes: list = field(default_factory=list)

    @property
    def hex(self) -> str:
        return "#%02x%02x%02x" % self.rgb


@dataclass
class CropInfo:
    ox: int
    oy: int
    w: int
    h: int
    lab: np.ndarray
    rgb: np.ndarray


def make_crop(rgb: np.ndarray, box: PlotBox) -> CropInfo:
    inset = int(np.ceil(box.axis_thickness / 2.0)) + 2
    x0, y0 = int(np.ceil(box.x0)) + inset, int(np.ceil(box.y0)) + inset
    x1, y1 = int(np.floor(box.x1)) - inset, int(np.floor(box.y1)) - inset
    H, W = rgb.shape[:2]
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W), min(y1, H)
    crop = np.ascontiguousarray(rgb[y0:y1, x0:x1])
    return CropInfo(x0, y0, x1 - x0, y1 - y0, rgb_to_lab(crop), crop)


def _dist_to_segment(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    t = float(np.clip(np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-9), 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def detect_grid(mask: np.ndarray) -> np.ndarray:
    """Pixels of regularly repeated long thin horizontal / vertical lines (grid) inside a neutral mask."""
    H, W = mask.shape
    out = np.zeros_like(mask)
    m8 = (mask > 0).astype(np.uint8)
    for horizontal in (True, False):
        length = int(0.45 * (W if horizontal else H))
        if length < 20:
            continue
        gap = 14
        kc = (gap, 1) if horizontal else (1, gap)
        closed = cv2.morphologyEx(m8, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, kc))
        kk = (length, 1) if horizontal else (1, length)
        opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kk))
        n, lab, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
        good = [i for i in range(1, n) if (stats[i][3] if horizontal else stats[i][2]) <= 6]
        if len(good) >= 2:
            sel = np.isin(lab, good).astype(np.uint8)
            sel = cv2.dilate(sel, np.ones((3, 3), np.uint8))
            out |= (sel & m8)
    return out


def find_color_clusters(rgb: np.ndarray, box: PlotBox, tol: float = 24.0, min_pixels: int = 60,
                        manual_colors: list | None = None, remove_grid: bool = True,
                        max_clusters: int = 12) -> tuple[list[ColorCluster], CropInfo]:
    crop = make_crop(rgb, box)
    lab = crop.lab
    if crop.w < 20 or crop.h < 20:
        return [], crop
    L, a, b = lab[..., 0], lab[..., 1], lab[..., 2]
    chroma = np.hypot(a, b)
    background = (L > 85) & (chroma < 12)
    core = ((chroma >= 20) | (L < 62)) & ~background
    centers: list[np.ndarray] = []
    manual_flags: list[bool] = []

    if manual_colors:
        for c in manual_colors:
            centers.append(rgb_to_lab(np.array([[c]], np.uint8)).reshape(3))
            manual_flags.append(True)
    else:
        pts = lab[core]
        if len(pts) >= min_pixels:
            q = np.floor(pts / np.array([10.0, 8.0, 8.0])).astype(np.int64)
            key = (q[:, 0] + 20) * 1_000_000 + (q[:, 1] + 40) * 1000 + (q[:, 2] + 40)
            uniq, inv, cnt = np.unique(key, return_inverse=True, return_counts=True)
            sums = np.zeros((len(uniq), 3))
            for k in range(3):
                sums[:, k] = np.bincount(inv, weights=pts[:, k], minlength=len(uniq))
            means = sums / cnt[:, None]
            for i in np.argsort(-cnt):
                if cnt[i] < max(min_pixels * 0.6, 20):
                    break
                m = means[i]
                if any(np.linalg.norm(m - c) < 26 for c in centers):
                    continue
                centers.append(m)
                manual_flags.append(False)
                if len(centers) >= max_clusters * 2:
                    break

    if not centers:
        return [], crop

    # refine centres (mean colour of pixels well inside the cluster)
    dE_all = np.stack([np.linalg.norm(lab - c, axis=2) for c in centers], axis=0)
    for k, c in enumerate(centers):
        sel = (dE_all[k] < 10) & (core | (manual_flags[k]))
        if sel.sum() >= 10:
            centers[k] = lab[sel].mean(axis=0)
    dE_all = np.stack([np.linalg.norm(lab - c, axis=2) for c in centers], axis=0)
    owner = np.argmin(dE_all, axis=0)

    clusters: list[ColorCluster] = []
    for k, c in enumerate(centers):
        m = ((owner == k) & (dE_all[k] < tol) & (core | manual_flags[k])).astype(np.uint8)
        px = int(m.sum())
        if px < min_pixels:
            continue
        neutral = float(np.hypot(c[1], c[2])) < 14
        clusters.append(ColorCluster(lab_to_rgb(c), c, m, px, neutral, (crop.ox, crop.oy),
                                     manual=manual_flags[k], dist=dE_all[k].astype(np.float32)))
    clusters.sort(key=lambda cl: -cl.pixels)

    # drop anti-aliasing fringes of stronger clusters (lighter shades lying between a colour and white)
    white = np.array([100.0, 0.0, 0.0])
    keep: list[ColorCluster] = []
    for cl in clusters:
        fringe = False
        if not cl.manual:
            for st in keep:
                if cl.pixels < 0.8 * st.pixels and _dist_to_segment(cl.lab, st.lab, white) < 16:
                    grown = cv2.dilate(st.mask, np.ones((5, 5), np.uint8))
                    if (grown & cl.mask).sum() >= 0.8 * cl.pixels:
                        fringe = True
                        break
        if not fringe:
            keep.append(cl)
    clusters = keep[:max_clusters]

    if remove_grid:
        for cl in clusters:
            if cl.neutral:
                g = detect_grid(cl.mask)
                if g.sum() > 0:
                    cl.mask = (cl.mask & ~g).astype(np.uint8)
                    cl.pixels = int(cl.mask.sum())
                    cl.notes.append("grid lines removed from this neutral cluster")
        clusters = [c for c in clusters if c.pixels >= min_pixels]
    log.info("Found %d colour cluster(s): %s", len(clusters), [c.hex for c in clusters])
    return clusters, crop


def component_stats(mask: np.ndarray):
    n, lab, st, cen = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    return n, lab, st, cen


def split_curve_and_small(mask: np.ndarray, plot_w: int, plot_h: int, min_len_frac: float = 0.04):
    """Split a series mask into long components (curve) and small blobs (markers / text / noise)."""
    n, lab, st, cen = component_stats(mask)
    curve = np.zeros_like(mask, np.uint8)
    small = np.zeros_like(mask, np.uint8)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        if w >= min_len_frac * plot_w or h >= min_len_frac * plot_h * 1.5:
            curve[lab == i] = 1
        elif area >= 4:
            small[lab == i] = 1
    return curve, small


def looks_like_markers(mask_small: np.ndarray) -> bool:
    """True if the small components are many, similar in size and compact (markers, not text)."""
    n, lab, st, cen = component_stats(mask_small)
    if n - 1 < 3:
        return False
    areas = st[1:, cv2.CC_STAT_AREA].astype(float)
    w = st[1:, cv2.CC_STAT_WIDTH].astype(float)
    h = st[1:, cv2.CC_STAT_HEIGHT].astype(float)
    ar = w / np.maximum(h, 1)
    fill = areas / np.maximum(w * h, 1)
    big = areas > 0.4 * np.median(areas)
    if big.sum() < 3:
        return False
    cv = areas[big].std() / (areas[big].mean() + 1e-9)
    return bool(cv < 0.45 and np.median(ar[big]) > 0.6 and np.median(ar[big]) < 1.7 and np.median(fill[big]) > 0.45)
