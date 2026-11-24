"""Curve centre-line tracing, adaptive sampling and conversion of pixels to data points."""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from skimage.morphology import skeletonize

from config import constants as C
from config.logging_config import get_logger
from models.data_models import POINT_COLUMNS, Series
from . import confidence_estimator as CE
from .coordinate_transform import PlotTransform

log = get_logger("digitizer")


# ------------------------------------------------------------------ tracing
@dataclass
class TracedPath:
    xs: np.ndarray                 # crop-pixel x (float)
    ys: np.ndarray                 # crop-pixel y (float, sub-pixel)
    interpolated: np.ndarray       # bool per sample (bridged gap)
    thickness: float               # median line thickness in px
    steep: np.ndarray              # bool: run much taller than the line
    breaks: list                   # indices i where the path is broken between i-1 and i
    purity: np.ndarray             # colour purity 0-1
    coverage: float                # fraction of columns (in x-extent) with data

    def __len__(self):
        return len(self.xs)


def _column_runs(mask: np.ndarray):
    H, W = mask.shape
    runs = []
    for x in range(W):
        idx = np.flatnonzero(mask[:, x])
        if idx.size == 0:
            runs.append([])
            continue
        br = np.flatnonzero(np.diff(idx) > 1)
        runs.append(list(zip(np.r_[idx[0], idx[br + 1]], np.r_[idx[br], idx[-1]])))
    return runs


def trace_function(mask: np.ndarray, dist: np.ndarray | None, tol: float, max_gap: int = 25) -> TracedPath | None:
    """Trace a single-valued curve y(x): one sub-pixel centre per column, chosen by dynamic programming."""
    H, W = mask.shape
    runs = _column_runs(mask > 0)
    cols = [x for x in range(W) if runs[x]]
    if len(cols) < 3:
        return None
    heights = [r[0][1] - r[0][0] + 1 for x in cols for r in [runs[x]] if len(r) == 1]
    thick = float(np.median(heights)) if heights else 3.0
    cand = {}
    for x in cols:
        lst = []
        for r0, r1 in runs[x]:
            a, b = max(r0 - 2, 0), min(r1 + 3, H)
            if dist is not None:
                w = np.clip(1.0 - dist[a:b, x] / (1.35 * tol), 0, 1)
                w[: max(r0 - a, 0)] *= 0.0 if False else 1.0
                rows = np.arange(a, b)
                centre = float((rows * w).sum() / w.sum()) if w.sum() > 0 else (r0 + r1) / 2.0
                pur = float(np.clip(1.0 - np.mean(dist[r0:r1 + 1, x]) / tol * 0.6, 0.3, 1.0))
            else:
                centre, pur = (r0 + r1) / 2.0, 1.0
            lst.append((centre, r1 - r0 + 1, pur))
        cand[x] = lst
    # Viterbi over columns that contain candidates
    prev_x = cols[0]
    cost_prev = np.array([0.0 for _ in cand[prev_x]])
    back = {}
    for x in cols[1:]:
        cur = cand[x]
        pc = cand[prev_x]
        dx = max(1, x - prev_x)
        cost = np.zeros(len(cur))
        bk = np.zeros(len(cur), int)
        for i, (c, h, _) in enumerate(cur):
            trans = [cost_prev[j] + abs(c - pc[j][0]) / np.sqrt(dx) + 0.01 * abs(h - pc[j][1]) for j in range(len(pc))]
            j = int(np.argmin(trans))
            cost[i], bk[i] = trans[j], j
        back[x] = bk
        cost_prev, prev_x = cost, x
    i = int(np.argmin(cost_prev))
    chosen = {}
    x = cols[-1]
    ci = cols.index(x)
    while True:
        chosen[x] = i
        if ci == 0:
            break
        i = int(back[x][i])
        ci -= 1
        x = cols[ci]
    xs, ys, hs, pur = [], [], [], []
    for x in cols:
        c, h, p = cand[x][chosen[x]]
        xs.append(x)
        ys.append(c)
        hs.append(h)
        pur.append(p)
    xs, ys, hs, pur = map(np.asarray, (xs, ys, hs, pur))
    # bridge short gaps, remember long ones as breaks
    ox, oy, oi, os_, op, breaks = [xs[0]], [ys[0]], [False], [hs[0]], [pur[0]], []
    for k in range(1, len(xs)):
        gap = xs[k] - xs[k - 1]
        if gap > 1:
            if gap <= max_gap:
                for g in range(1, gap):
                    t = g / gap
                    ox.append(xs[k - 1] + g)
                    oy.append(ys[k - 1] * (1 - t) + ys[k] * t)
                    oi.append(True)
                    os_.append(thick)
                    op.append(0.5)
            else:
                breaks.append(len(ox))
        ox.append(xs[k]); oy.append(ys[k]); oi.append(False); os_.append(hs[k]); op.append(pur[k])
    ox, oy = np.asarray(ox, float), np.asarray(oy, float)
    cover = len(cols) / max(cols[-1] - cols[0] + 1, 1)
    return TracedPath(ox, oy, np.asarray(oi), thick, np.asarray(os_) > max(3.2 * thick, thick + 6),
                      breaks, np.asarray(op), float(cover))


