"""End-to-end Chart Digitization pipeline: image -> ProjectState (axes, series, points, quality)."""
from __future__ import annotations

import gc
from dataclasses import dataclass
from typing import Callable

import cv2
import numpy as np
import pandas as pd

from config import constants as C
from config.logging_config import get_logger
from config.settings import ExtractionSettings
from models.chart_types import chart_strategy, chart_support
from models.data_models import AxisInfo, AxisTick, ChartResult, ProjectState, Series
from . import bar_extractor as BE
from . import chart_detector as CD
from . import confidence_estimator as CE
from . import curve_digitizer as DG
from .axis_detector import _label_regions_x, _ticks_along, detect_axis, read_chart_title
from .coordinate_transform import PlotTransform, calibration_from_box, fit_calibration
from .curve_detector import (find_color_clusters, looks_like_markers, split_curve_and_small)
from .error_bar_detector import detect_band, detect_error_bars, errors_frame
from .image_loader import LoadedImage
from .image_preprocessor import preprocess
from .legend_detector import detect_legend
from .marker_detector import detect_markers
from .ocr_engine import get_backend, ocr_status, read_text
from .plot_area_detector import PlotBox, detect_panels

log = get_logger("pipeline")


class AnalysisCancelled(Exception):
    """Raised when the user cancels a running analysis."""


@dataclass
class AnalysisOutput:
    state: ProjectState
    original: np.ndarray
    processed: np.ndarray


def _tick(progress, frac, msg, cancel):
    if cancel is not None and cancel():
        raise AnalysisCancelled()
    if progress:
        progress(float(frac), msg)


# ------------------------------------------------------------------ helpers
def _apply_manual_axis(info: AxisInfo, axis: str, box: PlotBox, mp: dict, scale: str) -> None:
    ticks = mp.get(f"{axis}_ticks")
    edges = mp.get(f"{axis}_edges")
    cats = mp.get(f"{axis}_categories")
    if scale == "categorical" and cats and len(info.ticks) >= 2:
        from .axis_calibration import calibrate_manual
        pix = [t.pixel for t in info.ticks][: len(cats)]
        cal = calibrate_manual([(p, 0) for p in pix], "categorical", list(cats)[: len(pix)])
        if cal:
            info.calibration = cal
            info.warnings.append("Categorical axis: categories were assigned to the detected ticks from left to right.")
        ticks = None
    if ticks and len(ticks) >= 2:
        from .axis_calibration import calibrate_manual
        cal = calibrate_manual([(t[0], t[1]) for t in ticks], scale if scale in ("datetime", "piecewise", "log10", "log2", "ln", "linear") else "linear")
        if cal is None:
            cal = fit_calibration([t[0] for t in ticks], [t[1] for t in ticks], scale=scale, source="manual")
        if cal:
            info.calibration = cal
            info.ticks = [AxisTick(float(p), str(v), (float(v) if not isinstance(v, str) else None), 1.0, "manual") for p, v in ticks]
            info.warnings = [w for w in info.warnings if "manual" not in w.lower()]
            info.warnings.append("Axis calibrated from tick values entered manually.")
    elif edges and len(edges) == 2:
        if axis == "x":
            cal = calibration_from_box(box.x0, box.x1, edges[0], edges[1], scale if scale != "auto" else "linear")
        else:
            cal = calibration_from_box(box.y1, box.y0, edges[0], edges[1], scale if scale != "auto" else "linear")
        if cal:
            cal.source = "manual"
            info.calibration = cal
            info.warnings.append("Axis calibrated from the plot-area edges (values entered manually).")
    if info.title is None and mp.get(f"{axis}_title"):
        info.raw_title = mp[f"{axis}_title"]
        info.title = mp[f"{axis}_title"]
    if mp.get(f"{axis}_unit"):
        info.unit = mp[f"{axis}_unit"]


