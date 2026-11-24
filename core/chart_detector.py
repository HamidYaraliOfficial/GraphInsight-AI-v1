"""Rule-based chart type classification (with transparent scores) and label-based refinement."""
from __future__ import annotations

import re

import cv2
import numpy as np

from models.chart_types import CHART_INFO

_KEYWORDS = [
    (("stress",), ("strain",), "stress_strain"),
    (("force", "load"), ("displacement", "extension", "elongation", "deflection", "deformation", "disp"), "force_displacement"),
    (("frequency", "freq"), ("magnitude", "gain", "db", "phase"), "bode"),
    (("true positive", "tpr", "sensitivity"), ("false positive", "fpr", "1-specificity"), "roc"),
    (("precision",), ("recall",), "pr"),
    (("survival", "probability"), ("time", "days", "months"), "kaplan_meier"),
    (("absorbance", "transmittance", "absorption", "intensity"), ("wavelength", "wavenumber", "nm"), "spectral"),
    (("impedance", "z'"), ("z''", "-z", "im"), "nyquist"),
]


def refine_by_labels(chart_type: str, x_title: str | None, y_title: str | None):
    """Specialise a generic curve type from axis titles. Returns (type, changed)."""
    if chart_type not in ("line", "scientific_curve", "multi_series", "smooth_curve", "generic", "dual_y", "scatter"):
        return chart_type, False
    xt, yt = (x_title or "").lower(), (y_title or "").lower()
    if not xt and not yt:
        return chart_type, False
    for ys, xs, key in _KEYWORDS:
        if any(k in yt for k in ys) and any(k in xt for k in xs):
            return key, True
    if "force" in yt and not xt:
        return "force_displacement", True
    return chart_type, False


def find_pie(rgb: np.ndarray):
    """Detect a pie/donut: one large, nearly circular coloured region. Returns dict or None."""
    H, W = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    ink = ((gray < 235) & ((hsv[..., 1] > 40) | (gray < 100))).astype(np.uint8)
    ink = cv2.morphologyEx(ink, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    n, lab, st, cen = cv2.connectedComponentsWithStats(ink, connectivity=8)
    if n <= 1:
        return None
    i = 1 + int(np.argmax(st[1:, 4]))
    x, y, w, h, area = st[i]
    if min(w, h) < 0.25 * min(H, W) or not (0.85 <= w / max(h, 1) <= 1.18):
        return None
    sel = (lab == i).astype(np.uint8)
    cnts, _ = cv2.findContours(sel, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    (cx, cy), r = cv2.minEnclosingCircle(max(cnts, key=cv2.contourArea))
    if area / (np.pi * r * r) < 0.72:
        return None
    hole = gray[int(cy), int(cx)] > 235
    return dict(cx=float(cx), cy=float(cy), r=float(r), donut=bool(hole))


def classify(f: dict) -> tuple[str, float, dict]:
    """Classify from extracted features.

    features (all optional): has_axes, pie, bars (dict: n, kind), n_series, n_marker_series, n_line_series,
    has_errors, has_band, step, area, dual_axis, log_x, log_y, panels, parametric.
    """
    s: dict[str, float] = {}
    if f.get("pie"):
        s["donut" if f["pie"].get("donut") else "pie"] = 0.9
    b = f.get("bars")
    if b and b.get("n", 0) >= 3:
        kind = b.get("kind", "bar")
        s[kind] = 0.8 if b["n"] >= 4 else 0.65
    if f.get("area"):
        s["area"] = 0.7
    if f.get("step"):
        s["step"] = 0.7
    if f.get("parametric"):
        s["parametric"] = 0.5
    ns = f.get("n_series", 0)
    if ns:
        base = 0.55
        if f.get("has_errors"):
            s["error_bar"] = 0.8
        if f.get("dual_axis"):
            s["dual_y"] = 0.8
        if f.get("n_marker_series", 0) and not f.get("n_line_series", 0):
            s["scatter"] = 0.75
        elif ns >= 2:
            s["multi_series"] = 0.65
        else:
            s["line"] = base + 0.1
    if not s:
        s["generic"] = 0.3
    key = max(s, key=s.get)
    if f.get("panels", 1) > 1:
        s["multi_panel"] = 0.6
    return key, float(s[key]), {k: round(v, 2) for k, v in sorted(s.items(), key=lambda kv: -kv[1])}


def support_note(chart_type: str) -> str | None:
    sup = CHART_INFO.get(chart_type, {}).get("support")
    if sup == "classify":
        return ("This chart type is recognised but automatic numeric extraction is not implemented; "
                "use manual digitization or the generic curve extraction.")
    if sup == "partial":
        return "Partial support for this chart type: please review extracted data manually."
    return None
