"""Measurement-uncertainty estimates for digitised data and bootstrap confidence intervals of fits."""
from __future__ import annotations

import numpy as np
from scipy import optimize

from models.data_models import ChartResult


def digitization_uncertainty(chart: ChartResult) -> list[dict]:
    """Half-pixel quantisation + calibration residual converted to data units for each series."""
    rows = []
    for s in chart.series:
        p = s.points.dropna(subset=["x", "y"])
        if p.empty:
            continue
        cx = chart.x_axis.calibration if chart.x_axis else None
        cy = (chart.y2_axis.calibration if (s.axis == "y2" and chart.y2_axis) else (chart.y_axis.calibration if chart.y_axis else None))
        if cx is None or cy is None:
            continue
        ux = cx.resolution_at(p.px.to_numpy())
        uy = cy.resolution_at(p.py.to_numpy())
        # 0.5 px quantisation (uniform) -> std = 0.5/sqrt(3) px ; plus calibration rmse
        sx = np.sqrt((ux * 0.5 / np.sqrt(3) * 2) ** 2 + (ux * cx.rmse_px) ** 2)
        sy = np.sqrt((uy * 0.5 / np.sqrt(3) * 2) ** 2 + (uy * cy.rmse_px) ** 2)
        rows.append(dict(series=s.name, n=len(p), x_resolution_per_px=float(np.mean(ux)), y_resolution_per_px=float(np.mean(uy)),
                         x_calibration_rmse_px=cx.rmse_px, y_calibration_rmse_px=cy.rmse_px,
                         mean_std_x=float(np.mean(sx)), mean_std_y=float(np.mean(sy)),
                         max_std_y=float(np.max(sy)), source="derived from pixel size and tick-fit residual (mathematical estimate)"))
    return rows


def bootstrap_fit_ci(model, x, y, popt, n_boot: int = 200, seed: int = 0) -> dict:
    """Residual bootstrap 95% intervals for the parameters of a fitted model (model.func, model.params)."""
    rng = np.random.default_rng(seed)
    yhat = model.func(x, *popt)
    res = y - yhat
    sols = []
    for _ in range(n_boot):
        yb = yhat + rng.choice(res, len(res), replace=True)
        try:
            p, _ = optimize.curve_fit(model.func, x, yb, p0=popt, maxfev=4000)
            sols.append(p)
        except Exception:  # noqa: BLE001
            continue
    if len(sols) < 20:
        return {}
    sols = np.asarray(sols)
    lo, hi = np.percentile(sols, [2.5, 97.5], axis=0)
    return {nm: dict(low=float(lo[i]), high=float(hi[i])) for i, nm in enumerate(model.params)}
