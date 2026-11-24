"""Descriptive statistics, correlation and regression for one data series."""
from __future__ import annotations

import numpy as np
from scipy import stats

from ._compat import first, second


def _mode(y: np.ndarray):
    if len(y) < 3:
        return None
    k = max(5, int(np.ceil(np.log2(len(y)) + 1)))
    q75, q25 = np.percentile(y, [75, 25])
    iqr = q75 - q25
    if iqr > 0:
        bw = 2 * iqr / len(y) ** (1 / 3)
        k = int(np.clip(np.ceil(np.ptp(y) / bw), 5, 200))
    h, e = np.histogram(y, bins=k)
    i = int(np.argmax(h))
    return float((e[i] + e[i + 1]) / 2)


def describe(v: np.ndarray) -> dict:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    n = len(v)
    if n == 0:
        return dict(n=0)
    out = dict(n=n, mean=float(v.mean()), median=float(np.median(v)), mode_histogram=_mode(v),
               variance=float(v.var(ddof=1)) if n > 1 else 0.0, std=float(v.std(ddof=1)) if n > 1 else 0.0,
               min=float(v.min()), max=float(v.max()), range=float(np.ptp(v)),
               q1=float(np.percentile(v, 25)), q3=float(np.percentile(v, 75)))
    out["iqr"] = out["q3"] - out["q1"]
    for p in (5, 10, 90, 95):
        out[f"p{p}"] = float(np.percentile(v, p))
    out["skewness"] = float(stats.skew(v, bias=False)) if n > 2 else None
    out["kurtosis_excess"] = float(stats.kurtosis(v, bias=False)) if n > 3 else None
    out["sem"] = float(out["std"] / np.sqrt(n)) if n > 1 else None
    return out


def xy_statistics(x: np.ndarray, y: np.ndarray, independent: bool) -> dict:
    """Correlation / regression between x and y of ONE curve.

    ``independent`` is False for dense reconstructed points (they are samples of a line, not independent
    observations), in which case p-values are reported but flagged as not statistically meaningful.
    """
    n = len(x)
    out = dict(n=n, independent_observations=bool(independent))
    if n < 4 or np.ptp(x) == 0 or np.ptp(y) == 0:
        out["note"] = "not enough variation / points for correlation statistics"
        return out
    pr = stats.pearsonr(x, y)
    sr = stats.spearmanr(x, y)
    kt = stats.kendalltau(x, y)
    lr = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, n - 2)
    out.update(covariance=float(np.cov(x, y, ddof=1)[0, 1]), pearson_r=first(pr), pearson_p=second(pr),
               spearman_rho=first(sr), spearman_p=second(sr), kendall_tau=first(kt),
               kendall_p=second(kt),
               linear_regression=dict(slope=float(lr.slope), intercept=float(lr.intercept), r2=float(lr.rvalue ** 2),
                                      slope_stderr=float(lr.stderr), slope_ci95=[float(lr.slope - tcrit * lr.stderr),
                                                                                 float(lr.slope + tcrit * lr.stderr)],
                                      p_value=float(lr.pvalue)))
    if not independent:
        out["significance_note"] = ("Points were reconstructed along a line and are not independent observations: "
                                    "the p-values above must NOT be interpreted as evidence of statistical significance.")
        out["significance_available"] = False
    else:
        out["significance_available"] = True
        out["significance_note"] = "p-values assume independent observations, normally distributed residuals and no systematic error."
    return out
