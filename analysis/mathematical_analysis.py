"""Mathematical Analysis Engine: features, derivatives, integrals, model fitting and statistics for every series."""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from config import constants as C
from models.data_models import ChartResult, Series, to_jsonable
from . import curve_fitting as CF
from . import correlation_analysis as CA
from . import data_cleaning as DC
from . import derivative_analysis as DA
from . import integral_analysis as IA
from . import intersection_analysis as IX
from . import statistical_analysis as SA
from . import uncertainty_analysis as UA

DEFAULT_OPTS = dict(fit_source="auto", families=None, quick=False, custom=[], deriv_method="spline", run_fits=True,
                    include_interpolated=False)


def _down(a, n=200):
    a = np.asarray(a, float)
    if len(a) <= n:
        return a.tolist()
    return a[np.linspace(0, len(a) - 1, n).astype(int)].tolist()


def _segments(sign: np.ndarray, xg: np.ndarray, min_frac: float = 0.02):
    out, start = [], 0
    for i in range(1, len(sign) + 1):
        if i == len(sign) or sign[i] != sign[start]:
            if xg[i - 1] - xg[start] >= min_frac * (xg[-1] - xg[0]) and sign[start] != 0:
                out.append(dict(x0=float(xg[start]), x1=float(xg[i - 1]), kind="convex (curving up)" if sign[start] > 0 else "concave (curving down)"))
            start = i
    return out


def curve_features(x: np.ndarray, y: np.ndarray, drep: dict) -> dict:
    rng = float(np.ptp(y)) or 1.0
    f = dict(start=dict(x=float(x[0]), y=float(y[0])), end=dict(x=float(x[-1]), y=float(y[-1])),
             global_max=dict(x=float(x[np.argmax(y)]), y=float(y.max())), global_min=dict(x=float(x[np.argmin(y)]), y=float(y.min())))
    if not drep.get("ok"):
        return f
    xg, yg, d1, d2 = drep["xg"], drep["y"], drep["d1"], drep["d2"]
    pk, _ = find_peaks(yg, prominence=0.05 * rng)
    vl, _ = find_peaks(-yg, prominence=0.05 * rng)
    f["local_max"] = [dict(x=float(xg[i]), y=float(yg[i])) for i in pk]
    f["local_min"] = [dict(x=float(xg[i]), y=float(yg[i])) for i in vl]
    dmax = float(np.max(np.abs(d1))) or 1.0
    flat = np.abs(d1) < 0.03 * dmax
    plateaus, i = [], 0
    while i < len(xg):
        if flat[i]:
            j = i
            while j + 1 < len(xg) and flat[j + 1]:
                j += 1
            if xg[j] - xg[i] >= 0.05 * (xg[-1] - xg[0]):
                plateaus.append(dict(x0=float(xg[i]), x1=float(xg[j]), y=float(np.mean(yg[i:j + 1]))))
            i = j + 1
        else:
            i += 1
    f["plateaus"] = plateaus
    tol = 0.01 * dmax
    up, dn = float(np.mean(d1 > tol)), float(np.mean(d1 < -tol))
    f["monotonicity"] = ("increasing" if up > 0.97 else "decreasing" if dn > 0.97 else
                         "non-decreasing (with plateaus)" if dn < 0.03 else "non-increasing (with plateaus)" if up < 0.03 else "non-monotonic")
    d2tol = 0.03 * (float(np.max(np.abs(d2))) or 1.0)
    f["convexity_segments"] = _segments(np.where(np.abs(d2) < d2tol, 0, np.sign(d2)), xg)
    kappa = DA.curvature(xg, yg, d1, d2)
    k = int(np.argmax(np.abs(kappa)))
    f["max_curvature"] = dict(x=float(xg[k]), value=float(kappa[k]), note="curvature in data units, kappa = y''/(1+y'^2)^(3/2)")
    f["turning_points"] = sorted([dict(x=p["x"], y=p["y"], type="maximum") for p in f["local_max"]] +
                                 [dict(x=p["x"], y=p["y"], type="minimum") for p in f["local_min"]], key=lambda t: t["x"])
    f["trend_changes"] = sorted([t["x"] for t in f["turning_points"]] + [p["x"] for p in drep.get("inflection_points", [])])
    f["zero_crossings"] = IX.zero_crossings(x, y)
    return f


