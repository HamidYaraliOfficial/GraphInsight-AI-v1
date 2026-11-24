"""Error-bar and shaded-band (confidence region) detection."""
from __future__ import annotations

import cv2
import numpy as np
import pandas as pd

from .curve_detector import ColorCluster, _dist_to_segment, component_stats, rgb_to_lab


def _scan(mask: np.ndarray, cx: float, cy: float, r: float, direction: int, half_w: int = 1, max_gap: int = 2):
    """Walk from the marker edge along a column band; return (end_row, has_cap)."""
    H, W = mask.shape
    x0, x1 = max(int(round(cx)) - half_w, 0), min(int(round(cx)) + half_w + 1, W)
    y = int(round(cy + direction * (r + 0.5)))
    last, miss = None, 0
    while 0 <= y < H:
        if mask[y, x0:x1].any():
            last, miss = y, 0
        else:
            miss += 1
            if miss > max_gap:
                break
        y += direction
    if last is None:
        return None, False
    cap_w = 0
    xc = int(round(cx))
    for dx in range(1, 40):
        if xc - dx >= 0 and xc + dx < W and (mask[last, xc - dx] or mask[last, xc + dx] or
                                             (last + direction >= 0 and last + direction < H and False)):
            cap_w = dx
        else:
            break
    return last, cap_w >= 3


def detect_error_bars(markers: list, mask_candidates: list, line_present: bool) -> dict | None:
    """Vertical and horizontal error bars attached to the markers of one series.

    ``mask_candidates`` is a list of masks (series colour, dark ink) tried in order.
    Returns dict(vertical=[(minus_px, plus_px)|None], horizontal=..., mask_to_erase) or None.
    """
    if len(markers) < 3:
        return None
    for mask in mask_candidates:
        res = {"vertical": [], "horizontal": []}
        erase = np.zeros_like(mask, np.uint8)
        caps_v = bars_v = 0
        for cx, cy, r in markers:
            up, cap_u = _scan(mask, cx, cy, r, -1)
            dn, cap_d = _scan(mask, cx, cy, r, +1)
            ok_u = up is not None and (cy - r - up) >= max(3, 0.6 * r)
            ok_d = dn is not None and (dn - (cy + r)) >= max(3, 0.6 * r)
            if ok_u or ok_d:
                bars_v += 1
                caps_v += int((ok_u and cap_u) or (ok_d and cap_d))
                u = (cy - up) if ok_u else 0.0
                d = (dn - cy) if ok_d else 0.0
                res["vertical"].append((float(d), float(u), float(cy)))
                top, bot = (up if ok_u else int(cy)), (dn if ok_d else int(cy))
                erase[max(top - 1, 0): bot + 2, max(int(round(cx)) - 3, 0): int(round(cx)) + 4] = 1
            else:
                res["vertical"].append(None)
        frac = bars_v / len(markers)
        if frac >= 0.6 and (caps_v >= 0.5 * bars_v or not line_present):
            # remove the bar pixels, but keep the marker discs themselves
            for cx, cy, r in markers:
                cv2.circle(erase, (int(round(cx)), int(round(cy))), int(np.ceil(r)) + 1, 0, -1)
            res["erase"] = erase
            res["caps"] = caps_v
            return res
    return None


def errors_frame(res: dict, markers: list, idx_offset: int, to_data_y) -> pd.DataFrame:
    """Convert pixel error lengths to data-space plus/minus values (y direction)."""
    rows = []
    for k, (m, v) in enumerate(zip(markers, res["vertical"])):
        if v is None:
            rows.append(dict(idx=idx_offset + k, y_minus=np.nan, y_plus=np.nan, kind="unspecified"))
            continue
        d_px, u_px, _ = v
        cy = m[1]
        y0 = float(to_data_y(cy))
        y_up = float(to_data_y(cy - u_px)) if u_px > 0 else y0
        y_dn = float(to_data_y(cy + d_px)) if d_px > 0 else y0
        rows.append(dict(idx=idx_offset + k, y_minus=abs(y0 - y_dn), y_plus=abs(y_up - y0), kind="unspecified"))
    return pd.DataFrame(rows)


def detect_band(crop_lab: np.ndarray, cluster: ColorCluster, curve_mask: np.ndarray, min_ratio: float = 2.5):
    """Shaded region around a curve: pixels whose colour lies between the series colour and white."""
    white = np.array([100.0, 0.0, 0.0])
    c = cluster.lab
    ab = white - c
    # distance to the segment (c -> white) for every pixel (vectorised)
    t = np.clip(((crop_lab - c) @ ab) / (ab @ ab + 1e-9), 0, 1)
    proj = c + t[..., None] * ab
    d = np.linalg.norm(crop_lab - proj, axis=2)
    chroma = np.hypot(crop_lab[..., 1], crop_lab[..., 2])
    tint = (d < 7.0) & (t > 0.12) & (t < 0.93) & (chroma > 5.0)
    tint = tint.astype(np.uint8)
    tint = cv2.morphologyEx(tint, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    n, lab, st, _ = component_stats(tint)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(st[1:, 4]))
    area = int(st[i][4])
    if area < min_ratio * max(int(curve_mask.sum()), 1) or st[i][2] < 0.2 * crop_lab.shape[1]:
        return None
    # the curve itself splits the tinted region into an upper and a lower part: keep every large part
    keep = [j for j in range(1, n) if st[j][4] >= 0.25 * area and st[j][2] >= 0.15 * crop_lab.shape[1]]
    region = (np.isin(lab, keep) | (curve_mask > 0))
    xs = np.flatnonzero(region.any(axis=0))
    low, high = [], []
    for x in xs:
        rows = np.flatnonzero(region[:, x])
        high.append(rows[0])      # top pixel row  (smaller row = larger value)
        low.append(rows[-1])
    return pd.DataFrame(dict(px=xs.astype(float), py_top=np.array(high, float), py_bottom=np.array(low, float)))
