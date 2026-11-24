"""Bar / histogram and pie / donut extraction."""
from __future__ import annotations

import cv2
import numpy as np
import pandas as pd

from .curve_detector import ColorCluster, CropInfo, component_stats
from .coordinate_transform import PlotTransform


def find_bars(cluster: ColorCluster, min_w: int | None = None, min_h: int = 5):
    """Axis-aligned filled rectangles in a cluster mask (crop coordinates)."""
    mask = cluster.mask.astype(np.uint8)
    min_w = min_w or max(8, int(0.015 * mask.shape[1]))
    m = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = component_stats(m)
    out = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if min(w, h) >= 5 and max(w, h) >= min_w and a / float(w * h) >= 0.92:
            out.append((int(x), int(y), int(w), int(h)))
    return out


def classify_bars(per_cluster: dict, crop_h: int, crop_w: int):
    """Return (kind, orientation) from rectangles grouped by cluster index."""
    allb = [b for lst in per_cluster.values() for b in lst]
    if len(allb) < 3:
        return None, None
    bottoms = np.array([y + h for x, y, w, h in allb], float)
    tops = np.array([y for x, y, w, h in allb], float)
    lefts = np.array([x for x, y, w, h in allb], float)
    rights = np.array([x + w for x, y, w, h in allb], float)

    def aligned(v):
        return max(int((np.abs(v - m) <= 2).sum()) for m in v)
    v_al, h_al = max(aligned(bottoms), aligned(tops)), max(aligned(lefts), aligned(rights))
    if max(v_al, h_al) < 3:
        return None, None
    vertical = v_al >= h_al
    if len(per_cluster) == 1:
        bars = sorted(next(iter(per_cluster.values())), key=lambda b: b[0] if vertical else b[1])
        if vertical and len(bars) >= 5:
            gaps = [bars[i + 1][0] - (bars[i][0] + bars[i][2]) for i in range(len(bars) - 1)]
            wmed = np.median([b[2] for b in bars])
            if np.median(gaps) <= 0.15 * wmed:
                return "histogram", "vertical"
        return ("bar" if vertical else "hbar"), ("vertical" if vertical else "horizontal")
    # several colours: stacked if bars of different colours overlap along the category axis
    stacked = False
    cl = list(per_cluster.values())
    for a in cl[0]:
        for other in cl[1:]:
            for b in other:
                if vertical:
                    ov = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
                    if ov > 0.6 * min(a[2], b[2]):
                        stacked = True
                else:
                    ov = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
                    if ov > 0.6 * min(a[3], b[3]):
                        stacked = True
    return ("stacked_bar" if stacked else "grouped_bar"), ("vertical" if vertical else "horizontal")


def bars_table(per_cluster: dict, names: dict, orientation: str, crop: CropInfo, tf: PlotTransform,
               labels: list | None = None, box=None) -> pd.DataFrame:
    """Convert rectangles to a data table.

    value = reading of the bar end when the bar starts at the axis (usual bars / histograms),
    or the segment length for stacked segments that do not touch the axis.
    """
    rows = []
    ext_b = (box.y1 - (crop.oy + crop.h)) if box is not None else 0.0
    ext_l = ((crop.ox) - box.x0) if box is not None else 0.0
    for ci, lst in per_cluster.items():
        for x, y, w, h in sorted(lst, key=lambda b: b[0] if orientation == "vertical" else b[1]):
            if orientation == "vertical":
                touches = y + h >= crop.h - 2
                bottom_px = y + h + crop.oy + (ext_b if touches else 0.0)
                top = float(tf.y.pixel_to_value(y + crop.oy)) if tf.y is not None else np.nan
                base = float(tf.y.pixel_to_value(bottom_px)) if tf.y is not None else np.nan
                lo = float(tf.x.pixel_to_value(x + crop.ox)) if tf.x is not None else np.nan
                hi = float(tf.x.pixel_to_value(x + w + crop.ox)) if tf.x is not None else np.nan
                value = top if touches else (top - base)
                rows.append(dict(series=names[ci], x_center_px=x + w / 2.0 + crop.ox, x_low=lo, x_high=hi,
                                 value=value, top=top, base=base, px_top=y + crop.oy, px_base=bottom_px,
                                 starts_at_axis=bool(touches)))
            else:
                touches = x <= 1
                left_px = x + crop.ox - (ext_l if touches else 0.0)
                right = float(tf.x.pixel_to_value(x + w + crop.ox)) if tf.x is not None else np.nan
                left = float(tf.x.pixel_to_value(left_px)) if tf.x is not None else np.nan
                lo = float(tf.y.pixel_to_value(y + h + crop.oy)) if tf.y is not None else np.nan
                hi = float(tf.y.pixel_to_value(y + crop.oy)) if tf.y is not None else np.nan
                rows.append(dict(series=names[ci], x_center_px=y + h / 2.0 + crop.oy, x_low=lo, x_high=hi,
                                 value=right if touches else (right - left), top=right, base=left,
                                 px_top=x + w + crop.ox, px_base=left_px, starts_at_axis=bool(touches)))
    df = pd.DataFrame(rows)
    if len(df) and labels:
        for i, r in df.iterrows():
            j = int(np.argmin([abs(r.x_center_px - c) for c, _ in labels]))
            df.loc[i, "category"] = labels[j][1]
    return df


def extract_pie(rgb: np.ndarray, pie: dict, n_samples: int = 1440, start_search: bool = True) -> pd.DataFrame:
    """Sector fractions from colours sampled on a circle at 0.72R (clockwise from 12 o'clock)."""
    cx, cy, r = pie["cx"], pie["cy"], pie["r"]
    rr = 0.78 * r if pie.get("donut") else 0.6 * r
    th = np.linspace(0, 2 * np.pi, n_samples, endpoint=False)
    xs = np.clip(np.round(cx + rr * np.sin(th)).astype(int), 0, rgb.shape[1] - 1)
    ys = np.clip(np.round(cy - rr * np.cos(th)).astype(int), 0, rgb.shape[0] - 1)
    col = rgb[ys, xs].astype(float)
    # segment by colour change
    seg_id = np.zeros(n_samples, int)
    centers = [col[0]]
    for i in range(n_samples):
        d = [np.linalg.norm(col[i] - c) for c in centers]
        j = int(np.argmin(d))
        if d[j] > 40:
            centers.append(col[i])
            j = len(centers) - 1
        seg_id[i] = j
    # merge contiguous runs
    rows = []
    start = 0
    for i in range(1, n_samples + 1):
        if i == n_samples or seg_id[i] != seg_id[start]:
            if i - start >= 6:
                rows.append(dict(color=tuple(int(v) for v in np.median(col[start:i], axis=0)),
                                 angle_start_deg=360.0 * start / n_samples, angle_end_deg=360.0 * i / n_samples))
            start = i
    # wrap-around: first and last run may be the same sector
    if len(rows) > 1 and np.linalg.norm(np.array(rows[0]["color"]) - np.array(rows[-1]["color"])) < 40:
        rows[0]["angle_start_deg"] = rows[-1]["angle_start_deg"] - 360.0
        rows.pop()
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["fraction"] = (df.angle_end_deg - df.angle_start_deg) / 360.0
    df["percent"] = df.fraction * 100.0
    df["sector"] = [f"Sector {i + 1}" for i in range(len(df))]
    return df[["sector", "color", "angle_start_deg", "angle_end_deg", "fraction", "percent"]]
