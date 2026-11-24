"""Model library and non-linear curve fitting with metrics, uncertainty and equation formatting."""
from __future__ import annotations

import math
import re
import warnings
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
from scipy import optimize, stats
from scipy.interpolate import BSpline, UnivariateSpline

from config import constants as C
from models.analysis_models import FitResult


def sig(v: float, n: int = 6) -> str:
    if v == 0 or not np.isfinite(v):
        return "0" if v == 0 else str(v)
    return f"{v:.{n}g}"


@dataclass
class Model:
    key: str
    name: str
    params: list
    func: Callable
    p0: Callable          # (x, y) -> list of initial guesses (list of lists)
    text: str             # "y = {a}*exp({b}*x)"
    latex: str
    python: str
    excel: str
    domain: Callable = lambda x, y: True
    bounds: tuple | None = None
    notes: str = ""

    @property
    def k(self) -> int:
        return len(self.params)


def _lin_p0(x, y):
    a, b = np.polyfit(x, y, 1)
    return [[a, b]]


def _exp_p0(x, y):
    out = []
    s = np.sign(np.median(y)) or 1.0
    ok = (s * y) > 0
    if ok.sum() >= 3:
        b, la = np.polyfit(x[ok], np.log(s * y[ok]), 1)
        out.append([s * math.exp(la), b])
    out += [[y.max() - y.min() or 1.0, 0.1 / (np.ptp(x) or 1.0)], [y.max() or 1.0, -1.0 / (np.ptp(x) or 1.0)]]
    return out


def _expo_p0(x, y):
    return [p + [float(np.min(y))] for p in _exp_p0(x, y)] + [[np.ptp(y), -3.0 / (np.ptp(x) or 1.0), float(np.min(y))]]


def _log_p0(x, y):
    a, b = np.polyfit(np.log(x), y, 1)
    return [[a, b]]


def _pow_p0(x, y):
    ok = (x > 0) & (y > 0)
    if ok.sum() >= 3:
        b, la = np.polyfit(np.log(x[ok]), np.log(y[ok]), 1)
        return [[math.exp(la), b], [1.0, 1.0]]
    return [[1.0, 1.0]]


def _logistic_p0(x, y):
    return [[np.ptp(y) * 1.1, 4.0 / (np.ptp(x) or 1), float(np.median(x))], [np.ptp(y), -4.0 / (np.ptp(x) or 1), float(np.median(x))]]


def _sig4_p0(x, y):
    return [[float(np.min(y)), np.ptp(y) * 1.05, 4.0 / (np.ptp(x) or 1), float(np.median(x))],
            [float(np.max(y)), -np.ptp(y) * 1.05, 4.0 / (np.ptp(x) or 1), float(np.median(x))]]


def _gauss_p0(x, y):
    i = int(np.argmax(np.abs(y - np.median(y))))
    return [[float(y[i]), float(x[i]), np.ptp(x) / 6.0 or 1.0]]


def _gauss_off_p0(x, y):
    return [[float(np.ptp(y)), float(x[int(np.argmax(y))]), np.ptp(x) / 6.0 or 1.0, float(np.min(y))],
            [-float(np.ptp(y)), float(x[int(np.argmin(y))]), np.ptp(x) / 6.0 or 1.0, float(np.max(y))]]


def _sin_p0(x, y):
    xs = np.linspace(x.min(), x.max(), len(x))
    ys = np.interp(xs, x, y) - np.mean(y)
    f = np.fft.rfftfreq(len(xs), d=(xs[1] - xs[0]))
    sp = np.abs(np.fft.rfft(ys))
    sp[0] = 0
    f0 = f[int(np.argmax(sp))] or 1.0 / (np.ptp(x) or 1.0)
    out = []
    for ph in (0.0, math.pi / 2, math.pi, 3 * math.pi / 2):
        out.append([np.ptp(y) / 2.0, 2 * math.pi * f0, ph, float(np.mean(y))])
    return out


def _rat_p0(x, y):
    return [[1.0, float(np.mean(y)), 0.01], [float(np.ptp(y) / (np.ptp(x) or 1)), float(y[0]), 0.1 / (np.ptp(x) or 1)]]


def _sat_p0(x, y):
    return [[float(np.ptp(y) * 1.1), 3.0 / (np.ptp(x) or 1)], [float(np.max(y)), 1.0 / (np.ptp(x) or 1)]]


