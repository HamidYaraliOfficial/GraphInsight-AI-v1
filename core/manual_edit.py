"""Manual corrections: add / delete / edit points, rename series, change colour or axis (all tracked as 'manual')."""
from __future__ import annotations

import numpy as np
import pandas as pd

from config import constants as C
from models.data_models import ChartResult, POINT_COLUMNS, ProjectState, Series
from .coordinate_transform import PlotTransform


def _tf(chart: ChartResult) -> PlotTransform:
    return PlotTransform(chart.x_axis.calibration if chart.x_axis else None, chart.y_axis.calibration if chart.y_axis else None,
                         chart.y2_axis.calibration if chart.y2_axis else None)


def _log(state: ProjectState, msg: str) -> None:
    state.manual_edits.append(msg)
    state.log("manual: " + msg)


def _pixel_from_data(chart: ChartResult, s: Series, x: float, y: float):
    tf = _tf(chart)
    if tf.x is None or tf.y_for(s.axis) is None:
        return np.nan, np.nan
    px, py = tf.to_pixel(np.array([x]), np.array([y]), s.axis)
    return float(px[0]), float(py[0])


def add_point(state: ProjectState, chart: ChartResult, series: str, x: float, y: float) -> None:
    s = chart.series_by_name(series)
    px, py = _pixel_from_data(chart, s, x, y)
    nid = float(s.points["idx"].max() + 1) if len(s.points) else 0.0
    row = pd.DataFrame([dict(idx=nid, x=x, y=y, px=px, py=py, status=C.ST_MANUAL, confidence=1.0, method="manual entry")])[POINT_COLUMNS]
    s.points = pd.concat([s.points, row], ignore_index=True)
    _log(state, f"added point ({x:.6g}, {y:.6g}) to '{series}'")


def delete_points(state: ProjectState, chart: ChartResult, series: str, idx_list) -> int:
    s = chart.series_by_name(series)
    before = len(s.points)
    s.points = s.points[~s.points.idx.isin(list(idx_list))].reset_index(drop=True)
    n = before - len(s.points)
    if s.errors is not None:
        s.errors = s.errors[~s.errors.idx.isin(list(idx_list))]
    _log(state, f"deleted {n} point(s) from '{series}'")
    return n


def apply_table_edits(state: ProjectState, chart: ChartResult, series: str, edited: pd.DataFrame) -> dict:
    """Apply an edited points table (from the dashboard data editor): changed x/y -> status 'manual'; new rows are added;
    rows missing from the edited table are deleted. Pixel coordinates are recomputed from the calibration."""
    s = chart.series_by_name(series)
    old = s.points.set_index("idx")
    e = edited.copy()
    e = e[[c for c in POINT_COLUMNS if c in e.columns]]
    changed = added = 0
    rows = []
    next_id = float(old.index.max() + 1) if len(old) else 0.0
    for _, r in e.iterrows():
        if pd.isna(r.get("x")) or pd.isna(r.get("y")):
            continue
        idx = r.get("idx")
        if pd.isna(idx) or idx not in old.index:
            px, py = _pixel_from_data(chart, s, r.x, r.y)
            rows.append(dict(idx=next_id, x=r.x, y=r.y, px=px, py=py, status=C.ST_MANUAL, confidence=1.0, method="manual entry"))
            next_id += 1
            added += 1
            continue
        o = old.loc[idx]
        if not (np.isclose(o.x, r.x, rtol=1e-12, atol=0) and np.isclose(o.y, r.y, rtol=1e-12, atol=0)):
            px, py = _pixel_from_data(chart, s, r.x, r.y)
            rows.append(dict(idx=idx, x=r.x, y=r.y, px=px, py=py, status=C.ST_MANUAL, confidence=1.0, method="manual edit"))
            changed += 1
        else:
            rows.append(dict(idx=idx, x=o.x, y=o.y, px=o.px, py=o.py, status=o.status, confidence=o.confidence, method=o.method))
    deleted = len(old) - (len(rows) - added)
    s.points = pd.DataFrame(rows, columns=POINT_COLUMNS) if rows else s.points.iloc[0:0]
    _log(state, f"table edit on '{series}': {changed} changed, {added} added, {max(deleted, 0)} deleted")
    return dict(changed=changed, added=added, deleted=max(deleted, 0))


def rename_series(state: ProjectState, chart: ChartResult, old: str, new: str) -> bool:
    if not new or chart.series_by_name(new):
        return False
    chart.series_by_name(old).name = new
    _log(state, f"renamed series '{old}' -> '{new}'")
    return True


def set_series_color(state: ProjectState, chart: ChartResult, name: str, rgb: tuple) -> None:
    chart.series_by_name(name).color = tuple(int(v) for v in rgb)
    _log(state, f"changed display colour of '{name}' to {tuple(rgb)}")


def set_series_axis(state: ProjectState, chart: ChartResult, name: str, axis: str) -> None:
    s = chart.series_by_name(name)
    tf = _tf(chart)
    if tf.y_for(axis) is None:
        return
    s.axis = axis
    xs, ys = tf.to_data(s.points.px.to_numpy(float), s.points.py.to_numpy(float), axis)
    s.points["x"], s.points["y"] = xs, ys
    _log(state, f"series '{name}' assigned to axis {axis}; values recomputed")


def set_axis_info(state: ProjectState, chart: ChartResult, which: str, title: str | None, unit: str | None) -> None:
    ax = {"x": chart.x_axis, "y": chart.y_axis, "y2": chart.y2_axis}[which]
    if ax is None:
        return
    ax.title, ax.unit = (title or None), (unit or None)
    _log(state, f"axis {which}: title='{title}' unit='{unit}'")
