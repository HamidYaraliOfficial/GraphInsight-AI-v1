"""Intersections between curves and zero crossings."""
from __future__ import annotations

import itertools

import numpy as np


def zero_crossings(x: np.ndarray, y: np.ndarray, level: float = 0.0) -> list[float]:
    d = y - level
    idx = np.where(d[:-1] * d[1:] < 0)[0]
    out = [float(x[i] - d[i] * (x[i + 1] - x[i]) / (d[i + 1] - d[i])) for i in idx]
    out += [float(v) for v in x[d == 0]]
    return sorted(set(out))


def intersections(data: dict[str, tuple[np.ndarray, np.ndarray]], n: int = 2000) -> list[dict]:
    """Crossing points for every pair of series (sign changes of the difference on the common range)."""
    rows = []
    for a, b in itertools.combinations(data, 2):
        (xa, ya), (xb, yb) = data[a], data[b]
        lo, hi = max(xa.min(), xb.min()), min(xa.max(), xb.max())
        if hi <= lo or len(xa) < 2 or len(xb) < 2:
            continue
        xg = np.linspace(lo, hi, n)
        d = np.interp(xg, xa, ya) - np.interp(xg, xb, yb)
        for i in np.where(d[:-1] * d[1:] < 0)[0]:
            t = d[i] / (d[i] - d[i + 1])
            xi = xg[i] + t * (xg[i + 1] - xg[i])
            rows.append(dict(series_a=a, series_b=b, x=float(xi), y=float(np.interp(xi, xa, ya))))
    return rows