def _mm_p0(x, y):
    return [[float(np.max(y) * 1.2), float(np.median(x))]]


def _poly_model(deg: int) -> Model:
    names = [chr(ord("a") + i) for i in range(deg + 1)]
    terms_t, terms_l, terms_p, terms_x = [], [], [], []
    for i, n in enumerate(names):
        p = deg - i
        if p == 0:
            terms_t.append("{%s}" % n); terms_l.append("{%s}" % n); terms_p.append("{%s}" % n); terms_x.append("{%s}" % n)
        elif p == 1:
            terms_t.append("{%s}*x" % n); terms_l.append("{%s}x" % n); terms_p.append("{%s}*x" % n); terms_x.append("{%s}*x" % n)
        else:
            terms_t.append("{%s}*x^%d" % (n, p)); terms_l.append("{%s}x^{%d}" % (n, p))
            terms_p.append("{%s}*x**%d" % (n, p)); terms_x.append("{%s}*x^%d" % (n, p))
    label = {1: "Linear", 2: "Quadratic", 3: "Cubic"}.get(deg, f"Polynomial (degree {deg})")
    return Model(f"poly{deg}", label, names, lambda x, *p: np.polyval(p, x), lambda x, y, d=deg: [list(np.polyfit(x, y, d))],
                 "y = " + " + ".join(terms_t), "y = " + " + ".join(terms_l), " + ".join(terms_p), " + ".join(terms_x))


def library() -> dict[str, Model]:
    M: dict[str, Model] = {}
    for d in range(1, 7):
        M[f"poly{d}"] = _poly_model(d)
    M["exp"] = Model("exp", "Exponential", ["a", "b"], lambda x, a, b: a * np.exp(b * x), _exp_p0,
                     "y = {a}*exp({b}*x)", r"y = {a}\,e^{{{b}x}}", "{a}*np.exp({b}*x)", "{a}*EXP({b}*x)")
    M["exp_off"] = Model("exp_off", "Exponential with offset", ["a", "b", "c"], lambda x, a, b, c: a * np.exp(b * x) + c, _expo_p0,
                         "y = {a}*exp({b}*x) + {c}", r"y = {a}\,e^{{{b}x}} + {c}", "{a}*np.exp({b}*x) + {c}", "{a}*EXP({b}*x) + {c}")
    M["log"] = Model("log", "Logarithmic", ["a", "b"], lambda x, a, b: a * np.log(x) + b, _log_p0,
                     "y = {a}*ln(x) + {b}", r"y = {a}\,\ln(x) + {b}", "{a}*np.log(x) + {b}", "{a}*LN(x) + {b}",
                     domain=lambda x, y: bool(np.all(x > 0)))
    M["power"] = Model("power", "Power law", ["a", "b"], lambda x, a, b: a * np.power(x, b), _pow_p0,
                       "y = {a}*x^{b}", r"y = {a}\,x^{{{b}}}", "{a}*x**{b}", "{a}*x^{b}",
                       domain=lambda x, y: bool(np.all(x > 0)))
    M["logistic"] = Model("logistic", "Logistic (sigmoid)", ["L", "k", "x0"], lambda x, L, k, x0: L / (1 + np.exp(-np.clip(k * (x - x0), -500, 500))),
                          _logistic_p0, "y = {L}/(1 + exp(-{k}*(x - {x0})))", r"y = \dfrac{{{L}}}{{1+e^{{-{k}(x-{x0})}}}}",
                          "{L}/(1 + np.exp(-{k}*(x - {x0})))", "{L}/(1+EXP(-{k}*(x-{x0})))")
    M["sigmoid4"] = Model("sigmoid4", "Sigmoid with baseline", ["b", "L", "k", "x0"],
                          lambda x, b, L, k, x0: b + L / (1 + np.exp(-np.clip(k * (x - x0), -500, 500))), _sig4_p0,
                          "y = {b} + {L}/(1 + exp(-{k}*(x - {x0})))", r"y = {b} + \dfrac{{{L}}}{{1+e^{{-{k}(x-{x0})}}}}",
                          "{b} + {L}/(1 + np.exp(-{k}*(x - {x0})))", "{b}+{L}/(1+EXP(-{k}*(x-{x0})))")
    M["gauss"] = Model("gauss", "Gaussian", ["a", "m", "s"], lambda x, a, m, s: a * np.exp(-((x - m) ** 2) / (2 * s ** 2)), _gauss_p0,
                       "y = {a}*exp(-(x - {m})^2/(2*{s}^2))", r"y = {a}\,e^{{-\frac{{(x-{m})^2}}{{2\cdot{s}^2}}}}",
                       "{a}*np.exp(-(x - {m})**2/(2*{s}**2))", "{a}*EXP(-(x-{m})^2/(2*{s}^2))")
    M["gauss_off"] = Model("gauss_off", "Gaussian with baseline", ["a", "m", "s", "c"],
                           lambda x, a, m, s, c: a * np.exp(-((x - m) ** 2) / (2 * s ** 2)) + c, _gauss_off_p0,
                           "y = {a}*exp(-(x - {m})^2/(2*{s}^2)) + {c}", r"y = {a}\,e^{{-\frac{{(x-{m})^2}}{{2\cdot{s}^2}}}} + {c}",
                           "{a}*np.exp(-(x - {m})**2/(2*{s}**2)) + {c}", "{a}*EXP(-(x-{m})^2/(2*{s}^2))+{c}")
    M["sin"] = Model("sin", "Sinusoidal", ["a", "w", "phi", "c"], lambda x, a, w, phi, c: a * np.sin(w * x + phi) + c, _sin_p0,
                     "y = {a}*sin({w}*x + {phi}) + {c}", r"y = {a}\sin({w}x+{phi}) + {c}",
                     "{a}*np.sin({w}*x + {phi}) + {c}", "{a}*SIN({w}*x+{phi})+{c}")
    M["rational"] = Model("rational", "Rational (1/1)", ["a", "b", "c"], lambda x, a, b, c: (a * x + b) / (1 + c * x), _rat_p0,
                          "y = ({a}*x + {b})/(1 + {c}*x)", r"y = \dfrac{{{a}x+{b}}}{{1+{c}x}}",
                          "({a}*x + {b})/(1 + {c}*x)", "({a}*x+{b})/(1+{c}*x)")
    M["saturation"] = Model("saturation", "Saturation (1 - exp)", ["a", "b"], lambda x, a, b: a * (1 - np.exp(-b * x)), _sat_p0,
                            "y = {a}*(1 - exp(-{b}*x))", r"y = {a}\left(1-e^{{-{b}x}}\right)",
                            "{a}*(1 - np.exp(-{b}*x))", "{a}*(1-EXP(-{b}*x))")
    M["mm"] = Model("mm", "Michaelis-Menten", ["a", "b"], lambda x, a, b: a * x / (b + x), _mm_p0,
                    "y = {a}*x/({b} + x)", r"y = \dfrac{{{a}x}}{{{b}+x}}", "{a}*x/({b} + x)", "{a}*x/({b}+x)",
                    domain=lambda x, y: bool(np.all(x >= 0)))
    return M


