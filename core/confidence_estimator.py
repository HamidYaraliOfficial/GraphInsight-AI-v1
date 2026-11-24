"""Confidence scores for points, series, calibration and the overall extraction quality."""
from __future__ import annotations

import numpy as np

from config import constants as C

BASE = {C.ST_MARKER: 0.92, C.ST_VECTOR: 0.99, C.ST_RECON: 0.85, C.ST_INTERP: 0.45, C.ST_MANUAL: 1.0}


def point_confidence(status, purity=1.0, ambiguity=1.0, steep=1.0, calibration=1.0):
    """Vectorised point confidence in [0, 1].

    status      : array of status strings
    purity      : colour purity of the pixels the point was computed from (0-1)
    ambiguity   : 1.0 = isolated, <1 when other series are very close (possible mix-up)
    steep       : <1 for very steep / thick runs (centre-line less certain)
    calibration : axis calibration confidence (0-1)
    """
    status = np.asarray(status, dtype=object)
    base = np.array([BASE.get(s, 0.7) for s in status], float)
    conf = base * np.asarray(purity) * np.asarray(ambiguity) * np.asarray(steep) * (0.5 + 0.5 * calibration)
    return np.clip(conf, 0.0, 1.0)


def series_confidence(point_conf: np.ndarray, coverage: float = 1.0) -> float:
    if len(point_conf) == 0:
        return 0.0
    return float(np.clip(np.mean(point_conf) * (0.6 + 0.4 * coverage), 0, 1))


def grade(score: float) -> str:
    return "excellent" if score >= 0.85 else "good" if score >= 0.7 else "fair" if score >= 0.5 else "poor"


def quality_assessment(image_w: int, image_h: int, scale: float, noise_sigma: float, cal_x, cal_y, ocr_scores: list,
                       series_conf: list, coverage: list, separation: float, n_series: int) -> dict:
    """Overall quality report (each component 0-1)."""
    res_score = float(np.clip(min(image_w, image_h) / 700.0, 0.2, 1.0)) * float(np.clip(1.0 - noise_sigma / 25.0, 0.4, 1.0))
    cal_score = float(np.mean([c.confidence for c in (cal_x, cal_y) if c is not None])) if (cal_x or cal_y) else 0.0
    if cal_x is None or cal_y is None:
        cal_score *= 0.5
    ocr_score = float(np.mean(ocr_scores)) if ocr_scores else 0.0
    sep_score = float(np.clip(separation, 0, 1))
    cov_score = float(np.mean(coverage)) if coverage else 0.0
    conf_score = float(np.mean(series_conf)) if series_conf else 0.0
    parts = dict(image_resolution=res_score, calibration=cal_score, ocr=ocr_score, curve_separation=sep_score,
                 point_coverage=cov_score, point_confidence=conf_score)
    w = dict(image_resolution=0.12, calibration=0.28, ocr=0.12, curve_separation=0.14, point_coverage=0.14,
             point_confidence=0.20)
    overall = float(sum(parts[k] * w[k] for k in parts))
    return dict(parts={k: round(v, 3) for k, v in parts.items()}, overall=round(overall, 3), grade=grade(overall),
                n_series=n_series, resize_scale=scale, noise_sigma=round(noise_sigma, 2))
