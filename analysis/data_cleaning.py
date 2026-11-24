"""Preparing digitised points for analysis (sorting, de-duplication, outlier flags, source selection)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import constants as C


def select_points(points: pd.DataFrame, source: str = "auto", include_interpolated: bool = False) -> tuple[pd.DataFrame, str]:
    """Choose which points feed the analysis.

    auto    : original markers if there are at least 6, otherwise all reconstructed points
    markers : only real markers
    dense   : all reconstructed (and vector / manual) points
    """
    p = points.dropna(subset=["x", "y"])
    nm = int((p.status == C.ST_MARKER).sum())
    if source == "markers" or (source == "auto" and nm >= 6):
        sel = p[p.status.isin([C.ST_MARKER, C.ST_MANUAL, C.ST_VECTOR])]
        used = "markers"
    else:
        sel = p if include_interpolated else p[p.status != C.ST_INTERP]
        used = "dense (reconstructed from the line)"
    return sel, used


def clean_xy(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, dict]:
    """Sort by x, average duplicated x, drop non-finite values. Returns x, y, info."""
    d = df[["x", "y"]].replace([np.inf, -np.inf], np.nan).dropna().sort_values("x")
    n0 = len(d)
    if n0 == 0:
        return np.array([]), np.array([]), dict(n_in=0, n_out=0, merged=0)
    g = d.groupby("x", sort=True).mean()
    x, y = g.index.to_numpy(float), g["y"].to_numpy(float)
    return x, y, dict(n_in=n0, n_out=len(x), merged=n0 - len(x))


def noise_sigma(y: np.ndarray) -> float:
    """Robust noise estimate from the second difference (MAD)."""
    if len(y) < 5:
        return 0.0
    d2 = np.diff(y, 2)
    return float(1.4826 * np.median(np.abs(d2 - np.median(d2))) / np.sqrt(6.0))


def flag_outliers(x: np.ndarray, y: np.ndarray, z: float = 6.0) -> np.ndarray:
    """Boolean mask of points far from a running median (robust z-score on residuals)."""
    if len(y) < 9:
        return np.zeros(len(y), bool)
    k = max(5, (len(y) // 20) | 1)
    med = pd.Series(y).rolling(k, center=True, min_periods=1).median().to_numpy()
    r = y - med
    mad = 1.4826 * np.median(np.abs(r - np.median(r))) + 1e-12
    return np.abs(r) > z * mad


def is_dense(points: pd.DataFrame) -> bool:
    return int((points.status != C.ST_MARKER).sum()) > 0 and int((points.status == C.ST_MARKER).sum()) < 6
