"""Core dataclasses shared by the engine, analysis, storage and dashboard."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from core.coordinate_transform import AxisCalibration

POINT_COLUMNS = ["idx", "x", "y", "px", "py", "status", "confidence", "method"]


def to_jsonable(obj):
    """Recursively convert numpy / pandas / dataclass objects to JSON-serialisable types."""
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return to_jsonable(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if np.isfinite(f) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return to_jsonable(obj.to_dict("records"))
    if isinstance(obj, pd.Series):
        return to_jsonable(obj.tolist())
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return to_jsonable(obj.to_dict())
    return obj


def empty_points() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="float64" if c not in ("status", "method") else "object")
                         for c in POINT_COLUMNS})


@dataclass
class AxisTick:
    pixel: float
    label: str | None = None
    value: float | None = None
    conf: float = 0.0
    source: str = "ocr"

    def to_dict(self):
        return dict(pixel=self.pixel, label=self.label, value=self.value, conf=self.conf, source=self.source)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: d.get(k) for k in ("pixel", "label", "value", "conf", "source") if k in d})


@dataclass
class AxisInfo:
    orientation: str = "x"                     # x | y
    side: str = "bottom"                       # bottom | left | right | top
    line_pos: float = 0.0
    ticks: list = field(default_factory=list)  # list[AxisTick]
    title: str | None = None
    unit: str | None = None
    raw_title: str | None = None
    title_conf: float = 0.0
    tick_direction: str = "out"
    label_color: tuple | None = None
    calibration: AxisCalibration | None = None
    warnings: list = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.title and self.unit:
            return f"{self.title} ({self.unit})"
        return self.title or ("unknown" if not self.unit else f"({self.unit})")

    def to_dict(self):
        return dict(orientation=self.orientation, side=self.side, line_pos=self.line_pos,
                    ticks=[t.to_dict() for t in self.ticks], title=self.title, unit=self.unit,
                    raw_title=self.raw_title, title_conf=self.title_conf, tick_direction=self.tick_direction,
                    label_color=list(self.label_color) if self.label_color else None,
                    calibration=self.calibration.to_dict() if self.calibration else None,
                    warnings=list(self.warnings))

    @classmethod
    def from_dict(cls, d):
        if not d:
            return None
        return cls(orientation=d.get("orientation", "x"), side=d.get("side", "bottom"),
                   line_pos=d.get("line_pos", 0.0), ticks=[AxisTick.from_dict(t) for t in d.get("ticks", [])],
                   title=d.get("title"), unit=d.get("unit"), raw_title=d.get("raw_title"),
                   title_conf=d.get("title_conf", 0.0), tick_direction=d.get("tick_direction", "out"),
                   label_color=tuple(d["label_color"]) if d.get("label_color") else None,
                   calibration=AxisCalibration.from_dict(d.get("calibration")), warnings=d.get("warnings", []))


@dataclass
class Series:
    name: str
    color: tuple = (0, 0, 0)                    # RGB 0-255
    kind: str = "line"                          # line | markers | line+markers | bars | step | band
    axis: str = "y"                             # y | y2
    points: pd.DataFrame = field(default_factory=empty_points)
    errors: pd.DataFrame | None = None          # idx, x_minus, x_plus, y_minus, y_plus, kind
    band: pd.DataFrame | None = None            # x, y_low, y_high  (shaded region)
    confidence: float = 0.0
    legend_matched: bool = False
    warnings: list = field(default_factory=list)
    visible: bool = True
    extra: dict = field(default_factory=dict)

    @property
    def hex_color(self) -> str:
        return "#%02x%02x%02x" % tuple(int(c) for c in self.color)

    def sorted_points(self) -> pd.DataFrame:
        return self.points.sort_values("x").reset_index(drop=True)

    def n_by_status(self) -> dict:
        return self.points["status"].value_counts().to_dict() if len(self.points) else {}

    def to_dict(self):
        return dict(name=self.name, color=[int(c) for c in self.color], kind=self.kind, axis=self.axis,
                    points=to_jsonable(self.points),
                    errors=to_jsonable(self.errors) if self.errors is not None else None,
                    band=to_jsonable(self.band) if self.band is not None else None,
                    confidence=float(self.confidence), legend_matched=self.legend_matched,
                    warnings=list(self.warnings), visible=self.visible, extra=to_jsonable(self.extra))

    @classmethod
    def from_dict(cls, d):
        pts = pd.DataFrame(d.get("points") or [], columns=POINT_COLUMNS)
        for c in ("idx", "x", "y", "px", "py", "confidence"):
            pts[c] = pd.to_numeric(pts[c], errors="coerce")
        er = pd.DataFrame(d["errors"]) if d.get("errors") else None
        bd = pd.DataFrame(d["band"]) if d.get("band") else None
        return cls(name=d["name"], color=tuple(d.get("color", (0, 0, 0))), kind=d.get("kind", "line"),
                   axis=d.get("axis", "y"), points=pts, errors=er, band=bd,
                   confidence=d.get("confidence", 0.0), legend_matched=d.get("legend_matched", False),
                   warnings=d.get("warnings", []), visible=d.get("visible", True), extra=d.get("extra", {}))


@dataclass
class ChartResult:
    """Everything extracted from one chart / panel."""
    panel_index: int = 0
    box: dict = field(default_factory=dict)
    chart_type: str = "generic"
    type_confidence: float = 0.0
    type_scores: dict = field(default_factory=dict)
    title: str | None = None
    x_axis: AxisInfo | None = None
    y_axis: AxisInfo | None = None
    y2_axis: AxisInfo | None = None
    legend: list = field(default_factory=list)       # [{name, color, bbox, ocr_conf}]
    series: list = field(default_factory=list)       # list[Series]
    bars: pd.DataFrame | None = None
    pie: pd.DataFrame | None = None
    quality: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    analysis: dict = field(default_factory=dict)     # filled by analysis.mathematical_analysis
    log: list = field(default_factory=list)

    def series_by_name(self, name: str):
        return next((s for s in self.series if s.name == name), None)

    def to_dict(self):
        return dict(panel_index=self.panel_index, box=self.box, chart_type=self.chart_type,
                    type_confidence=self.type_confidence, type_scores=self.type_scores, title=self.title,
                    x_axis=self.x_axis.to_dict() if self.x_axis else None,
                    y_axis=self.y_axis.to_dict() if self.y_axis else None,
                    y2_axis=self.y2_axis.to_dict() if self.y2_axis else None,
                    legend=to_jsonable(self.legend), series=[s.to_dict() for s in self.series],
                    bars=to_jsonable(self.bars) if self.bars is not None else None,
                    pie=to_jsonable(self.pie) if self.pie is not None else None,
                    quality=to_jsonable(self.quality), warnings=list(self.warnings),
                    analysis=to_jsonable(self.analysis), log=list(self.log))

    @classmethod
    def from_dict(cls, d):
        return cls(panel_index=d.get("panel_index", 0), box=d.get("box", {}), chart_type=d.get("chart_type", "generic"),
                   type_confidence=d.get("type_confidence", 0.0), type_scores=d.get("type_scores", {}),
                   title=d.get("title"), x_axis=AxisInfo.from_dict(d.get("x_axis")),
                   y_axis=AxisInfo.from_dict(d.get("y_axis")), y2_axis=AxisInfo.from_dict(d.get("y2_axis")),
                   legend=d.get("legend", []), series=[Series.from_dict(s) for s in d.get("series", [])],
                   bars=pd.DataFrame(d["bars"]) if d.get("bars") else None,
                   pie=pd.DataFrame(d["pie"]) if d.get("pie") else None,
                   quality=d.get("quality", {}), warnings=d.get("warnings", []),
                   analysis=d.get("analysis", {}), log=d.get("log", []))


@dataclass
class ProjectState:
    """Complete, re-loadable state of one analysis project."""
    project_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "New project"
    created: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    updated: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    image_meta: dict = field(default_factory=dict)
    settings: dict = field(default_factory=dict)
    preprocess: dict = field(default_factory=dict)
    charts: list = field(default_factory=list)       # list[ChartResult]
    active_chart: int = 0
    manual_edits: list = field(default_factory=list)
    processing_log: list = field(default_factory=list)
    is_sample: bool = False

    @property
    def chart(self) -> ChartResult | None:
        if not self.charts:
            return None
        return self.charts[min(self.active_chart, len(self.charts) - 1)]

    def log(self, msg: str):
        self.processing_log.append(f"{datetime.now().strftime('%H:%M:%S')} | {msg}")

    def touch(self):
        self.updated = datetime.now().isoformat(timespec="seconds")

    def to_dict(self):
        return dict(format="graphinsight-project", version=1, project_id=self.project_id, name=self.name,
                    created=self.created, updated=self.updated, image_meta=to_jsonable(self.image_meta),
                    settings=to_jsonable(self.settings), preprocess=to_jsonable(self.preprocess),
                    charts=[c.to_dict() for c in self.charts], active_chart=self.active_chart,
                    manual_edits=to_jsonable(self.manual_edits), processing_log=list(self.processing_log),
                    is_sample=self.is_sample)

    @classmethod
    def from_dict(cls, d):
        return cls(project_id=d.get("project_id", uuid.uuid4().hex[:12]), name=d.get("name", "Project"),
                   created=d.get("created", ""), updated=d.get("updated", ""), image_meta=d.get("image_meta", {}),
                   settings=d.get("settings", {}), preprocess=d.get("preprocess", {}),
                   charts=[ChartResult.from_dict(c) for c in d.get("charts", [])],
                   active_chart=d.get("active_chart", 0), manual_edits=d.get("manual_edits", []),
                   processing_log=d.get("processing_log", []), is_sample=d.get("is_sample", False))

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(to_jsonable(self.to_dict()), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str):
        return cls.from_dict(json.loads(text))
