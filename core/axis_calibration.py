"""Public axis-calibration API: build, validate and describe calibrations (manual and automatic)."""
from __future__ import annotations

import numpy as np

from .coordinate_transform import (AxisCalibration, PlotTransform, calibration_from_box, fit_calibration, format_datetime_value,
                                   parse_datetime_value)

__all__ = ["AxisCalibration", "PlotTransform", "fit_calibration", "calibration_from_box", "calibrate_manual", "validate_calibration",
           "calibration_error_at_ticks"]


def calibrate_manual(ticks: list, scale: str = "linear", categories: list | None = None) -> AxisCalibration | None:
    """Calibration from user-entered ticks [(pixel, value), ...].

    For ``scale='datetime'`` values may be ISO date strings; for ``'categorical'`` give ``categories`` (left-to-right)
    and the pixel positions of their centres.
    """
    if scale == "categorical":
        pix = [float(t[0]) for t in ticks]
        return fit_calibration(pix, list(range(len(pix))), scale="categorical", source="manual", categories=categories or [])
    vals = []
    for _, v in ticks:
        vals.append(parse_datetime_value(v) if (scale == "datetime" and isinstance(v, str)) else float(v))
    cal = fit_calibration([float(t[0]) for t in ticks], vals, scale="linear" if scale == "datetime" else scale, source="manual")
    if cal is not None and scale == "datetime":
        cal.scale = "datetime"
        cal.note = "date/time axis: values are seconds since 1970-01-01 (UTC)"
    return cal


def calibration_error_at_ticks(cal: AxisCalibration) -> dict:
    """Residuals of the reference ticks in pixels and in data units."""
    if cal is None or not cal.refs:
        return {}
    px = np.array([p for p, _ in cal.refs])
    vals = np.array([v for _, v in cal.refs])
    pred_px = cal.value_to_pixel(vals)
    return dict(residual_px=(pred_px - px).tolist(), max_abs_px=float(np.max(np.abs(pred_px - px))),
                residual_value=(cal.pixel_to_value(px) - vals).tolist())


def validate_calibration(cal: AxisCalibration | None, axis_length_px: float) -> list[str]:
    """Human-readable problems of a calibration (empty list = fine)."""
    if cal is None:
        return ["axis is not calibrated"]
    msgs = []
    if len(cal.refs) < 2:
        msgs.append("fewer than two reference ticks")
    elif len(cal.refs) == 2 and cal.scale != "piecewise":
        msgs.append("only two reference ticks: the calibration cannot be cross-checked (three or more are recommended)")
    if cal.rmse_px > max(2.0, 0.005 * axis_length_px):
        msgs.append(f"tick fit error is large ({cal.rmse_px:.1f}px)")
    if cal.outliers:
        msgs.append(f"{len(cal.outliers)} tick(s) rejected as outliers")
    if cal.source == "box":
        msgs.append("calibrated from the plot-area edges (assumes the axis limits equal the box edges)")
    return msgs
