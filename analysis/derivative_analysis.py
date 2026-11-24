"""Numerical derivatives (smoothing spline / Savitzky-Golay / finite differences), slopes and inflection points."""
from __future__ import annotations

import numpy as np
from scipy.interpolate import UnivariateSpline, PchipInterpolator
from scipy.signal import savgol_filter

from .data_cleaning import noise_sigma


def smooth_derivatives(x: np.ndarray, y: np.ndarray, method: str = "spline", n_grid: int = 400) -> dict:
    """Return a dict with grid xg, smoothed y, first and second derivatives.

    method: 'spline' (smoothing spline, noise-adaptive), 'savgol' (uniform grid), 'finite' (np.gradient on raw points).
    Derivatives amplify noise; the smoothing level is estimated from the second differences of the data.
    """
    n = len(x)
    if n < 5:
        return dict(ok=False, reason="at least 5 points are required")
    if method == "finite":
        d1 = np.gradient(y, x)
        d2 = np.gradient(d1, x)
        return dict(ok=True, method="finite differences (numpy.gradient, non-uniform)", xg=x, y=y, d1=d1, d2=d2,
                    note="raw finite differences are noise-sensitive")
    xg = np.linspace(x.min(), x.max(), min(max(n_grid, 50), 2000))
    if method == "savgol":
        yg = PchipInterpolator(x, y)(xg)
        w = max(7, (len(xg) // 25) | 1)
        h = xg[1] - xg[0]
        return dict(ok=True, method=f"Savitzky-Golay (window {w}, order 3) on a uniform resampled grid", xg=xg,
                    y=savgol_filter(yg, w, 3), d1=savgol_filter(yg, w, 3, deriv=1, delta=h),
                    d2=savgol_filter(yg, w, 3, deriv=2, delta=h), note="")
    sg = max(noise_sigma(y), 1e-9 * (np.ptp(y) or 1.0))
    spl = UnivariateSpline(x, y, k=4 if n > 12 else 3, s=n * sg ** 2)
    return dict(ok=True, method="smoothing spline (scipy UnivariateSpline, s = n*sigma^2 from noise estimate)", xg=xg,
                y=spl(xg), d1=spl.derivative(1)(xg), d2=spl.derivative(2)(xg), note="", spline=spl)


def derivative_report(x: np.ndarray, y: np.ndarray, method: str = "spline") -> dict:
    r = smooth_derivatives(x, y, method)
    if not r.get("ok"):
        return r
    xg, d1, d2, yg = r["xg"], r["d1"], r["d2"], r["y"]
    i_max, i_min = int(np.argmax(d1)), int(np.argmin(d1))
    sc = np.where(np.sign(d2[1:]) * np.sign(d2[:-1]) < 0)[0]
    tol = 0.02 * (np.max(np.abs(d2)) or 1.0)
    infl = []
    for i in sc:
        if abs(d2[i]) + abs(d2[i + 1]) < 1e-12:
            continue
        t = d2[i] / (d2[i] - d2[i + 1])
        xi = xg[i] + t * (xg[i + 1] - xg[i])
        # reject sign flips caused by tiny noise
        if max(np.max(np.abs(d2[max(i - 5, 0): i + 6])), 0) > tol:
            infl.append(dict(x=float(xi), y=float(np.interp(xi, xg, yg)), slope=float(np.interp(xi, xg, d1))))
    r.update(max_slope=dict(x=float(xg[i_max]), value=float(d1[i_max])), min_slope=dict(x=float(xg[i_min]), value=float(d1[i_min])),
             mean_slope=float((yg[-1] - yg[0]) / (xg[-1] - xg[0])) if xg[-1] != xg[0] else 0.0, inflection_points=infl)
    r.pop("spline", None)
    return r


def local_slope(x: np.ndarray, y: np.ndarray, x0: float) -> float | None:
    r = smooth_derivatives(x, y, "spline")
    if not r.get("ok"):
        return None
    return float(np.interp(x0, r["xg"], r["d1"]))


def curvature(xg, yg, d1, d2):
    return d2 / np.power(1 + d1 ** 2, 1.5)
