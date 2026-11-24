"""Pixel <-> data coordinate transforms and axis calibration.

An :class:`AxisCalibration` maps ONE image axis (pixel coordinate along that axis) to a data value.
Supported scales: linear, log10, log2, ln, piecewise (non-uniform), categorical, datetime.
Reversed axes are handled automatically (negative slope).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

LOG_BASES = {"log10": 10.0, "log2": 2.0, "ln": math.e}


def parse_datetime_value(text: str) -> float:
    """Parse a date/time string to seconds since epoch (used for date axes)."""
    import pandas as pd
    ts = pd.to_datetime(text)
    return float(ts.timestamp())


def format_datetime_value(seconds: float) -> str:
    import pandas as pd
    return str(pd.to_datetime(seconds, unit="s"))


@dataclass
class AxisCalibration:
    scale: str = "linear"                    # linear|log10|log2|ln|piecewise|categorical|datetime
    a: float = 1.0                           # pixel = a * f(value) + b
    b: float = 0.0
    refs: list = field(default_factory=list)       # [(pixel, value)] used points
    outliers: list = field(default_factory=list)   # [(pixel, value)] rejected points
    rmse_px: float = 0.0
    confidence: float = 0.0
    source: str = "ocr"                      # ocr | manual | box
    categories: list = field(default_factory=list)
    note: str = ""

    # ---------------------------------------------------------------- transforms
    def _f(self, v):
        v = np.asarray(v, dtype=float)
        if self.scale in LOG_BASES:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.log(v) / math.log(LOG_BASES[self.scale])
        return v

    def _finv(self, u):
        u = np.asarray(u, dtype=float)
        if self.scale in LOG_BASES:
            return LOG_BASES[self.scale] ** u
        return u

    def _pw(self):
        r = sorted(self.refs, key=lambda t: t[0])
        return np.array([t[0] for t in r], float), np.array([t[1] for t in r], float)

    def pixel_to_value(self, p):
        p = np.asarray(p, dtype=float)
        if self.scale == "piecewise":
            px, vals = self._pw()
            out = np.interp(p, px, vals)
            lo, hi = p < px[0], p > px[-1]
            if lo.any() and len(px) > 1:
                out = np.where(lo, vals[0] + (p - px[0]) * (vals[1] - vals[0]) / (px[1] - px[0]), out)
            if hi.any() and len(px) > 1:
                out = np.where(hi, vals[-1] + (p - px[-1]) * (vals[-1] - vals[-2]) / (px[-1] - px[-2]), out)
            return out
        if self.a == 0:
            return np.full_like(p, np.nan)
        return self._finv((p - self.b) / self.a)

    def value_to_pixel(self, v):
        v = np.asarray(v, dtype=float)
        if self.scale == "piecewise":
            px, vals = self._pw()
            order = np.argsort(vals)
            return np.interp(v, vals[order], px[order])
        return self.a * self._f(v) + self.b

    def resolution_at(self, p) -> np.ndarray:
        """Data-unit change for one pixel step at pixel p (used for uncertainty)."""
        p = np.asarray(p, dtype=float)
        return np.abs(self.pixel_to_value(p + 0.5) - self.pixel_to_value(p - 0.5))

    def category_at(self, p) -> str | None:
        if self.scale != "categorical" or not self.categories:
            return None
        i = int(round(float(self.pixel_to_value(p))))
        return self.categories[i] if 0 <= i < len(self.categories) else None

    @property
    def is_valid(self) -> bool:
        return (self.scale == "piecewise" and len(self.refs) >= 2) or (np.isfinite(self.a) and self.a != 0)

    # ------------------------------------------------------------ serialisation
    def to_dict(self) -> dict:
        return dict(scale=self.scale, a=float(self.a), b=float(self.b),
                    refs=[[float(p), float(v)] for p, v in self.refs],
                    outliers=[[float(p), float(v)] for p, v in self.outliers],
                    rmse_px=float(self.rmse_px), confidence=float(self.confidence),
                    source=self.source, categories=list(self.categories), note=self.note)

    @classmethod
    def from_dict(cls, d: dict | None):
        if not d:
            return None
        return cls(scale=d.get("scale", "linear"), a=d.get("a", 1.0), b=d.get("b", 0.0),
                   refs=[tuple(x) for x in d.get("refs", [])],
                   outliers=[tuple(x) for x in d.get("outliers", [])],
                   rmse_px=d.get("rmse_px", 0.0), confidence=d.get("confidence", 0.0),
                   source=d.get("source", "ocr"), categories=d.get("categories", []),
                   note=d.get("note", ""))


# ====================================================================== fitting
def _lstsq(f: np.ndarray, p: np.ndarray):
    A = np.vstack([f, np.ones_like(f)]).T
    (a, b), *_ = np.linalg.lstsq(A, p, rcond=None)
    return float(a), float(b), p - (a * f + b)


def _robust_fit(f: np.ndarray, p: np.ndarray, min_keep: int = 3):
    """Exhaustive two-point RANSAC (small n) followed by least squares on the inliers."""
    n = len(p)
    idx_all = np.arange(n)
    if n <= 2:
        a, b, res = _lstsq(f, p)
        return idx_all, a, b, res
    span = float(np.ptp(p)) or 1.0
    tol = max(2.0, 0.006 * span)
    rng = np.random.default_rng(0)
    pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
    if len(pairs) > 400:
        pairs = [pairs[k] for k in rng.choice(len(pairs), 400, replace=False)]
    best = None
    for i, j in pairs:
        if abs(f[j] - f[i]) < 1e-12:
            continue
        a = (p[j] - p[i]) / (f[j] - f[i])
        b = p[i] - a * f[i]
        res = p - (a * f + b)
        inl = np.flatnonzero(np.abs(res) <= tol)
        score = (len(inl), -float(np.sum(res[inl] ** 2)))
        if best is None or score > best[0]:
            best = (score, inl)
    if best is None or len(best[1]) < max(2, min(min_keep, n)) or len(best[1]) < 0.5 * n:
        a, b, res = _lstsq(f, p)
        return idx_all, a, b, res
    idx = best[1]
    a, b, _ = _lstsq(f[idx], p[idx])
    res = p[idx] - (a * f[idx] + b)
    return idx, a, b, res


def fit_calibration(pixels, values, scale: str = "auto", source: str = "ocr",
                    ocr_conf: float | None = None, categories: list | None = None) -> AxisCalibration | None:
    """Fit pixel = a*f(value)+b. Needs >= 2 reference ticks (>= 3 preferred for validation)."""
    pixels = np.asarray(pixels, float)
    values = np.asarray(values, float)
    ok = np.isfinite(pixels) & np.isfinite(values)
    pixels, values = pixels[ok], values[ok]
    if len(pixels) < 2 or len(set(np.round(pixels, 1))) < 2:
        return None

    if scale == "categorical":
        a, b, res = _lstsq(values, pixels)
        cal = AxisCalibration("categorical", a, b, list(zip(pixels, values)), [], float(np.sqrt(np.mean(res ** 2))),
                              0.7, source, list(categories or []))
        return cal
    if scale == "piecewise":
        order = np.argsort(pixels)
        return AxisCalibration("piecewise", 1.0, 0.0, list(zip(pixels[order], values[order])), [], 0.0,
                               0.6, source, note="non-uniform axis (interpolated between reference ticks)")

    candidates = []
    names = ["linear"] if scale in ("linear", "datetime") else ([scale] if scale in LOG_BASES else ["linear", "log10"])
    for name in names:
        if name in LOG_BASES:
            if np.any(values <= 0):
                continue
            f = np.log(values) / math.log(LOG_BASES[name])
        else:
            f = values
        idx, a, b, res = _robust_fit(f, pixels)
        rmse = float(np.sqrt(np.mean(res ** 2)))
        candidates.append((name, idx, a, b, rmse, f))
    if not candidates:
        return None

    chosen = candidates[0]
    if scale == "auto" and len(candidates) == 2:
        lin, log = candidates
        decades = np.log10(values.max() / values.min()) if values.min() > 0 else 0
        if log[4] < 0.6 * lin[4] and lin[4] > 1.2 and decades >= 0.9:
            chosen = log
    name, idx, a, b, rmse, f = chosen
    if scale in ("auto", "piecewise_ok") and rmse > 3.0 and len(pixels) >= 4:
        v_sorted = values[np.argsort(pixels)]
        if np.all(np.diff(v_sorted) > 0) or np.all(np.diff(v_sorted) < 0):
            order = np.argsort(pixels)
            return AxisCalibration("piecewise", 1.0, 0.0, list(zip(pixels[order], values[order])), [], rmse,
                                   0.5, source, note="linear/log fit poor; using piecewise interpolation")
    keep = np.zeros(len(pixels), bool)
    keep[idx] = True
    n = int(keep.sum())
    conf = {2: 0.6, 3: 0.85}.get(n, 1.0) * float(np.clip(1.0 - rmse / 4.0, 0.25, 1.0))
    if ocr_conf is not None:
        conf *= float(np.clip(0.5 + 0.5 * ocr_conf, 0.4, 1.0))
    if source == "manual":
        conf = max(conf, 0.9)
    return AxisCalibration(name if name != "linear" or scale != "datetime" else "datetime", a, b,
                           [(float(p), float(v)) for p, v in zip(pixels[keep], values[keep])],
                           [(float(p), float(v)) for p, v in zip(pixels[~keep], values[~keep])],
                           rmse, float(conf), source)


def calibration_from_box(p0: float, p1: float, v0: float, v1: float, scale: str = "linear") -> AxisCalibration | None:
    """Calibration from the plot-area edges: pixel p0 <-> value v0 and p1 <-> v1."""
    cal = fit_calibration([p0, p1], [v0, v1], scale=scale, source="box")
    if cal:
        cal.confidence = 0.55
        cal.note = "calibrated from plot-area edges (assumes axis limits equal the box edges)"
    return cal


# ================================================================ plot transform
@dataclass
class PlotTransform:
    """Bundle of axis calibrations for a chart (x, y and optional secondary y)."""
    x: AxisCalibration | None = None
    y: AxisCalibration | None = None
    y2: AxisCalibration | None = None

    def y_for(self, axis: str = "y") -> AxisCalibration | None:
        return self.y2 if (axis == "y2" and self.y2 is not None) else self.y

    def to_data(self, px, py, axis: str = "y"):
        cy = self.y_for(axis)
        xs = self.x.pixel_to_value(px) if self.x is not None else np.full(np.shape(px), np.nan)
        ys = cy.pixel_to_value(py) if cy is not None else np.full(np.shape(py), np.nan)
        return xs, ys

    def to_pixel(self, x, y, axis: str = "y"):
        cy = self.y_for(axis)
        return self.x.value_to_pixel(x), cy.value_to_pixel(y)

    @property
    def ready(self) -> bool:
        return self.x is not None and self.y is not None and self.x.is_valid and self.y.is_valid