def curve_metrics(x: np.ndarray, y: np.ndarray, drep: dict) -> dict:
    """Generic metrics that are useful for force-displacement / stress-strain like curves (no physical interpretation)."""
    i_pk = int(np.argmax(y))
    out = dict(peak_value=float(y[i_pk]), x_at_peak=float(x[i_pk]), last_value=float(y[-1]), x_last=float(x[-1]))
    if y[i_pk] != 0:
        out["drop_after_peak_percent"] = float((y[i_pk] - y[-1]) / abs(y[i_pk]) * 100)
        post = np.where((np.arange(len(y)) > i_pk) & (y <= 0.8 * y[i_pk]))[0]
        if len(post):
            out["x_at_80pct_of_peak_after_peak"] = float(x[post[0]])
        post = np.where((np.arange(len(y)) > i_pk) & (y <= 0.5 * y[i_pk]))[0]
        if len(post):
            out["x_at_50pct_of_peak_after_peak"] = float(x[post[0]])
    if i_pk >= 6:
        xr, yr = x[: i_pk + 1], y[: i_pk + 1]
        w = max(4, int(0.18 * len(xr)))
        best = None
        for s in range(0, len(xr) - w):
            xs, ys = xr[s:s + w], yr[s:s + w]
            if np.ptp(xs) == 0:
                continue
            sl, ic = np.polyfit(xs, ys, 1)
            ss = np.sum((ys - (sl * xs + ic)) ** 2)
            r2 = 1 - ss / (np.sum((ys - ys.mean()) ** 2) or 1e-300)
            if r2 >= 0.98 and (best is None or sl > best[0]):
                best = (sl, xs[0], xs[-1], r2)
        if best:
            out["max_slope_linear_window"] = dict(slope=float(best[0]), x0=float(best[1]), x1=float(best[2]), r2=float(best[3]),
                                                  note="steepest window (18% of the rising part) with R^2 >= 0.98")
        a = IA.integrate_series(xr, yr)
        if a.get("ok"):
            out["area_to_peak"] = a["trapezoid"]
    return out


def analyze_series(s: Series, chart: ChartResult, opts: dict | None = None) -> dict:
    o = {**DEFAULT_OPTS, **(opts or {})}
    res: dict = dict(name=s.name, kind=s.kind, axis=s.axis, n_points_total=len(s.points), n_by_status=s.n_by_status())
    if s.kind in ("pie",):
        res["skipped"] = "pie sector: no curve analysis"
        return res
    sel, used = DC.select_points(s.points, o["fit_source"], o["include_interpolated"])
    x, y, info = DC.clean_xy(sel)
    res.update(fit_source=used, n_used=len(x), cleaning=info)
    if len(x) < 3:
        res["skipped"] = "fewer than 3 usable points"
        return res
    out = DC.flag_outliers(x, y)
    res["outliers"] = [dict(x=float(a), y=float(b)) for a, b in zip(x[out], y[out])]
    dense = used.startswith("dense")
    res["stats"] = dict(x=SA.describe(x), y=SA.describe(y), xy=SA.xy_statistics(x, y, independent=not dense))
    if s.kind == "bars" or len(x) < 5:
        res["skipped_curve_analysis"] = "bar series / too few points: only descriptive statistics computed"
        res["integral"] = IA.integrate_series(x, y) if len(x) >= 3 else {}
        return to_jsonable(res)
    drep = DA.derivative_report(x, y, o["deriv_method"])
    res["features"] = curve_features(x, y, drep)
    res["metrics"] = curve_metrics(x, y, drep)
    if drep.get("ok"):
        res["derivative"] = dict(method=drep["method"], x=_down(drep["xg"]), y_smooth=_down(drep["y"]), d1=_down(drep["d1"]),
                                 d2=_down(drep["d2"]), max_slope=drep["max_slope"], min_slope=drep["min_slope"],
                                 mean_slope=drep["mean_slope"], inflection_points=drep["inflection_points"],
                                 note="Derivatives of digitised data amplify noise; they are computed from a noise-adaptive smoothing "
                                      "spline and are estimates, not exact values.")
    ig = IA.integrate_series(x, y)
    if ig.get("ok"):
        ig["cum_x"], ig["cum_y"] = _down(ig["cum_x"]), _down(ig["cum_y"])
    res["integral"] = ig
    if o["run_fits"]:
        fam = o["families"] or (CF.QUICK_FAMILIES if o["quick"] else CF.DEFAULT_FAMILIES)
        fr = CF.fit_all(x, y, fam, o["custom"], dense_data=dense)
        fits = [f.to_dict() for f in fr["fits"]]
        keep = {f["name"] for f in fits[:5]} | {fr["best"]}
        for f in fits:
            if f["name"] not in keep:
                f["x_fit"], f["y_fit"] = [], []
        res["fits"] = dict(models=fits, best=fr["best"], bic_best=fr["bic_best"], notes=fr["notes"], failures=fr["failures"])
    return to_jsonable(res)