# families tried by default (speed vs coverage)
DEFAULT_FAMILIES = ["poly1", "poly2", "poly3", "poly4", "poly5", "exp", "exp_off", "log", "power", "logistic", "sigmoid4",
                    "gauss", "gauss_off", "sin", "rational", "saturation", "mm", "piecewise2", "piecewise3", "spline"]
QUICK_FAMILIES = ["poly1", "poly2", "poly3", "exp", "log", "power", "logistic", "gauss", "saturation", "piecewise2", "spline"]


# ----------------------------------------------------------------- formatting
def _fmt_param(v: float) -> str:
    s = sig(v, 6)
    return f"({s})" if v < 0 else s


def format_equation(model: Model, params: dict) -> dict:
    def sub(tpl: str, neg_paren: bool) -> str:
        out = tpl
        for n, v in params.items():
            val = _fmt_param(v) if neg_paren else sig(v, 6)
            out = out.replace("{%s}" % n, val)
        return out
    text = sub(model.text, True)
    latex = sub(model.latex, True)
    # tidy "+ (-3)" -> "- 3"
    text = re.sub(r"\+ \((-[\d.e+\-]+)\)", lambda m: "- " + m.group(1)[1:], text)
    latex = re.sub(r"\+ \((-[\d.e+\-]+)\)", lambda m: "- " + m.group(1)[1:], latex)
    return dict(text=text, latex=latex, python="lambda x: " + sub(model.python, True), excel="=" + sub(model.excel, True))


def excel_formula(equation_excel: str, xref: str) -> str:
    """Replace the symbol x in an Excel template by a cell reference (e.g. A2)."""
    return re.sub(r"(?<![A-Za-z])x(?![A-Za-z0-9])", xref, equation_excel)


