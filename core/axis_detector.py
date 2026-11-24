"""Axis detection: tick positions, tick-label OCR, axis titles / units and calibration."""
from __future__ import annotations

import re

import cv2
import numpy as np

from config.logging_config import get_logger
from models.data_models import AxisInfo, AxisTick
from .coordinate_transform import fit_calibration
from .ocr_engine import OCRBackend, read_number, read_text
from .plot_area_detector import PlotBox

log = get_logger("axis")


# ------------------------------------------------------------------ ticks
def _ticks_along(dark: np.ndarray, axis_row: float, thick: float, out_sign: int, c0: int, c1: int):
    """Axis is horizontal in ``dark`` at ``axis_row``; ticks extend in direction ``out_sign`` (+1 = down).

    Returns (tick_centres, tick_length). Works for outward and inward ticks via ``out_sign``.
    """
    H, W = dark.shape
    half = int(np.ceil(thick / 2.0))
    start = int(round(axis_row)) + out_sign * (half + 1)
    maxlen = int(max(10, min(60, 0.08 * max(H, W))))
    run = np.zeros(W, int)
    alive = np.ones(W, bool)
    for k in range(maxlen):
        r = start + out_sign * k
        if r < 0 or r >= H:
            break
        alive &= dark[r, :]
        run += alive
        if not alive[max(c0, 0): c1 + 1].any():
            break
    seg = run[max(c0, 0): c1 + 1]
    if seg.size == 0 or seg.max() < 3:
        return [], 0
    cand = seg[seg >= 3]
    ref = float(np.percentile(cand, 90)) if len(cand) > 4 else float(cand.max())
    thr = max(3.0, 0.6 * ref)
    on = seg >= thr
    ticks = []
    i, n = 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j + 1 < n and on[j + 1]:
                j += 1
            width = j - i + 1
            if width <= max(8, int(3 * thick) + 2):
                ticks.append(max(c0, 0) + (i + j) / 2.0)
            i = j + 1
        else:
            i += 1
    return ticks, int(round(ref))


def _refine_centres(gray: np.ndarray, centres, rows: tuple, vertical_ticks: bool, win: int = 3):
    """Sub-pixel tick centres by darkness-weighted centroid within +/-win px."""
    out = []
    for c in centres:
        c0, c1 = int(round(c)) - win, int(round(c)) + win + 1
        if vertical_ticks:
            patch = 255.0 - gray[rows[0]:rows[1], max(c0, 0):c1].astype(float)
            prof = patch.mean(axis=0)
            xs = np.arange(max(c0, 0), max(c0, 0) + len(prof))
        else:
            patch = 255.0 - gray[max(c0, 0):c1, rows[0]:rows[1]].astype(float)
            prof = patch.mean(axis=1)
            xs = np.arange(max(c0, 0), max(c0, 0) + len(prof))
        prof = np.clip(prof - prof.min(), 0, None)
        out.append(float((xs * prof).sum() / prof.sum()) if prof.sum() > 0 else float(c))
    return out


def _segments_1d(profile: np.ndarray, min_gap: int):
    """Split a boolean 1-D ink profile into (start, end) runs separated by >= min_gap blanks."""
    idx = np.flatnonzero(profile)
    if idx.size == 0:
        return []
    out, s, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i - prev > min_gap:
            out.append((int(s), int(prev)))
            s = i
        prev = i
    out.append((int(s), int(prev)))
    return out


def _dominant_color(rgb: np.ndarray, bbox) -> tuple | None:
    x0, y0, x1, y1 = [int(v) for v in bbox]
    patch = rgb[max(y0, 0):y1, max(x0, 0):x1].reshape(-1, 3).astype(float)
    if len(patch) == 0:
        return None
    mx, mn = patch.max(1), patch.min(1)
    sat = (mx - mn)
    sel = patch[(sat > 50) & (mx < 240)]
    if len(sel) < 6:
        return None
    return tuple(int(v) for v in np.median(sel, axis=0))


# ------------------------------------------------------------- label parsing
_UNIT_RE = re.compile(r"^(?P<name>.*?)\s*[\(\[\{]\s*(?P<unit>[^\)\]\}]+?)\s*[\)\]\}]\s*$")


def split_title_unit(text: str | None):
    """'Force (N)' -> ('Force', 'N');  'Time / s' -> ('Time', 's')."""
    if not text:
        return None, None
    t = " ".join(text.split())
    m = _UNIT_RE.match(t)
    if m and m.group("name"):
        return m.group("name").strip(), m.group("unit").strip()
    m2 = re.match(r"^(.*?)\s*/\s*([^/]{1,12})$", t)
    if m2 and m2.group(1):
        return m2.group(1).strip(), m2.group(2).strip()
    m3 = re.match(r"^\s*[\(\[]\s*([^\)\]]+)[\)\]]\s*$", t)
    if m3:
        return None, m3.group(1).strip()
    return t, None


