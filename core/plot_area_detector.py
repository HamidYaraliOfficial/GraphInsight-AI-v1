"""Plot-area (axes box) detection from long horizontal / vertical lines; multi-panel support."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from config.logging_config import get_logger

log = get_logger("plotarea")


@dataclass
class Seg:
    a0: float      # start along the line
    a1: float      # end along the line
    pos: float     # perpendicular position (y for horizontal, x for vertical)
    thick: float

    @property
    def length(self) -> float:
        return self.a1 - self.a0


@dataclass
class PlotBox:
    x0: float
    y0: float
    x1: float
    y1: float                      # y1 is the bottom axis row, y0 the top
    confidence: float = 1.0
    axis_thickness: float = 1.0
    framed: bool = False
    method: str = "axes-lines"
    notes: list = field(default_factory=list)

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0

    def to_tuple(self):
        return (self.x0, self.y0, self.x1, self.y1)

    def to_dict(self) -> dict:
        return dict(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1, confidence=self.confidence,
                    axis_thickness=self.axis_thickness, framed=self.framed, method=self.method,
                    notes=list(self.notes))

    @classmethod
    def from_dict(cls, d: dict):
        return cls(**{k: d[k] for k in ("x0", "y0", "x1", "y1")},
                   confidence=d.get("confidence", 1.0), axis_thickness=d.get("axis_thickness", 1.0),
                   framed=d.get("framed", False), method=d.get("method", "manual"),
                   notes=d.get("notes", []))


def _segments(mask: np.ndarray, horizontal: bool, min_len: int, max_thick: int = 9) -> list[Seg]:
    k = (min_len, 1) if horizontal else (1, min_len)
    opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, k))
    n, _, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, _a = stats[i]
        if horizontal and h <= max_thick:
            out.append(Seg(x, x + w - 1, y + (h - 1) / 2.0, h))
        elif not horizontal and w <= max_thick:
            out.append(Seg(y, y + h - 1, x + (w - 1) / 2.0, w))
    return out


def detect_panels(gray: np.ndarray, rgb: np.ndarray | None = None, min_frac: float = 0.10) -> list[PlotBox]:
    """Detect every plot area (axes corner = vertical line meeting a horizontal line)."""
    H, W = gray.shape
    neutral = None
    if rgb is not None:                      # axes are neutral (black / gray): ignore coloured bars and curves
        neutral = (rgb.max(axis=2).astype(np.int16) - rgb.min(axis=2).astype(np.int16)) < 60
    for thr in (110, 150, 200, 235):
        mask = (gray < thr)
        if neutral is not None and thr <= 150:
            mask &= neutral
        mask = mask.astype(np.uint8) * 255
        min_len = max(40, int(min_frac * min(H, W)))
        hs = _segments(mask, True, min_len)
        vs = _segments(mask, False, min_len)
        if not hs or not vs:
            continue
        tol = max(8.0, 0.03 * min(H, W))
        boxes: list[PlotBox] = []
        for v in vs:
            for h in hs:
                # corner: the horizontal axis starts at the vertical axis and lies along its lower part
                # (tick marks may make either line stick out a little)
                if abs(h.a0 - v.pos) <= tol and v.a0 - 2 <= h.pos <= v.a1 + tol and h.pos > v.a0 + 0.3 * v.length:
                    box = PlotBox(v.pos, v.a0, h.a1, h.pos, axis_thickness=max(h.thick, v.thick),
                                  method=f"axes-lines(thr={thr})")
                    top = any(abs(t.pos - box.y0) <= tol and t.a0 <= box.x0 + tol and t.a1 >= box.x1 - tol for t in hs)
                    right = any(abs(r.pos - box.x1) <= tol and r.a0 <= box.y0 + tol and r.a1 >= box.y1 - tol for r in vs)
                    box.framed = bool(top and right)
                    if right:      # snap the right edge to the frame line (tick marks may extend the axis line)
                        r_seg = min((r for r in vs if abs(r.pos - box.x1) <= tol), key=lambda r: abs(r.pos - box.x1))
                        box.x1 = float(r_seg.pos)
                    box.confidence = 0.95 if thr <= 150 else 0.7
                    if thr > 150:
                        box.notes.append("axes found only with a relaxed darkness threshold (light axes / grid)")
                    boxes.append(box)
        # de-duplicate: keep larger of overlapping boxes with same corner
        boxes.sort(key=lambda b: -(b.w * b.h))
        keep: list[PlotBox] = []
        for b in boxes:
            dup = False
            for k in keep:
                ix = max(0, min(b.x1, k.x1) - max(b.x0, k.x0))
                iy = max(0, min(b.y1, k.y1) - max(b.y0, k.y0))
                if ix * iy > 0.5 * min(b.w * b.h, k.w * k.h):
                    dup = True
                    break
            if not dup and b.w > 0.08 * W and b.h > 0.08 * H:
                keep.append(b)
        if keep:
            keep.sort(key=lambda b: (round(b.y0 / (0.15 * H)), b.x0))
            log.info("Detected %d plot area(s) at threshold %d", len(keep), thr)
            return keep
    log.warning("No axes found; falling back to the image interior")
    mx, my = int(0.12 * W), int(0.10 * H)
    return [PlotBox(mx, my, W - int(0.05 * W), H - int(1.2 * my), confidence=0.15, method="fallback-margins",
                    notes=["axes lines not found: the plot area was guessed; please set it manually"])]


def detect_plot_area(gray: np.ndarray, rgb: np.ndarray | None = None) -> PlotBox:
    """Largest detected plot area."""
    return max(detect_panels(gray, rgb), key=lambda b: b.w * b.h)