def _series_xy(s: Series, o: dict):
    sel, _ = DC.select_points(s.points, o["fit_source"], o["include_interpolated"])
    x, y, _ = DC.clean_xy(sel)
    return x, y


def analyze_chart(chart: ChartResult, opts: dict | None = None, progress=None) -> dict:
    """Run the complete analysis for a chart; the result is stored in ``chart.analysis``."""
    o = {**DEFAULT_OPTS, **(opts or {})}
    out: dict = dict(series={}, options={k: v for k, v in o.items() if k != "families"})
    n = max(len(chart.series), 1)
    for i, s in enumerate(chart.series):
        if progress:
            progress(i / n, f"analysing {s.name}")
        try:
            out["series"][s.name] = analyze_series(s, chart, o)
        except Exception as exc:  # noqa: BLE001
            out["series"][s.name] = dict(name=s.name, error=str(exc))
    data = {}
    for s in chart.series:
        if s.kind in ("pie", "bars"):
            continue
        x, y = _series_xy(s, o)
        if len(x) >= 3:
            data[s.name] = (x, y)
    same_axis = {a: {n: v for n, v in data.items() if chart.series_by_name(n).axis == a} for a in ("y", "y2")}
    comp = {}
    for a, d in same_axis.items():
        if len(d) >= 2:
            comp[a] = CA.compare_series(d)
    if not comp and data:
        comp["y"] = CA.compare_series(data)
    out["comparison"] = comp
    out["intersections"] = [r for d in same_axis.values() if len(d) >= 2 for r in IX.intersections(d)]
    out["uncertainty"] = UA.digitization_uncertainty(chart)
    ya, xa = chart.y_axis, chart.x_axis
    xu, yu = (xa.unit if xa else None), (ya.unit if ya else None)
    out["units"] = dict(x=xu, y=yu, area=(f"{yu}·{xu}" if xu and yu else None),
                        x_title=(xa.title if xa else None), y_title=(ya.title if ya else None))
    if len(data) > 1 and any(a == "y2" for a in [s.axis for s in chart.series]):
        out["comparison_note"] = "series on different Y axes are compared only within their own axis"
    out["limitations"] = [
        "Data were digitised from a raster/vector image: reconstructed points are NOT original measurements.",
        "Fitted equations are approximate descriptions of the digitised curve, not the true law of the phenomenon.",
        "Derivatives and integrals are numerical estimates computed from the extracted points.",
    ]
    chart.analysis = out
    if progress:
        progress(1.0, "analysis complete")
    return out