# -------------------------------------------------------------------- metrics
def metrics_for(y: np.ndarray, yhat: np.ndarray, k: int) -> dict:
    n = len(y)
    res = y - yhat
    sse = float(np.sum(res ** 2))
    sst = float(np.sum((y - np.mean(y)) ** 2)) or 1e-300
    mse = sse / n
    r2 = 1 - sse / sst
    dof = n - k - 1
    adj = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else float("nan")
    mape = float(np.mean(np.abs(res / y)) * 100) if np.all(np.abs(y) > 1e-9 * (np.ptp(y) or 1)) and np.all(y != 0) else None
    lnl = n * math.log(max(sse / n, 1e-300))
    aic = lnl + 2 * k
    bic = lnl + k * math.log(n)
    aicc = aic + (2 * k * (k + 1) / (n - k - 1) if n - k - 1 > 0 else float("inf"))
    return dict(r2=float(r2), adj_r2=float(adj), rmse=float(math.sqrt(mse)), mae=float(np.mean(np.abs(res))), mse=float(mse),
                mape=mape, sse=sse, aic=float(aic), bic=float(bic), aicc=float(aicc))


def residual_analysis(x: np.ndarray, res: np.ndarray) -> dict:
    n = len(res)
    out = dict(mean=float(np.mean(res)), std=float(np.std(res, ddof=1)) if n > 1 else 0.0, max_abs=float(np.max(np.abs(res))))
    if n >= 8:
        sub = res if n <= 5000 else np.random.default_rng(0).choice(res, 5000, replace=False)
        try:
            out["shapiro_p"] = float(stats.shapiro(sub)[1])
        except Exception:  # noqa: BLE001
            out["shapiro_p"] = None
        d = np.diff(res)
        out["durbin_watson"] = float(np.sum(d ** 2) / (np.sum(res ** 2) or 1e-300))
        r = res - res.mean()
        out["lag1_autocorr"] = float(np.sum(r[1:] * r[:-1]) / (np.sum(r ** 2) or 1e-300))
        signs = np.sign(res)
        out["runs"] = int(1 + np.sum(signs[1:] != signs[:-1]))
        out["systematic_pattern"] = bool(out["lag1_autocorr"] > 0.6 and out["runs"] < n / 5)
    return out


