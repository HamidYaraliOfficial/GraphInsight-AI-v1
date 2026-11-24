"""Numerical integration: trapezoidal rule, Simpson's rule, cumulative integral and area between curves."""
from __future__ import annotations

import numpy as np
from scipy import integrate
from scipy.interpolate import PchipInterpolator

from ._compat import trapezoid


def _uniform(x, y, n=None):
    n = n or max(201, (len(x) // 2) * 2 + 1)
    if n % 2 == 0:
        n += 1
    xg = np.linspace(x.min(), x.max(), n)
    return xg, PchipInterpolator(x, y)(xg)


def integrate_series(x: np.ndarray, y: np.ndarray, a: float | None = None, b: float | None = None) -> dict:
    """Definite integral on [a, b] (defaults to the whole x-range)."""
    if len(x) < 3:
        return dict(ok=False, reason="at least 3 points required")
    lo = x.min() if a is None else max(a, x.min())
    hi = x.max() if b is None else min(b, x.max())
    if hi <= lo:
        return dict(ok=False, reason="empty integration interval")
    xi = np.interp(np.linspace(lo, hi, 2), x, y)
    sel = (x > lo) & (x < hi)
    xs = np.r_[lo, x[sel], hi]
    ys = np.r_[xi[0], y[sel], xi[1]]
    trap = float(trapezoid(ys, xs))
    xu, yu = _uniform(xs, ys)
    simp = float(integrate.simpson(yu, x=xu))
    cum = integrate.cumulative_trapezoid(ys, xs, initial=0.0)
    pos = float(trapezoid(np.clip(ys, 0, None), xs))
    neg = float(trapezoid(np.clip(ys, None, 0), xs))
    return dict(ok=True, a=float(lo), b=float(hi), trapezoid=trap, simpson=simp, area_positive=pos, area_negative=neg,
                abs_area=float(trapezoid(np.abs(ys), xs)), cum_x=xs.tolist(), cum_y=cum.tolist(),
                method="trapezoidal rule on the extracted points; Simpson's rule on a PCHIP-resampled uniform grid",
                difference_trap_simpson=float(abs(trap - simp)))


def area_between(x1, y1, x2, y2) -> dict:
    """Signed and absolute area between two curves on their common x-range."""
    lo, hi = max(x1.min(), x2.min()), min(x1.max(), x2.max())
    if hi <= lo:
        return dict(ok=False, reason="the curves share no common x-range")
    xg = np.linspace(lo, hi, max(400, len(x1), len(x2)))
    d = np.interp(xg, x1, y1) - np.interp(xg, x2, y2)
    return dict(ok=True, a=float(lo), b=float(hi), signed=float(trapezoid(d, xg)), absolute=float(trapezoid(np.abs(d), xg)),
                mean_difference=float(np.mean(d)), max_difference=float(d[np.argmax(np.abs(d))]),
                x_at_max_difference=float(xg[np.argmax(np.abs(d))]))
