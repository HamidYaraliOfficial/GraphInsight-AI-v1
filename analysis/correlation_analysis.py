"""Comparison of several series on their common x-range."""
from __future__ import annotations

import itertools

import numpy as np
from scipy import stats

from ._compat import first, trapezoid
from .integral_analysis import area_between


def _common(x1, y1, x2, y2, n=400):
    lo, hi = max(x1.min(), x2.min()), min(x1.max(), x2.max())
    if hi - lo <= 0:
        return None
    xg = np.linspace(lo, hi, n)
    return xg, np.interp(xg, x1, y1), np.interp(xg, x2, y2)


def compare_series(data: dict[str, tuple[np.ndarray, np.ndarray]]) -> dict:
    """data = {name: (x, y)}. Returns per-series metrics, pairwise table and rankings."""
    per = {}
    for nm, (x, y) in data.items():
        if len(x) < 3:
            continue
        lr = stats.linregress(x, y) if np.ptp(x) > 0 else None
        per[nm] = dict(max=float(y.max()), x_at_max=float(x[np.argmax(y)]), min=float(y.min()), x_at_min=float(x[np.argmin(y)]),
                       start=float(y[0]), end=float(y[-1]), change=float(y[-1] - y[0]),
                       change_percent=float((y[-1] - y[0]) / y[0] * 100) if y[0] != 0 else None,
                       mean=float(np.mean(y)), x_min=float(x.min()), x_max=float(x.max()),
                       linear_slope=float(lr.slope) if lr else None,
                       auc=float(trapezoid(y, x)))
    pairs = []
    for a, b in itertools.combinations(per, 2):
        c = _common(*data[a], *data[b])
        if c is None:
            pairs.append(dict(a=a, b=b, common_range=None))
            continue
        xg, ya, yb = c
        d = ya - yb
        rngv = max(np.ptp(np.r_[ya, yb]), 1e-12)
        row = dict(a=a, b=b, common_range=[float(xg[0]), float(xg[-1])], mean_difference=float(d.mean()),
                   max_abs_difference=float(np.max(np.abs(d))), x_at_max_difference=float(xg[np.argmax(np.abs(d))]),
                   rmsd=float(np.sqrt(np.mean(d ** 2))), nrmsd=float(np.sqrt(np.mean(d ** 2)) / rngv),
                   mean_relative_difference_pct=float(np.mean(np.abs(d) / np.maximum(np.abs(yb), 1e-12 * rngv)) * 100),
                   )
        if np.ptp(ya) > 0 and np.ptp(yb) > 0:
            row.update(pearson_r=first(stats.pearsonr(ya, yb)), spearman_rho=first(stats.spearmanr(ya, yb)),
                       kendall_tau=first(stats.kendalltau(ya, yb)))
            za, zb = (ya - ya.mean()) / ya.std(), (yb - yb.mean()) / yb.std()
            row["shape_similarity"] = float(1.0 - np.sqrt(np.mean((za - zb) ** 2)) / 2.0)
        ab = area_between(*data[a], *data[b])
        if ab.get("ok"):
            row.update(area_signed=ab["signed"], area_absolute=ab["absolute"])
        pairs.append(row)
    rank = {}
    for key in ("max", "mean", "auc", "change"):
        order = sorted(per, key=lambda n: -per[n][key])
        rank[key] = order
    return dict(per_series=per, pairs=pairs, ranking=rank,
                note="Pairwise statistics use linear interpolation on the common x-range; correlations of "
                     "reconstructed curves describe shape similarity, not statistical significance.")