def trace_parametric(mask: np.ndarray, dist: np.ndarray | None = None, tol: float = 24.0) -> TracedPath | None:
    """Longest skeleton path (for curves that are not functions of x: loops, Nyquist, hysteresis)."""
    sk = skeletonize(mask > 0)
    pts = np.argwhere(sk)
    if len(pts) < 5:
        return None
    idx = {(int(y), int(x)): i for i, (y, x) in enumerate(pts)}
    nb = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

    def bfs(start):
        dist_, par = {start: 0}, {start: None}
        q = [start]
        for cur in q:
            for dy, dx in nb:
                n = (cur[0] + dy, cur[1] + dx)
                if n in idx and n not in dist_:
                    dist_[n] = dist_[cur] + 1
                    par[n] = cur
                    q.append(n)
        far = max(dist_, key=dist_.get)
        return far, par

    a, _ = bfs((int(pts[0][0]), int(pts[0][1])))
    b, par = bfs(a)
    path = []
    cur = b
    while cur is not None:
        path.append(cur)
        cur = par[cur]
    path = np.asarray(path[::-1], float)
    if len(path) < 5:
        return None
    ys, xs = path[:, 0], path[:, 1]
    k = min(len(xs) - (1 - len(xs) % 2), 7)
    if k >= 5:
        xs, ys = savgol_filter(xs, k, 2), savgol_filter(ys, k, 2)
    thick = float(np.median(cv2.distanceTransform((mask > 0).astype(np.uint8), cv2.DIST_L2, 5)[sk]) * 2)
    n = len(xs)
    return TracedPath(xs, ys, np.zeros(n, bool), thick, np.zeros(n, bool), [], np.ones(n), 1.0)


def step_corners(path: TracedPath, tol_px: float = 0.7, min_len: int = 3):
    """Reduce a traced step curve to plateau end points (corner points)."""
    xs, ys = path.xs, path.ys
    seg_start = 0
    pts = []
    for i in range(1, len(xs) + 1):
        if i == len(xs) or abs(ys[i] - ys[i - 1]) > tol_px:
            if i - seg_start >= min_len:
                level = float(np.median(ys[seg_start:i]))
                pts.append((xs[seg_start], level))
                pts.append((xs[i - 1], level))
            seg_start = i
    return pts


# ------------------------------------------------------------------ sampling
def _split_segments(path: TracedPath):
    idx = [0] + list(path.breaks) + [len(path)]
    return [(a, b) for a, b in zip(idx[:-1], idx[1:]) if b - a >= 2]