def _label_regions_x(dark, box: PlotBox, y_start: int, band_h: int, gap: int):
    """Return list of (x0, x1, y0, y1) boxes of tick labels below the x axis, and the label-band bottom."""
    H, W = dark.shape
    x0, x1 = max(int(box.x0) - 25, 0), min(int(box.x1) + 40, W - 1)
    y_end = min(y_start + band_h, H)
    band = dark[y_start:y_end, x0:x1 + 1]
    rows = band.any(axis=1)
    segs = _segments_1d(rows, 2)
    if len(segs) > 1 and segs[0][1] - segs[0][0] < 3 and segs[1][0] - segs[0][1] < 20:
        segs = segs[1:]                                   # remnant of a (blurred) tick mark
    if not segs:
        return [], y_start
    first = segs[0]
    if first[0] > 0.6 * band_h:      # nothing close enough to the axis
        return [], y_start
    ry0, ry1 = first[0], first[1]
    reg = band[ry0:ry1 + 1]
    ch = ry1 - ry0 + 1
    cols = reg.any(axis=0)
    csegs = _segments_1d(cols, max(gap, int(0.45 * ch)))
    out = [(x0 + a, x0 + b, y_start + ry0, y_start + ry1) for a, b in csegs]
    return out, y_start + ry1


def _label_regions_y(dark, box: PlotBox, x_start: int, band_w: int, gap: int):
    """Tick-label regions left of the y axis (x_start = first column left of the ticks, scanning leftwards)."""
    H, W = dark.shape
    y0, y1 = max(int(box.y0) - 25, 0), min(int(box.y1) + 25, H - 1)
    xa = max(x_start - band_w, 0)
    band = dark[y0:y1 + 1, xa:x_start + 1]
    # typical text height from the row runs of the band
    near = band[:, max(band.shape[1] - 48, 0):]
    rsegs0 = _segments_1d(near.any(axis=1), 1)
    hs = [b - a + 1 for a, b in rsegs0 if 4 <= b - a + 1 <= 60]
    text_h = float(np.median(hs)) if hs else 12.0
    min_gap = max(3, int(0.38 * text_h))
    cols = band.any(axis=0)[::-1]                         # scan from the axis outwards
    segs = _segments_1d(cols, min_gap)
    if len(segs) > 1 and segs[0][1] - segs[0][0] < 3 and segs[1][0] - segs[0][1] < 3 * text_h:
        segs = segs[1:]                                   # remnant of a (blurred) tick mark
    if not segs or segs[0][0] > 0.5 * band_w:
        return [], x_start
    c0, c1 = segs[0]
    bw = band.shape[1]
    xs0, xs1 = xa + (bw - 1 - c1), xa + (bw - 1 - c0)
    reg = dark[y0:y1 + 1, xs0:xs1 + 1]
    rows = reg.any(axis=1)
    rsegs = _segments_1d(rows, 2)
    out = [(xs0, xs1, y0 + a, y0 + b) for a, b in rsegs]
    return out, xs0


def _match_labels(tick_px, label_centres, tol):
    """Greedy nearest matching; returns {tick_index: label_index}."""
    pairs = []
    for ti, t in enumerate(tick_px):
        for li, c in enumerate(label_centres):
            d = abs(t - c)
            if d <= tol:
                pairs.append((d, ti, li))
    pairs.sort()
    used_t, used_l, out = set(), set(), {}
    for d, ti, li in pairs:
        if ti in used_t or li in used_l:
            continue
        used_t.add(ti)
        used_l.add(li)
        out[ti] = li
    return out