def _is_area_like(mask: np.ndarray) -> bool:
    H, W = mask.shape
    cols = np.flatnonzero(mask.any(axis=0))
    if len(cols) < 0.2 * W:
        return False
    bottom_touch = mask[min(H - 3, H - 1):, :].any(axis=0)[cols].mean()
    heights = mask[:, cols].sum(axis=0)
    return bool(bottom_touch > 0.6 and np.mean(heights) > 0.09 * H)


def _top_edge(mask: np.ndarray) -> np.ndarray:
    out = np.zeros_like(mask, np.uint8)
    for x in np.flatnonzero(mask.any(axis=0)):
        r0 = int(np.argmax(mask[:, x] > 0))
        out[r0:r0 + 2, x] = 1
    return out


def _dark_mask(lab: np.ndarray) -> np.ndarray:
    return ((lab[..., 0] < 45) & (np.hypot(lab[..., 1], lab[..., 2]) < 22)).astype(np.uint8)


def _series_axis(color, y_info: AxisInfo | None, y2_info: AxisInfo | None) -> str:
    if y2_info is None or y2_info.calibration is None:
        return "y"
    def d(info):
        return np.linalg.norm(np.array(color, float) - np.array(info.label_color, float)) if info and info.label_color else 1e9
    return "y2" if d(y2_info) < d(y_info) and d(y2_info) < 90 else "y"