def adaptive_sample(xs, ys, n: int, curvature_weight: float = 4.0, mode: str = "adaptive") -> np.ndarray:
    """Return an (n, 2) array of sample positions along a path (more points where the curve bends)."""
    xs, ys = np.asarray(xs, float), np.asarray(ys, float)
    if len(xs) < 2 or n < 2:
        return np.c_[xs, ys]
    ds = np.hypot(np.diff(xs), np.diff(ys))
    s = np.r_[0, np.cumsum(ds)]
    if s[-1] <= 0:
        return np.c_[xs[:1], ys[:1]]
    if mode == "uniform_x":
        grid = np.linspace(xs.min(), xs.max(), n)
        order = np.argsort(xs)
        return np.c_[grid, np.interp(grid, xs[order], ys[order])]
    if mode == "uniform_arc":
        t = np.linspace(0, s[-1], n)
        return np.c_[np.interp(t, s, xs), np.interp(t, s, ys)]
    k = min(len(xs) - (1 - len(xs) % 2), 11)
    if k >= 5:
        xsm, ysm = savgol_filter(xs, k, 2), savgol_filter(ys, k, 2)
    else:
        xsm, ysm = xs, ys
    ang = np.unwrap(np.arctan2(np.diff(ysm), np.diff(xsm)))
    dth = np.abs(np.diff(ang, prepend=ang[0]))
    r0 = max(8.0, 0.02 * s[-1])
    dens = ds * (1.0 + curvature_weight * dth * r0 / np.maximum(ds, 1e-6) * 0.5)
    cum = np.r_[0, np.cumsum(dens)]
    t = np.linspace(0, cum[-1], n)
    return np.c_[np.interp(t, cum, xs), np.interp(t, cum, ys)]


def sample_path(path: TracedPath, n_points: int, mode: str, curvature_weight: float):
    """Sample every unbroken segment; returns (positions Nx2, interpolated flags, purity, steep) arrays."""
    segs = _split_segments(path)
    if not segs:
        return np.empty((0, 2)), np.empty(0, bool), np.empty(0), np.empty(0, bool)
    lengths = np.array([np.hypot(np.diff(path.xs[a:b]), np.diff(path.ys[a:b])).sum() + 1 for a, b in segs])
    alloc = np.maximum(2, np.round(n_points * lengths / lengths.sum()).astype(int))
    P, F, U, S = [], [], [], []
    for (a, b), m in zip(segs, alloc):
        pos = adaptive_sample(path.xs[a:b], path.ys[a:b], int(m), curvature_weight, mode)
        P.append(pos)
        # nearest original sample gives the flags
        idx = np.clip(np.searchsorted(path.xs[a:b], pos[:, 0]) if mode != "uniform_arc" else
                      np.argmin(np.abs(path.xs[a:b][None, :] - pos[:, :1]), axis=1), 0, b - a - 1)
        F.append(path.interpolated[a:b][idx])
        U.append(path.purity[a:b][idx])
        S.append(path.steep[a:b][idx])
    return np.vstack(P), np.concatenate(F), np.concatenate(U), np.concatenate(S)


# ------------------------------------------------------------ point tables
def make_points(px, py, status, transform: PlotTransform, axis: str, offset: tuple, method: str,
                purity, ambiguity, steep, cal_conf: float, start_idx: int = 0) -> pd.DataFrame:
    px = np.asarray(px, float) + offset[0]
    py = np.asarray(py, float) + offset[1]
    xd, yd = transform.to_data(px, py, axis)
    status = np.asarray(status, dtype=object)
    conf = CE.point_confidence(status, purity, ambiguity, steep, cal_conf)
    return pd.DataFrame(dict(idx=np.arange(start_idx, start_idx + len(px), dtype=float), x=xd, y=yd, px=px, py=py,
                             status=status, confidence=conf, method=method))[POINT_COLUMNS]


def ambiguity_map(other_masks: list, thickness: float, shape: tuple) -> np.ndarray:
    """1 where no other series is close, 0.6 where another series is within ~2 line widths."""
    if not other_masks:
        return np.ones(shape, np.float32)
    u = np.zeros(shape, np.uint8)
    for m in other_masks:
        u |= (m > 0).astype(np.uint8)
    k = int(max(3, 2 * thickness + 3)) | 1
    near = cv2.dilate(u, np.ones((k, k), np.uint8))
    return np.where(near > 0, 0.6, 1.0).astype(np.float32)


def amb_at(amb: np.ndarray, px, py) -> np.ndarray:
    xi = np.clip(np.round(px).astype(int), 0, amb.shape[1] - 1)
    yi = np.clip(np.round(py).astype(int), 0, amb.shape[0] - 1)
    return amb[yi, xi]