# ------------------------------------------------------------------ main API
def detect_axis(gray: np.ndarray, rgb: np.ndarray, box: PlotBox, orientation: str, backend: OCRBackend,
                scale_hint: str = "auto", side: str | None = None, lang: str = "eng",
                read_title: bool = True) -> AxisInfo:
    """Detect ticks, read their labels, read the axis title and fit a calibration."""
    H, W = gray.shape
    dark = gray < 150
    info = AxisInfo(orientation=orientation, side=side or ("bottom" if orientation == "x" else "left"))
    thick = max(1.0, box.axis_thickness)

    if orientation == "x":
        axis_pos = box.y1
        info.line_pos = axis_pos
        outs, tl_out = _ticks_along(dark, axis_pos, thick, +1, int(box.x0) - 3, int(box.x1) + 3)
        ins, tl_in = _ticks_along(dark, axis_pos, thick, -1, int(box.x0) - 3, int(box.x1) + 3)
    else:
        if info.side == "right":
            axis_pos = box.x1
            info.line_pos = axis_pos
            outs, tl_out = _ticks_along(dark.T, axis_pos, thick, +1, int(box.y0) - 3, int(box.y1) + 3)
            ins, tl_in = _ticks_along(dark.T, axis_pos, thick, -1, int(box.y0) - 3, int(box.y1) + 3)
        else:
            axis_pos = box.x0
            info.line_pos = axis_pos
            outs, tl_out = _ticks_along(dark.T, axis_pos, thick, -1, int(box.y0) - 3, int(box.y1) + 3)
            ins, tl_in = _ticks_along(dark.T, axis_pos, thick, +1, int(box.y0) - 3, int(box.y1) + 3)

    if len(outs) >= 2 and len(outs) >= 0.6 * len(ins):
        ticks, tl, direction = outs, tl_out, "out"
    elif len(ins) >= 2:
        ticks, tl, direction = ins, tl_in, "in"
    else:
        ticks, tl, direction = outs or ins, max(tl_out, tl_in), "out"
    info.tick_direction = direction
    if len(ticks) < 2:
        info.warnings.append("Fewer than two axis ticks were detected; enter the axis values manually.")
        return info
    # sub-pixel refinement
    half = int(np.ceil(thick / 2.0))
    if orientation == "x":
        sgn = 1 if direction == "out" else -1
        r0 = int(round(axis_pos)) + sgn * (half + 1)
        rows = tuple(sorted((r0, r0 + sgn * max(tl - 1, 2))))
        ticks = _refine_centres(gray, ticks, (rows[0], rows[1] + 1), True)
    else:
        if info.side == "right":
            sgn = 1 if direction == "out" else -1
        else:
            sgn = -1 if direction == "out" else 1
        c0_ = int(round(axis_pos)) + sgn * (half + 1)
        cols = tuple(sorted((c0_, c0_ + sgn * max(tl - 1, 2))))
        ticks = _refine_centres(gray, ticks, (cols[0], cols[1] + 1), False)
    spacing = np.median(np.diff(sorted(ticks))) if len(ticks) > 1 else 40.0
    info.ticks = [AxisTick(float(t)) for t in sorted(ticks)]

    # ---- label regions
    gap = 3
    band_h = int(max(40, min(0.16 * H, 120)))
    band_w = int(max(60, min(0.2 * W, 220)))
    regions, label_edge = [], 0
    if orientation == "x":
        y_start = int(round(axis_pos)) + half + (tl if direction == "out" else 0) + 1
        regions, label_edge = _label_regions_x(dark, box, y_start, band_h, gap)
        centres = [(r[0] + r[1]) / 2.0 for r in regions]
    else:
        if info.side == "right":
            # mirror: scan to the right by flipping the image horizontally
            fd = dark[:, ::-1]
            fbox = PlotBox(W - 1 - box.x1, box.y0, W - 1 - box.x0, box.y1)
            x_start = int(round(W - 1 - axis_pos)) - half - (tl if direction == "out" else 0) - 1
            reg_f, edge_f = _label_regions_y(fd, fbox, x_start, band_w, gap)
            regions = [(W - 1 - r[1], W - 1 - r[0], r[2], r[3]) for r in reg_f]
            label_edge = W - 1 - edge_f
        else:
            x_start = int(round(axis_pos)) - half - (tl if direction == "out" else 0) - 1
            regions, label_edge = _label_regions_y(dark, box, x_start, band_w, gap)
        centres = [(r[2] + r[3]) / 2.0 for r in regions]

    # ---- OCR labels
    nums = []
    for r in regions:
        x0, x1, y0, y1 = r
        crop = gray[max(y0 - 2, 0): y1 + 3, max(x0 - 2, 0): x1 + 3]
        nums.append(read_number(crop, backend))
    tick_px = [t.pixel for t in info.ticks]
    match = _match_labels(tick_px, centres, tol=max(0.6 * spacing, 6))
    for ti, li in match.items():
        n = nums[li]
        tk = info.ticks[ti]
        tk.label, tk.value, tk.conf = n.raw, n.value, n.conf
        if n.value is None:
            tk.label = n.raw or None
    if regions and rgb is not None:
        bb = (min(r[0] for r in regions), min(r[2] for r in regions), max(r[1] for r in regions) + 1,
              max(r[3] for r in regions) + 1)
        info.label_color = _dominant_color(rgb, bb)

    # ---- calibration
    lab = [(t.pixel, t.value, t.conf) for t in info.ticks if t.value is not None]
    if len(lab) >= 2:
        px = [a for a, _, _ in lab]
        vals = [b for _, b, _ in lab]
        mean_conf = float(np.mean([c for _, _, c in lab]))
        cal = fit_calibration(px, vals, scale=scale_hint, source="ocr", ocr_conf=mean_conf)
        axis_len = (box.w if orientation == "x" else box.h)
        if cal is None:
            info.warnings.append("Axis calibration failed (inconsistent tick values).")
        elif cal.scale != "piecewise" and cal.rmse_px > max(6.0, 0.015 * axis_len):
            info.warnings.append(f"OCR tick values are mutually inconsistent (fit error {cal.rmse_px:.1f}px); "
                                 "calibration rejected - enter tick values manually.")
        else:
            info.calibration = cal
            if cal.outliers:
                info.warnings.append(f"{len(cal.outliers)} OCR tick label(s) rejected as outliers.")
    else:
        info.warnings.append("Tick labels could not be read reliably by OCR; enter the tick values manually.")

    # ---- axis title
    if read_title and backend.available:
        try:
            title_img = None
            if orientation == "x":
                top = label_edge + max(3, gap)
                strip = dark[top: min(top + int(0.18 * H), H), max(int(box.x0) - 10, 0): min(int(box.x1) + 10, W)]
                segs = _segments_1d(strip.any(axis=1), 3)
                if segs and segs[0][0] < 0.12 * H:
                    a, b = segs[0]
                    cx = strip[a:b + 1].any(axis=0)
                    ci = np.flatnonzero(cx)
                    xa = max(int(box.x0) - 10, 0)
                    title_img = gray[top + a - 3: top + b + 4, xa + ci[0] - 3: xa + ci[-1] + 4]
            elif info.side == "right":
                left = min(label_edge + max(3, gap) + 1, W - 1)
                xe = min(left + int(0.2 * W), W)
                strip = dark[max(int(box.y0) - 10, 0): min(int(box.y1) + 10, H), left:xe]
                segs = _segments_1d(strip.any(axis=0), 3)
                if segs and segs[0][0] < 0.12 * W:
                    a, b = segs[0]
                    ys_ = np.flatnonzero(strip[:, a:b + 1].any(axis=1))
                    ya_ = max(int(box.y0) - 10, 0)
                    crop = gray[ya_ + ys_[0] - 3: ya_ + ys_[-1] + 4, left + a - 3: left + b + 4]
                    title_img = cv2.rotate(crop, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif info.side == "left":
                right = max(label_edge - max(3, gap), 0)
                strip = dark[max(int(box.y0) - 10, 0): min(int(box.y1) + 10, H), max(right - int(0.2 * W), 0): right]
                segs = _segments_1d(strip.any(axis=0)[::-1], 3)
                if segs and segs[0][0] < 0.12 * W:
                    a, b = segs[0]
                    n = strip.shape[1]
                    xs0, xs1 = n - 1 - b, n - 1 - a
                    xb = max(right - int(0.2 * W), 0)
                    ys = np.flatnonzero(strip[:, xs0:xs1 + 1].any(axis=1))
                    ya = max(int(box.y0) - 10, 0)
                    crop = gray[ya + ys[0] - 3: ya + ys[-1] + 4, xb + xs0 - 3: xb + xs1 + 4]
                    title_img = cv2.rotate(crop, cv2.ROTATE_90_CLOCKWISE)
            if title_img is not None and title_img.size:
                txt, conf = read_text(title_img, backend, 7, lang)
                if orientation == "y" and (conf < 0.55 or len(txt) < 2):
                    alt = cv2.rotate(title_img, cv2.ROTATE_180)
                    t2, c2 = read_text(alt, backend, 7, lang)
                    if c2 > conf:
                        txt, conf = t2, c2
                if txt and conf >= 0.35:
                    info.raw_title, info.title_conf = txt, conf
                    info.title, info.unit = split_title_unit(txt)
        except Exception as exc:  # noqa: BLE001
            log.warning("Axis title OCR failed: %s", exc)
    return info


def read_chart_title(gray: np.ndarray, box: PlotBox, backend: OCRBackend, lang: str = "eng"):
    if not backend.available or box.y0 < 12:
        return None, 0.0
    dark = gray < 150
    strip = dark[: max(int(box.y0) - 2, 1), max(int(box.x0) - 10, 0): int(box.x1) + 10]
    if not strip.any():
        return None, 0.0
    segs = _segments_1d(strip.any(axis=1), 3)
    a, b = segs[-1]
    cols = np.flatnonzero(strip[a:b + 1].any(axis=0))
    xa = max(int(box.x0) - 10, 0)
    crop = gray[max(a - 3, 0): b + 4, xa + cols[0] - 3: xa + cols[-1] + 4]
    txt, conf = read_text(crop, backend, 7, lang)
    return (txt, conf) if txt and conf >= 0.4 else (None, 0.0)