# ---------------------------------------------------------- series extraction
def _extract_curves(clusters, crop, tf: PlotTransform, settings: ExtractionSettings, x_info, y_info, y2_info,
                    chart_log: list, strategy: str) -> tuple[list[Series], dict]:
    feats = dict(has_errors=False, n_marker_series=0, n_line_series=0, step=False, area=False, parametric=False)
    cands = []
    dark = _dark_mask(crop.lab)
    for cl in clusters:
        mask = cl.mask.astype(np.uint8)
        curve_m, small_m = split_curve_and_small(mask, crop.w, crop.h)
        area_like = _is_area_like(mask) and not cl.neutral
        if area_like:
            total = _top_edge(mask)
        elif cl.neutral:
            total = curve_m | (small_m if looks_like_markers(small_m) else 0)
        else:
            total = curve_m | small_m
        total = total.astype(np.uint8)
        if int(total.sum()) < max(settings.min_series_pixels * 0.6, 25):
            chart_log.append(f"cluster {cl.hex}: ignored (text / noise, {int(total.sum())} px)")
            continue
        cands.append(dict(cl=cl, total=total, area=area_like))
    if not cands:
        return [], feats
    cal_conf = float(np.mean([c.confidence for c in (tf.x, tf.y) if c is not None])) if (tf.x or tf.y) else 0.2
    all_series: list[Series] = []
    for k, c in enumerate(cands):
        cl, total = c["cl"], c["total"]
        warnings: list[str] = []
        mk = detect_markers(total, crop.w, crop.h) if not c["area"] else dict(markers=[], line_radius=0, marker_only=False)
        markers = mk["markers"]
        errors_df = None
        if settings.detect_error_bars and len(markers) >= 3:
            res = detect_error_bars(markers, [total, dark], line_present=not mk["marker_only"])
            if res:
                total = (total & (1 - res["erase"])).astype(np.uint8)
                errors_df = res
                feats["has_errors"] = True
                chart_log.append(f"{cl.hex}: error bars detected on {sum(v is not None for v in res['vertical'])} markers")
        disc = np.zeros_like(total)
        for cx, cy, r in markers:
            cv2.circle(disc, (int(round(cx)), int(round(cy))), int(np.ceil(r)) + 2, 1, -1)
        line_only = (total & (1 - disc)).astype(np.uint8)
        occupied = int(line_only.any(axis=0).sum())
        line_present = occupied >= 0.12 * crop.w or (occupied >= 0.06 * crop.w and not markers)
        other = [o["total"] for j, o in enumerate(cands) if j != k]

        path = None
        if line_present:
            mode = settings.curve_mode
            if mode == "parametric" or strategy == "parametric":
                path = DG.trace_parametric(total, cl.dist, settings.color_tolerance)
                feats["parametric"] = True
            else:
                path = DG.trace_function(total, cl.dist, settings.color_tolerance, settings.max_gap_px)
            if path is None:
                line_present = False
        pieces, kind, steppy = [], "markers", False
        amb = DG.ambiguity_map(other, path.thickness if path else (mk["line_radius"] * 2 or 3), total.shape)
        axis = _series_axis(cl.rgb, y_info, y2_info)
        marker_df = None
        if markers:
            mxy = np.array([[m[0], m[1]] for m in markers])
            marker_df = DG.make_points(mxy[:, 0], mxy[:, 1], [C.ST_MARKER] * len(markers), tf, axis, (crop.ox, crop.oy),
                                       "marker blob centroid", np.ones(len(markers)), DG.amb_at(amb, mxy[:, 0], mxy[:, 1]),
                                       np.ones(len(markers)), cal_conf)
            pieces.append(marker_df)
        if path is not None:
            kind = "line+markers" if markers else "line"
            if strategy == "step" or settings.curve_mode == "step":
                steppy = True
            else:
                dy = np.abs(np.diff(path.ys))
                if len(dy) > 20 and (dy < 0.6).mean() > 0.85 and (dy > 3 * path.thickness).sum() >= 2:
                    steppy = True
            if steppy:
                pts = DG.step_corners(path)
                kind = "step"
                feats["step"] = True
                if pts:
                    arr = np.array(pts)
                    pieces.append(DG.make_points(arr[:, 0], arr[:, 1], [C.ST_RECON] * len(arr), tf, axis, (crop.ox, crop.oy),
                                                 "step plateau end points", np.ones(len(arr)), DG.amb_at(amb, arr[:, 0], arr[:, 1]),
                                                 np.ones(len(arr)), cal_conf))
            elif settings.dense_mode or not markers:
                pos, flags, pur, steep = DG.sample_path(path, settings.n_points, settings.sampling, settings.curvature_weight)
                if len(pos):
                    st = np.where(flags, C.ST_INTERP, C.ST_RECON)
                    pieces.append(DG.make_points(pos[:, 0], pos[:, 1], st, tf, axis, (crop.ox, crop.oy),
                                                 f"centre-line, {settings.sampling} sampling", pur,
                                                 DG.amb_at(amb, pos[:, 0], pos[:, 1]), np.where(steep, 0.85, 1.0), cal_conf))
            if c["area"]:
                feats["area"] = True
                warnings.append("Area chart: the upper boundary of the filled region was digitised.")
        if not pieces:
            continue
        pts = pd.concat(pieces, ignore_index=True).sort_values(["px", "status"]).reset_index(drop=True)
        pts["idx"] = np.arange(len(pts), dtype=float)
        cov = path.coverage if path is not None else 1.0
        sr = Series(name=(cl.legend or {}).get("name") or f"Series {len(all_series) + 1}", color=cl.rgb, kind=kind, axis=axis,
                    points=pts, legend_matched=bool(cl.legend and cl.legend.get("name")), warnings=warnings,
                    confidence=CE.series_confidence(pts["confidence"].to_numpy(), cov),
                    extra=dict(coverage=cov, line_thickness_px=(path.thickness if path else None),
                               n_markers=len(markers), area=c["area"], cluster_hex=cl.hex,
                               min_ambiguity=float(amb[total > 0].min()) if (total > 0).any() else 1.0))
        if path is not None and path.coverage < 0.8:
            sr.warnings.append(f"Curve visible over only {path.coverage:.0%} of its x-extent (gaps / occlusion).")
        if errors_df is not None and marker_df is not None:
            midx = pts.index[pts["status"] == C.ST_MARKER].to_numpy()
            ydata = lambda py: tf.y_for(axis).pixel_to_value(py + crop.oy) if tf.y_for(axis) is not None else np.nan  # noqa: E731
            ef = errors_frame(errors_df, markers, 0, ydata)
            ef["idx"] = midx[: len(ef)].astype(float)
            sr.errors = ef
        if settings.detect_bands and not cl.neutral and path is not None and not markers and not c["area"]:
            band = detect_band(crop.lab, cl, line_only)
            if band is not None and tf.ready:
                ya = tf.y_for(axis).pixel_to_value(band.py_top.to_numpy() + crop.oy)
                yb = tf.y_for(axis).pixel_to_value(band.py_bottom.to_numpy() + crop.oy)
                xb = tf.x.pixel_to_value(band.px.to_numpy() + crop.ox)
                step = max(1, len(xb) // 300)
                sr.band = pd.DataFrame(dict(x=xb[::step], y_low=np.minimum(ya, yb)[::step], y_high=np.maximum(ya, yb)[::step]))
                sr.warnings.append("A shaded region (confidence band / uncertainty) around the curve was detected; "
                                   "its statistical meaning (SD, SE, CI) is unspecified.")
        if kind in ("markers", "line+markers"):
            feats["n_marker_series"] += int(kind == "markers")
        feats["n_line_series"] += int(kind in ("line", "line+markers", "step"))
        all_series.append(sr)
    return all_series, feats


def _vector_series(paths, box: PlotBox, tf: PlotTransform, legend_entries, scale: float, y_info, y2_info,
                   cal_conf: float) -> list[Series]:
    out: list[Series] = []
    for vp in paths:
        pts = vp.points * scale
        if pts[:, 0].min() < box.x0 - 3 or pts[:, 0].max() > box.x1 + 3 or pts[:, 1].min() < box.y0 - 3 or pts[:, 1].max() > box.y1 + 3:
            continue
        if np.ptp(pts[:, 0]) < 0.2 * box.w:
            continue
        col = tuple(int(c) for c in vp.color)
        name = None
        for e in legend_entries:
            if e.get("name") and np.linalg.norm(np.array(e["color"], float) - np.array(col, float)) < 40:
                name = e["name"]
        axis = _series_axis(col, y_info, y2_info)
        xd, yd = tf.to_data(pts[:, 0], pts[:, 1], axis)
        df = pd.DataFrame(dict(idx=np.arange(len(pts), dtype=float), x=xd, y=yd, px=pts[:, 0], py=pts[:, 1],
                               status=C.ST_VECTOR, confidence=CE.point_confidence([C.ST_VECTOR] * len(pts), 1, 1, 1, cal_conf),
                               method="vector path vertex"))
        out.append(Series(name=name or f"Series {len(out) + 1}", color=col, kind="line", axis=axis, points=df,
                          legend_matched=name is not None, confidence=float(df["confidence"].mean()),
                          extra=dict(coverage=1.0, source="vector PDF path")))
    return out


# --------------------------------------------------------------------- panel
def analyze_panel(pp, box: PlotBox, idx: int, settings: ExtractionSettings, manual_panel: dict, vector_paths=None,
                  vector_scale: float = 1.0, progress=None, cancel=None, p0=0.0, p1=1.0) -> ChartResult:
    rgb, gray = pp.processed, pp.gray
    backend = get_backend(settings.ocr_backend, settings.ocr_lang)
    res = ChartResult(panel_index=idx, box=box.to_dict())
    L = res.log
    for n in box.notes:
        res.warnings.append(n)
    if box.confidence < 0.3:
        res.warnings.append("Plot area could not be detected reliably: set it manually in 'Image Processing'.")
    span = p1 - p0
    _tick(progress, p0 + 0.05 * span, f"panel {idx + 1}: axes and tick labels", cancel)
    xs = manual_panel.get("x_scale") or settings.x_scale
    ys = manual_panel.get("y_scale") or settings.y_scale
    xa = detect_axis(gray, rgb, box, "x", backend, scale_hint=xs, lang=settings.ocr_lang)
    ya = detect_axis(gray, rgb, box, "y", backend, scale_hint=ys, lang=settings.ocr_lang)
    y2 = None
    if box.x1 + 25 < gray.shape[1]:
        cand = detect_axis(gray, rgb, box, "y", backend, scale_hint="auto", side="right", lang=settings.ocr_lang, read_title=True)
        if cand.calibration is not None and sum(t.value is not None for t in cand.ticks) >= 2:
            y2 = cand
    _apply_manual_axis(xa, "x", box, manual_panel, xs)
    _apply_manual_axis(ya, "y", box, manual_panel, ys)
    if y2 is not None or manual_panel.get("y2_ticks"):
        y2 = y2 or AxisInfo(orientation="y", side="right", line_pos=box.x1)
        _apply_manual_axis(y2, "y2", box, manual_panel, "auto")
    res.x_axis, res.y_axis, res.y2_axis = xa, ya, y2
    for a, nm in ((xa, "X"), (ya, "Y")):
        for w in a.warnings:
            res.warnings.append(f"{nm} axis: {w}")
        if a.calibration is not None:
            L.append(f"{nm} axis calibration: {a.calibration.scale}, rmse={a.calibration.rmse_px:.2f}px, "
                     f"conf={a.calibration.confidence:.2f}, {len(a.calibration.refs)} ticks used")
    title, tconf = read_chart_title(gray, box, backend, settings.ocr_lang)
    res.title = title
    tf = PlotTransform(xa.calibration, ya.calibration, y2.calibration if y2 else None)

    _tick(progress, p0 + 0.25 * span, f"panel {idx + 1}: colour clustering", cancel)
    clusters, crop = find_color_clusters(rgb, box, tol=settings.color_tolerance, min_pixels=settings.min_series_pixels,
                                         manual_colors=settings.manual_series_colors or None, remove_grid=settings.remove_grid)
    L.append(f"{len(clusters)} colour cluster(s): {[c.hex for c in clusters]}")
    _tick(progress, p0 + 0.4 * span, f"panel {idx + 1}: legend", cancel)
    legend = detect_legend(rgb, gray, box, crop, clusters, backend, settings.ocr_lang, settings.color_tolerance)
    res.legend = sorted([dict(name=e["name"], color=list(e["color"]), bbox=list(e["bbox_image"]), conf=e["conf"], where=e["where"])
                         for e in legend], key=lambda e: (round(e["bbox"][1] / 12.0), e["bbox"][0]))

    # ---------------- bars
    forced = settings.chart_type if settings.chart_type != "auto" else None
    strategy = chart_strategy(forced) if forced else "curve"
    bars_pc = {}
    if (strategy == "bars" or not forced):
        for ci, cl in enumerate(clusters):
            if cl.neutral and cl.pixels < 200:
                continue
            bl = BE.find_bars(cl)
            if len(bl) >= 2:
                bars_pc[ci] = bl
    n_bars = sum(len(v) for v in bars_pc.values())
    bar_kind = bar_orient = None
    if n_bars >= 3 and (strategy == "bars" or not forced):
        bar_kind, bar_orient = BE.classify_bars(bars_pc, crop.h, crop.w)
    feats: dict = dict(panels=1)
    series: list[Series] = []

    if bar_kind is not None and not (forced and strategy != "bars"):
        _tick(progress, p0 + 0.6 * span, f"panel {idx + 1}: bars", cancel)
        names = {ci: ((clusters[ci].legend or {}).get("name") or f"Series {j + 1}") for j, ci in enumerate(bars_pc)}
        labels = []
        if bar_orient == "vertical":
            dark = gray < 150
            th = max(1.0, box.axis_thickness)
            _, tl = _ticks_along(dark, box.y1, th, +1, int(box.x0) - 3, int(box.x1) + 3)
            regs, _ = _label_regions_x(dark, box, int(round(box.y1)) + int(np.ceil(th / 2)) + tl + 1, 90, 3)
            for x0, x1, y0, y1 in regs:
                txt, cf = read_text(gray[max(y0 - 2, 0): y1 + 3, max(x0 - 2, 0): x1 + 3], backend, 7, settings.ocr_lang)
                labels.append(((x0 + x1) / 2.0, txt))
        df = BE.bars_table(bars_pc, names, bar_orient, crop, tf, labels, box)
        res.bars = df
        for nm in df["series"].unique():
            sub = df[df.series == nm].reset_index(drop=True)
            cl = clusters[[ci for ci, n in names.items() if n == nm][0]]
            xval = np.asarray(sub[["x_low", "x_high"]].mean(axis=1), float) if sub["x_low"].notna().all() and bar_kind == "histogram" else np.arange(1, len(sub) + 1, dtype=float)
            pts = pd.DataFrame(dict(idx=np.arange(len(sub), dtype=float), x=xval, y=sub["value"].to_numpy(float),
                                    px=sub["x_center_px"].to_numpy(float), py=sub["px_top"].to_numpy(float),
                                    status=C.ST_MARKER, confidence=0.9 * (0.5 + 0.5 * (tf.y.confidence if tf.y else 0.3)),
                                    method="bar edge (top)"))
            series.append(Series(name=nm, color=cl.rgb, kind="bars", points=pts, confidence=float(pts.confidence.mean()),
                                 extra=dict(orientation=bar_orient, categories=sub.get("category", pd.Series(dtype=object)).tolist())))
        feats["bars"] = dict(n=n_bars, kind=bar_kind)
        L.append(f"bar chart: {n_bars} bars ({bar_kind}, {bar_orient})")
    else:
        _tick(progress, p0 + 0.55 * span, f"panel {idx + 1}: curves and markers", cancel)
        series, f2 = _extract_curves(clusters, crop, tf, settings, xa, ya, y2, L, strategy)
        feats.update(f2)
        if vector_paths and settings.use_vector_pdf and tf.ready:
            vs = _vector_series(vector_paths, box, tf, res.legend, vector_scale, ya, y2,
                                float(np.mean([tf.x.confidence, tf.y.confidence])))
            if vs:
                L.append(f"vector PDF paths used: {len(vs)} series with exact vertices")
                series = vs
    # present series in legend order (top -> bottom, left -> right) when a legend was read
    if res.legend and series:
        order = {e["name"]: (round(e["bbox"][1] / 12.0), e["bbox"][0]) for e in res.legend if e.get("name")}
        series.sort(key=lambda s: order.get(s.name, (10 ** 9, 0)))
    res.series = series
    feats["n_series"] = len(series)
    feats["dual_axis"] = y2 is not None and any(s.axis == "y2" for s in series)
    key, conf, scores = CD.classify(feats)
    if forced:
        key, conf = forced, 1.0
    else:
        refined, changed = CD.refine_by_labels(key, xa.title, ya.title)
        if changed:
            scores[refined] = 0.5
            key, conf = refined, 0.5
    res.chart_type, res.type_confidence, res.type_scores = key, conf, scores
    note = CD.support_note(key)
    if note:
        res.warnings.append(note)
    if not series:
        res.warnings.append("No data series could be detected automatically. Try another colour tolerance, set series "
                            "colours manually, or digitise points by hand.")
    bar_like = res.bars is not None and tf.y is not None
    if (tf.x is None or tf.y is None) and not bar_like:
        res.warnings.append("Axis calibration is missing: points are in pixel coordinates only (x/y = NaN) until you "
                            "enter the axis tick values in 'Image Processing'.")
    if xa.calibration is not None and xa.calibration.scale.startswith("log"):
        L.append("x axis is logarithmic")
    if ya.calibration is not None and ya.calibration.scale.startswith("log"):
        L.append("y axis is logarithmic")
    # quality
    ocr_scores = [t.conf for a in (xa, ya) for t in a.ticks if t.value is not None] + [e["conf"] for e in legend]
    ocr_scores += [a.title_conf for a in (xa, ya) if a.title]
    sep = 1.0 if len(series) <= 1 else float(np.mean([s.extra.get("min_ambiguity", 1.0) for s in series]))
    res.quality = CE.quality_assessment(rgb.shape[1], rgb.shape[0], pp.scale, pp.noise_sigma, xa.calibration, ya.calibration,
                                        ocr_scores, [s.confidence for s in series], [s.extra.get("coverage", 1.0) for s in series],
                                        sep, len(series))
    return res


# ----------------------------------------------------------------- top level
def analyze_image(loaded: LoadedImage, settings: ExtractionSettings | None = None, progress: Callable | None = None,
                  cancel: Callable[[], bool] | None = None, manual: dict | None = None, pdf_bytes: bytes | None = None,
                  pdf_page: int = 0, pdf_scale: float = 3.0, project_name: str | None = None) -> AnalysisOutput:
    settings = settings or ExtractionSettings()
    manual = manual or {}
    state = ProjectState(name=project_name or loaded.name, settings=settings.to_dict())
    state.image_meta = dict(name=loaded.name, format=loaded.fmt, width=loaded.width, height=loaded.height,
                            dpi=list(loaded.dpi) if loaded.dpi else None)
    state.log(f"Loaded {loaded.name} ({loaded.width}x{loaded.height}, {loaded.fmt})")
    ocr = ocr_status(settings.ocr_lang)
    if not ocr["available"] and settings.ocr_backend != "none":
        state.log("OCR engine not available - axis values must be entered manually.")
    _tick(progress, 0.03, "pre-processing", cancel)
    pp = preprocess(loaded.rgb, settings.denoise, settings.deskew, settings.enhance_contrast, settings.upscale_small,
                    manual_rotation=float(manual.get("rotation", 0.0)))
    state.preprocess = dict(steps=pp.steps, scale=pp.scale, rotation_deg=pp.rotation_deg, noise_sigma=pp.noise_sigma,
                            warnings=pp.warnings, processed_size=[pp.processed.shape[1], pp.processed.shape[0]])
    for s in pp.steps:
        state.log("preprocess: " + s)
    _tick(progress, 0.08, "detecting plot areas", cancel)
    panels = detect_panels(pp.gray, pp.processed) if settings.detect_panels else [max(detect_panels(pp.gray, pp.processed), key=lambda b: b.w * b.h)]
    mp_all = manual.get("panels", {})
    for i in range(len(panels)):
        if str(i) in mp_all and mp_all[str(i)].get("box"):
            b = mp_all[str(i)]["box"]
            panels[i] = PlotBox(*b, confidence=1.0, axis_thickness=panels[i].axis_thickness, method="manual")
    if not panels:
        panels = detect_panels(pp.gray, pp.processed)
    # pie / donut (no axes)
    if panels[0].method == "fallback-margins" and not manual.get("panels"):
        pie = CD.find_pie(pp.processed)
        if pie:
            res = ChartResult(box=dict(x0=pie["cx"] - pie["r"], y0=pie["cy"] - pie["r"], x1=pie["cx"] + pie["r"], y1=pie["cy"] + pie["r"]),
                              chart_type="donut" if pie["donut"] else "pie", type_confidence=0.9)
            res.pie = BE.extract_pie(pp.processed, pie)
            for _, r in res.pie.iterrows():
                pts = pd.DataFrame(dict(idx=[0.0], x=[float(_ + 1)], y=[r.percent], px=[pie["cx"]], py=[pie["cy"]],
                                        status=C.ST_MARKER, confidence=0.85, method="sector angle"))
                res.series.append(Series(name=r.sector, color=tuple(r.color), kind="pie", points=pts, confidence=0.85))
            res.quality = dict(overall=0.8, grade="good", parts={}, n_series=len(res.series))
            res.log.append("pie chart: sector fractions measured from the angular colour profile")
            state.charts.append(res)
            state.log(f"Detected {res.chart_type} chart with {len(res.pie)} sectors")
            return AnalysisOutput(state, loaded.rgb, pp.processed)
    vector_paths = None
    if pdf_bytes and settings.use_vector_pdf and abs(pp.rotation_deg) < 0.05:
        try:
            from .pdf_processor import extract_vector_paths
            vector_paths = extract_vector_paths(pdf_bytes, pdf_page, pdf_scale)
        except Exception as exc:  # noqa: BLE001
            state.log(f"vector path extraction skipped: {exc}")
    major = max(panels, key=lambda b: b.w * b.h)
    panels = [b for b in panels if b.w * b.h >= 0.12 * major.w * major.h] or [major]
    state.log(f"{len(panels)} plot area(s) detected")
    for i, box in enumerate(panels):
        a, b = 0.1 + 0.85 * i / len(panels), 0.1 + 0.85 * (i + 1) / len(panels)
        res = analyze_panel(pp, box, i, settings, mp_all.get(str(i), {}), vector_paths, pp.scale, progress, cancel, a, b)
        if len(panels) > 1:
            res.chart_type = "multi_panel" if res.chart_type == "generic" else res.chart_type
        state.charts.append(res)
        state.log(f"panel {i + 1}: {res.chart_type}, {len(res.series)} series, "
                  f"{sum(len(s.points) for s in res.series)} points, quality {res.quality.get('overall')}")
    _tick(progress, 1.0, "done", cancel)
    gc.collect()
    return AnalysisOutput(state, loaded.rgb, pp.processed)


# ------------------------------------------------------------ re-digitisation
def _transform_of(chart: ChartResult) -> PlotTransform:
    return PlotTransform(chart.x_axis.calibration if chart.x_axis else None, chart.y_axis.calibration if chart.y_axis else None,
                         chart.y2_axis.calibration if chart.y2_axis else None)


def redigitize_chart(state: ProjectState, rgb: np.ndarray, chart_idx: int, settings: ExtractionSettings,
                     manual_colors: list | None = None) -> ChartResult:
    """Re-run colour clustering / legend / tracing for an existing chart, keeping its axes and calibration
    (used after changing sampling options, colours or noise settings in the dashboard)."""
    chart = state.charts[chart_idx]
    box = PlotBox.from_dict(chart.box)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    backend = get_backend(settings.ocr_backend, settings.ocr_lang)
    tf = _transform_of(chart)
    clusters, crop = find_color_clusters(rgb, box, tol=settings.color_tolerance, min_pixels=settings.min_series_pixels,
                                         manual_colors=manual_colors or settings.manual_series_colors or None,
                                         remove_grid=settings.remove_grid)
    legend = detect_legend(rgb, gray, box, crop, clusters, backend, settings.ocr_lang, settings.color_tolerance)
    old_names = {tuple(s.color): s.name for s in chart.series}
    series, feats = _extract_curves(clusters, crop, tf, settings, chart.x_axis, chart.y_axis, chart.y2_axis, chart.log, "curve")
    for s in series:      # keep user-given names of series whose colour is (almost) unchanged
        for col, nm in old_names.items():
            if np.linalg.norm(np.array(col, float) - np.array(s.color, float)) < 30 and not s.legend_matched:
                s.name = nm
    chart.series = series
    chart.legend = [dict(name=e["name"], color=list(e["color"]), bbox=list(e["bbox_image"]), conf=e["conf"], where=e["where"]) for e in legend]
    state.settings = settings.to_dict()
    state.log(f"re-digitised panel {chart_idx + 1}: {len(series)} series ({settings.sampling}, n={settings.n_points})")
    return chart


def reextract_series_by_color(state: ProjectState, rgb: np.ndarray, chart_idx: int, series_name: str, color: tuple,
                              settings: ExtractionSettings) -> bool:
    """Extract one series again using a user-chosen colour (for ambiguous / same-colour curves)."""
    chart = state.charts[chart_idx]
    box = PlotBox.from_dict(chart.box)
    tf = _transform_of(chart)
    clusters, crop = find_color_clusters(rgb, box, tol=settings.color_tolerance, min_pixels=max(20, settings.min_series_pixels // 3),
                                         manual_colors=[list(color)], remove_grid=False)
    series, _ = _extract_curves(clusters, crop, tf, settings, chart.x_axis, chart.y_axis, chart.y2_axis, chart.log, "curve")
    if not series:
        return False
    new = series[0]
    new.name = series_name
    for i, s in enumerate(chart.series):
        if s.name == series_name:
            chart.series[i] = new
            state.log(f"series '{series_name}' re-extracted from colour {tuple(color)}")
            return True
    chart.series.append(new)
    return True