def _cv_rmse(model: Model, x, y, p_final, folds: int = 5) -> float | None:
    n = len(x)
    if n < 12:
        return None
    k = min(folds, n // 4)
    idx = np.random.default_rng(1).permutation(n)
    errs = []
    for f in range(k):
        te = idx[f::k]
        tr = np.setdiff1d(idx, te)
        try:
            if model.key.startswith("poly"):
                p = np.polyfit(x[tr], y[tr], int(model.key[4:]))
                pred = np.polyval(p, x[te])
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    p, _ = optimize.curve_fit(model.func, x[tr], y[tr], p0=p_final, maxfev=4000)
                pred = model.func(x[te], *p)
            errs.append(np.mean((y[te] - pred) ** 2))
        except Exception:  # noqa: BLE001
            return None
    return float(math.sqrt(np.mean(errs))) if errs else None


# ------------------------------------------------------------------- fitting
def _grid(x, f, n=200):
    xg = np.linspace(float(np.min(x)), float(np.max(x)), n)
    return xg.tolist(), np.asarray(f(xg), float).tolist()


def _finish(model_name, family, k, params, eq, x, y, yhat, func, method, extra_warn, source_note, cv, n, uncert=None):
    m = metrics_for(y, yhat, k)
    m["cv_rmse"] = cv
    xs, ys = _grid(x, func)
    return FitResult(name=model_name, family=family, n_params=k, params=params, equation=eq, metrics=m,
                     residuals=residual_analysis(x, y - yhat), valid_range=(float(np.min(x)), float(np.max(x))), n_points=n,
                     method=method, warnings=extra_warn, x_fit=xs, y_fit=ys)


def fit_model(model: Model, x: np.ndarray, y: np.ndarray, dense_data: bool = False) -> FitResult | None:
    n = len(x)
    if n < model.k + 2 or not model.domain(x, y):
        return None
    best = None
    warn: list[str] = []
    if model.key.startswith("poly"):
        deg = int(model.key[4:])
        if n < deg + 3:
            return None
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            p, cov = np.polyfit(x, y, deg, cov=True) if n > deg + 2 else (np.polyfit(x, y, deg), None)
        popt, pcov = np.asarray(p), cov
        method = "least squares (numpy.polyfit)"
    else:
        for p0 in model.p0(x, y):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    kw = dict(maxfev=20000)
                    if model.bounds:
                        kw["bounds"] = model.bounds
                    popt, pcov = optimize.curve_fit(model.func, x, y, p0=p0, **kw)
                yhat = model.func(x, *popt)
                if not np.all(np.isfinite(yhat)):
                    continue
                sse = float(np.sum((y - yhat) ** 2))
                if best is None or sse < best[0]:
                    best = (sse, popt, pcov)
            except Exception:  # noqa: BLE001
                continue
        if best is None:
            return None
        _, popt, pcov = best
        method = "non-linear least squares (scipy.optimize.curve_fit, trf)"
    yhat = model.func(x, *popt)
    params, tcrit = {}, stats.t.ppf(0.975, max(n - model.k, 1))
    se = np.sqrt(np.clip(np.diag(pcov), 0, None)) if pcov is not None and np.all(np.isfinite(pcov)) else np.full(model.k, np.nan)
    for i, nm in enumerate(model.params):
        params[nm] = dict(value=float(popt[i]), stderr=float(se[i]) if np.isfinite(se[i]) else None,
                          ci_low=float(popt[i] - tcrit * se[i]) if np.isfinite(se[i]) else None,
                          ci_high=float(popt[i] + tcrit * se[i]) if np.isfinite(se[i]) else None)
    if np.any(~np.isfinite(se)):
        warn.append("parameter uncertainty could not be estimated (singular covariance)")
    if dense_data:
        warn.append("dense digitised points are strongly correlated: standard errors / CIs are optimistic")
    if n / model.k < 5:
        warn.append(f"few points per parameter (n/k = {n / model.k:.1f}): risk of over-fitting")
    eq = format_equation(model, {nm: popt[i] for i, nm in enumerate(model.params)})
    cv = _cv_rmse(model, x, y, popt)
    return _finish(model.name, model.key, model.k, params, eq, x, y, yhat, lambda xx: model.func(xx, *popt), method, warn, "", cv, n)


# ---- piecewise linear (continuous) ------------------------------------------
def _pw_design(x, bps):
    cols = [np.ones_like(x), x - bps[0]]
    for b in bps:
        cols.append(np.maximum(x - b, 0.0))
    return np.vstack(cols).T


def fit_piecewise(x, y, n_seg: int = 2, dense_data=False) -> FitResult | None:
    n = len(x)
    nb = n_seg - 1
    k = 2 + 2 * nb
    if n < max(12, 3 * k):
        return None
    cand = np.quantile(x, np.linspace(0.08, 0.92, 30 if nb == 1 else 16))
    best = None
    import itertools
    combos = [(b,) for b in cand] if nb == 1 else [c for c in itertools.combinations(cand, 2) if c[1] - c[0] > 0.1 * np.ptp(x)]
    for bps in combos:
        A = _pw_design(x, bps)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        sse = float(np.sum((y - A @ coef) ** 2))
        if best is None or sse < best[0]:
            best = (sse, bps, coef)
    if best is None:
        return None
    # refine break points
    def obj(b):
        b = np.sort(b)
        A = _pw_design(x, b)
        coef, *_ = np.linalg.lstsq(A, y, rcond=None)
        return float(np.sum((y - A @ coef) ** 2))
    r = optimize.minimize(obj, best[1], method="Nelder-Mead", options=dict(xatol=1e-6 * np.ptp(x), maxiter=400))
    bps = tuple(np.sort(r.x)) if r.fun <= best[0] else best[1]
    A = _pw_design(x, bps)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    yhat = A @ coef

    def f(xx):
        return _pw_design(np.asarray(xx, float), bps) @ coef
    c0, s1 = coef[0], coef[1]
    slopes = [s1]
    for j in range(nb):
        slopes.append(slopes[-1] + coef[2 + j])
    params = {"y_at_b1": dict(value=float(c0), stderr=None, ci_low=None, ci_high=None)}
    for i, s in enumerate(slopes):
        params[f"slope{i + 1}"] = dict(value=float(s), stderr=None, ci_low=None, ci_high=None)
    for j, b in enumerate(bps):
        params[f"break{j + 1}"] = dict(value=float(b), stderr=None, ci_low=None, ci_high=None)
    k = len(params)
    b1 = bps[0]
    if nb == 1:
        text = f"y = {sig(c0)} + {sig(slopes[0])}*(x - {sig(b1)}) for x < {sig(b1)};  y = {sig(c0)} + {sig(slopes[1])}*(x - {sig(b1)}) for x >= {sig(b1)}"
        xl = "=IF(x<%s,%s+%s*(x-%s),%s+%s*(x-%s))" % tuple(sig(v) for v in (b1, c0, slopes[0], b1, c0, slopes[1], b1))
    else:
        b2 = bps[1]
        y2 = c0 + slopes[1] * (b2 - b1)
        text = (f"y = {sig(c0)} + {sig(slopes[0])}*(x - {sig(b1)}) for x < {sig(b1)};  y = {sig(c0)} + {sig(slopes[1])}*(x - {sig(b1)}) for "
                f"{sig(b1)} <= x < {sig(b2)};  y = {sig(y2)} + {sig(slopes[2])}*(x - {sig(b2)}) for x >= {sig(b2)}")
        xl = "=IF(x<%s,%s+%s*(x-%s),IF(x<%s,%s+%s*(x-%s),%s+%s*(x-%s)))" % tuple(
            sig(v) for v in (b1, c0, slopes[0], b1, b2, c0, slopes[1], b1, y2, slopes[2], b2))
    py = ("lambda x: np.interp(x, " + str([float(v) for v in [x.min(), *bps, x.max()]]) + ", " +
          str([float(v) for v in f(np.array([x.min(), *bps, x.max()]))]) + ")")
    eq = dict(text=text, latex=r"\text{continuous piecewise-linear function with %d segments}" % n_seg, python=py, excel=xl)
    warn = ["break points were estimated from the data (flexible model)"]
    if dense_data:
        warn.append("dense digitised points are strongly correlated: uncertainty is optimistic")
    cv = None
    return _finish(f"Piecewise linear ({n_seg} segments)", f"piecewise{n_seg}", k, params, eq, x, y, yhat, f,
                   "segmented least squares with break-point search", warn, "", cv, n)


def fit_spline(x, y, dense_data=False) -> FitResult | None:
    n = len(x)
    if n < 10:
        return None
    from .data_cleaning import noise_sigma
    sg = max(noise_sigma(y), 1e-9 * (np.ptp(y) or 1))
    spl = UnivariateSpline(x, y, k=3, s=n * sg ** 2)
    t, c, kdeg = spl._eval_args
    yhat = spl(x)
    k = max(len(t) - 4, 4)
    eq = dict(text=f"cubic smoothing spline with {len(t)} knots (no closed-form expression)",
              latex=r"\text{cubic smoothing spline}",
              python=(f"BSpline({np.round(t, 8).tolist()}, {np.round(c, 8).tolist()}, 3)" if len(t) <= 60 else "see JSON export"),
              excel="(not representable as a single cell formula)")
    params = {"n_knots": dict(value=float(len(t)), stderr=None, ci_low=None, ci_high=None)}
    warn = ["spline interpolation is a smooth descriptor, not an analytical model of the phenomenon"]
    return _finish("Cubic smoothing spline", "spline", k, params, eq, x, y, yhat, spl, "scipy UnivariateSpline (s from noise estimate)",
                   warn, "", None, n)


# ----------------------------------------------------------- custom expression
_ALLOWED_FUNCS = {"sin", "cos", "tan", "exp", "log", "ln", "sqrt", "tanh", "sinh", "cosh", "atan", "abs", "pow"}


def parse_custom(expr: str) -> Model:
    """Build a model from a user expression in x, e.g. 'a*x**2 + b*sin(c*x)'. Safe-parsed with SymPy."""
    import sympy as sp
    e = expr.strip().replace("^", "**")
    if not re.fullmatch(r"[A-Za-z0-9_+\-*/().,\s]+", e) or "__" in e:
        raise ValueError("Only numbers, names, + - * / ** ( ) are allowed in a custom model.")
    names = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", e))
    bad = [n for n in names if n not in _ALLOWED_FUNCS and n != "x" and (len(n) > 3 or n in ("pi",))]
    if bad:
        raise ValueError(f"Unsupported name(s): {bad}. Use short parameter names (a, b, c, ...) and x.")
    local = {n: sp.Symbol(n) for n in names if n not in _ALLOWED_FUNCS}
    local.update({"ln": sp.log, "log": sp.log, "exp": sp.exp, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan, "sqrt": sp.sqrt,
                  "tanh": sp.tanh, "sinh": sp.sinh, "cosh": sp.cosh, "atan": sp.atan, "abs": sp.Abs})
    sym = sp.sympify(e, locals=local)
    xs = sp.Symbol("x")
    params = sorted([s.name for s in sym.free_symbols if s.name != "x"])
    if not params or len(params) > 6:
        raise ValueError("A custom model needs between 1 and 6 free parameters.")
    f = sp.lambdify([xs] + [sp.Symbol(p) for p in params], sym, modules="numpy")
    ex = str(sym).replace("**", "^")
    return Model("custom", f"Custom: {expr}", params, lambda x, *p: np.asarray(f(x, *p), float) * np.ones_like(x),
                 lambda x, y: [[1.0] * len(params), [0.1] * len(params), [float(np.ptp(y) or 1)] * len(params)],
                 "y = " + re.sub(r"\b(" + "|".join(params) + r")\b", r"{\1}", str(sym)),
                 "y = " + re.sub(r"\b(" + "|".join(params) + r")\b", r"{\1}", sp.latex(sym).replace("{", "{{").replace("}", "}}")),
                 re.sub(r"\b(" + "|".join(params) + r")\b", r"{\1}", str(sym)), re.sub(r"\b(" + "|".join(params) + r")\b", r"{\1}", ex))


# ---------------------------------------------------------------- orchestration
def fit_all(x: np.ndarray, y: np.ndarray, families: list[str] | None = None, custom: list[str] | None = None,
            dense_data: bool = False) -> dict:
    """Fit all requested families and rank them."""
    families = families or DEFAULT_FAMILIES
    lib = library()
    fits: list[FitResult] = []
    failures = []
    for fam in families:
        try:
            if fam.startswith("piecewise"):
                r = fit_piecewise(x, y, int(fam[-1]), dense_data)
            elif fam == "spline":
                r = fit_spline(x, y, dense_data)
            else:
                r = fit_model(lib[fam], x, y, dense_data) if fam in lib else None
        except Exception as exc:  # noqa: BLE001
            r = None
            failures.append(f"{fam}: {exc}")
        if r is not None and np.isfinite(r.metrics["rmse"]):
            fits.append(r)
        elif fam in lib or fam.startswith("piecewise") or fam == "spline":
            failures.append(fam)
    for ex in custom or []:
        try:
            m = parse_custom(ex)
            r = fit_model(m, x, y, dense_data)
            if r:
                fits.append(r)
            else:
                failures.append(f"custom '{ex}': did not converge")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"custom '{ex}': {exc}")
    if not fits:
        return dict(fits=[], best=None, bic_best=None, notes=["no model could be fitted"], failures=failures)
    fits.sort(key=lambda f: f.metrics["bic"])
    b0 = fits[0].metrics["bic"]
    bic_best_name = next((f.name for f in fits if f.family != "spline"), fits[0].name)
    w = np.exp(-0.5 * np.array([f.metrics["bic"] - b0 for f in fits]))
    w = w / w.sum()
    for f, wi in zip(fits, w):
        f.metrics["delta_bic"] = float(f.metrics["bic"] - b0)
        f.metrics["bic_weight"] = float(wi)
    analytic = [f for f in fits if f.family != "spline"] or fits
    rm = min(f.metrics["rmse"] for f in analytic)
    rng = float(np.ptp(y)) or 1.0
    cands = [f for f in analytic if f.metrics["rmse"] <= max(1.15 * rm, rm + 0.0025 * rng)]
    best = min(cands, key=lambda f: (f.n_params, f.metrics["bic"]))
    notes = ["The selected model is an APPROXIMATE description of the digitised data; it is not proof of the true law "
             "that generated the data. Several model families can fit a limited set of points equally well.",
             "Selection rule: smallest number of parameters among models whose RMSE is within 15% (or 0.25% of the y-range) "
             "of the best RMSE, ties broken by BIC."]
    if best.family.startswith("poly") and best.n_params >= 5:
        notes.append("A high-degree polynomial was selected: check for over-fitting outside the data range.")
    return dict(fits=fits, best=best.name, bic_best=bic_best_name, notes=notes, failures=failures)
