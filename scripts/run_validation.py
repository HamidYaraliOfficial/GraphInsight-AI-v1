"""Validate the extraction engine against the synthetic charts that have known ground truth.

Metrics: MAE, RMSE (data units and % of the axis range), coordinate error (normalised distance to the true polyline),
axis-calibration error, point-detection precision / recall (markers), extraction coverage, series recall.

Usage:  python scripts/run_validation.py [sample_dir] [output_dir]
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import constants as C  # noqa: E402
from config.settings import ExtractionSettings  # noqa: E402
from core.image_loader import load_image  # noqa: E402
from core.pipeline import analyze_image  # noqa: E402

# samples that are analysed a second time with manual axis information (what a user would do)
MANUAL_RUNS = {"09_low_quality": {"panels": {"0": {"x_edges": [0, 10], "y_edges": [0, 10]}}}}


def _norm_polyline(gx, gy, xr, yr, n=3000):
    xs = np.linspace(min(gx), max(gx), n)
    ys = np.interp(xs, gx, gy)
    return np.c_[(xs - xr[0]) / (xr[1] - xr[0]), (ys - yr[0]) / (yr[1] - yr[0])]


def _match(gt_series, chart):
    """Greedy colour matching of ground-truth series to extracted series of the same panel."""
    pairs, used = [], set()
    for g in gt_series:
        best, bd = None, 1e9
        for i, s in enumerate(chart.series):
            if i in used:
                continue
            d = float(np.linalg.norm(np.array(g["color"], float) - np.array(s.color, float)))
            if s.name == g["name"]:
                d -= 60
            if d < bd:
                best, bd = i, d
        if best is not None and bd < 110:
            used.add(best)
            pairs.append((g, chart.series[best]))
        else:
            pairs.append((g, None))
    return pairs, len(chart.series) - len(used)


def validate_one(path: Path, manual: dict | None = None, label: str | None = None) -> dict:
    gt = json.loads(path.with_suffix(".json").read_text(encoding="utf-8")) if path.with_suffix(".json").exists() else json.loads(
        (path.parent / (path.stem + ".json")).read_text(encoding="utf-8"))
    t0 = time.time()
    out = analyze_image(load_image(path), ExtractionSettings(), manual=manual or {})
    secs = time.time() - t0
    st = out.state
    res = dict(sample=label or path.stem, file=path.name, seconds=round(secs, 2), detected_type=st.charts[0].chart_type if st.charts else None,
               n_panels=len(st.charts), expected_panels=len(gt["panels"]) or 1, series_found=0, series_expected=len(gt["series"]),
               false_series=0, mae=None, rmse=None, mae_pct=None, rmse_pct=None, coord_error_pct=None, cal_error_pct=None,
               point_precision=None, point_recall=None, coverage=None, marker_precision=None, marker_recall=None, notes=[], manual=bool(manual))
    if "bars" in gt:
        ch = st.charts[0]
        if ch.bars is not None and len(ch.bars) == len(gt["bars"]["values"]):
            err = np.abs(ch.bars["value"].to_numpy(float) - np.array(gt["bars"]["values"]))
            rng = max(gt["bars"]["values"])
            res.update(series_found=1, mae=float(err.mean()), rmse=float(np.sqrt((err ** 2).mean())), mae_pct=float(err.mean() / rng * 100),
                       rmse_pct=float(np.sqrt((err ** 2).mean()) / rng * 100), coverage=1.0, point_precision=1.0, point_recall=1.0)
            res["notes"].append("bar values compared with ground truth; categories: " + ",".join(map(str, ch.bars.get("category", []))))
        else:
            res["notes"].append("bars not detected correctly")
        return res
    if "pie" in gt:
        ch = st.charts[0]
        if ch.pie is not None and len(ch.pie) == len(gt["pie"]["fractions"]):
            err = np.abs(ch.pie["fraction"].to_numpy(float) - np.array(gt["pie"]["fractions"])) * 100
            res.update(series_found=len(ch.pie), mae=float(err.mean()), rmse=float(np.sqrt((err ** 2).mean())), mae_pct=float(err.mean()),
                       rmse_pct=float(np.sqrt((err ** 2).mean())), coverage=1.0, point_precision=1.0, point_recall=1.0)
            res["notes"].append("pie: errors are in percentage points")
        else:
            res["notes"].append("pie sectors not detected correctly")
        return res
    maes, rmses, mpct, rpct, coords, precs, covs = [], [], [], [], [], [], []
    mprec, mrec, cal_errs = [], [], []
    found = 0
    false_series = 0
    for pi, chart in enumerate(st.charts):
        gts = [g for g in gt["series"] if g["panel"] == chart.panel_index]
        pairs, extra = _match(gts, chart)
        false_series += extra
        pinfo = next((p for p in gt["panels"] if p["panel"] == chart.panel_index), None)
        # axis calibration error from the plot-area corners (only when no rotation / manual box was applied)
        if pinfo and abs(st.preprocess.get("rotation_deg", 0)) < 1e-6 and chart.x_axis and chart.y_axis and chart.x_axis.calibration and chart.y_axis.calibration and not manual:
            sc = st.preprocess.get("scale", 1.0)
            c = pinfo["corners"]
            xr = abs(pinfo["xlim"][1] - pinfo["xlim"][0])
            yr = abs(pinfo["ylim"][1] - pinfo["ylim"][0])
            for key in ("bl", "br", "tl"):
                px, py = c[key]["px"] * sc, c[key]["py"] * sc
                xv = float(chart.x_axis.calibration.pixel_to_value(px))
                yv = float(chart.y_axis.calibration.pixel_to_value(py))
                if pinfo["xscale"] == "log10":
                    cal_errs.append(abs(np.log10(xv) - np.log10(c[key]["x"])) / abs(np.log10(pinfo["xlim"][1]) - np.log10(pinfo["xlim"][0])) * 100)
                else:
                    cal_errs.append(abs(xv - c[key]["x"]) / xr * 100)
                if pinfo["yscale"] == "log10":
                    cal_errs.append(abs(np.log10(yv) - np.log10(c[key]["y"])) / abs(np.log10(pinfo["ylim"][1]) - np.log10(pinfo["ylim"][0])) * 100)
                else:
                    cal_errs.append(abs(yv - c[key]["y"]) / yr * 100)
        for g, s in pairs:
            if s is None:
                res["notes"].append(f"series '{g['name']}' not found")
                continue
            found += 1
            gx, gy = np.array(g["x"]), np.array(g["y"])
            pts = s.points[(s.points.status != C.ST_INTERP)].dropna(subset=["x", "y"])
            if pts.empty:
                continue
            logx = pinfo and pinfo["xscale"] == "log10"
            logy = pinfo and pinfo["yscale"] == "log10"
            tx = (lambda v: np.log10(v)) if logx else (lambda v: v)
            ty = (lambda v: np.log10(v)) if logy else (lambda v: v)
            xr = (float(tx(gx.min())), float(tx(gx.max())))
            yr = (float(ty(gy.min())), float(ty(gy.max())))
            if xr[1] == xr[0] or yr[1] == yr[0]:
                continue
            ok = (pts.x >= gx.min()) & (pts.x <= gx.max())
            p = pts[ok]
            if p.empty:
                continue
            ypred = np.interp(p.x, gx, gy)
            err = np.abs(p.y.to_numpy() - ypred)
            span = float(np.ptp(gy))
            maes.append(err.mean()); rmses.append(np.sqrt((err ** 2).mean()))
            mpct.append(err.mean() / span * 100); rpct.append(np.sqrt((err ** 2).mean()) / span * 100)
            poly = _norm_polyline(tx(gx), ty(gy), xr, yr)
            tree = cKDTree(poly)
            q = np.c_[(tx(p.x.to_numpy()) - xr[0]) / (xr[1] - xr[0]), (ty(p.y.to_numpy()) - yr[0]) / (yr[1] - yr[0])]
            d, _ = tree.query(q)
            coords.append(d.mean() * 100)
            precs.append(float((d <= 0.01).mean()))
            xs_ok = np.sort(q[d <= 0.02, 0])
            if len(xs_ok) < 2:
                cov = 0.0
            else:
                gaps = np.diff(np.r_[0.0, xs_ok, 1.0])
                cov = float(max(0.0, 1.0 - gaps[gaps > 0.03].sum()))
            covs.append(cov)
            cov_idx = len(covs) - 1
            if "markers" in g and g["markers"]["x"]:
                mk = s.points[s.points.status == C.ST_MARKER].dropna(subset=["x", "y"])
                if len(mk):
                    gm = np.c_[(tx(np.array(g["markers"]["x"])) - xr[0]) / (xr[1] - xr[0]), (ty(np.array(g["markers"]["y"])) - yr[0]) / (yr[1] - yr[0])]
                    em = np.c_[(tx(mk.x.to_numpy()) - xr[0]) / (xr[1] - xr[0]), (ty(mk.y.to_numpy()) - yr[0]) / (yr[1] - yr[0])]
                    dd, _ = cKDTree(gm).query(em)
                    de, _ = cKDTree(em).query(gm)
                    mprec.append(float((dd <= 0.03).mean()))
                    mrec.append(float((de <= 0.03).mean()))
                    if s.kind == "markers":
                        covs[cov_idx] = mrec[-1]
                else:
                    mprec.append(0.0); mrec.append(0.0)
            if "errors" in g and s.errors is not None and len(s.errors):
                ge = np.array(g["errors"])
                e = s.errors.dropna(subset=["y_plus", "y_minus"])
                if len(e) == len(ge):
                    avg = (e.y_plus.to_numpy() + e.y_minus.to_numpy()) / 2
                    res["error_bar_mae"] = float(np.abs(avg - ge).mean())
                    res["error_bar_mae_pct_of_value"] = float((np.abs(avg - ge) / ge).mean() * 100)
            if "band" in g and s.band is not None and len(s.band):
                gb = g["band"]
                gh = np.interp(s.band.x, gb["x"], gb["high"]); gl = np.interp(s.band.x, gb["x"], gb["low"])
                res["band_mae"] = float((np.abs(s.band.y_high - gh).mean() + np.abs(s.band.y_low - gl).mean()) / 2)
                res["band_mae_pct"] = float(res["band_mae"] / np.ptp(gy) * 100)
    res.update(series_found=found, false_series=false_series)
    f = lambda a: (float(np.mean(a)) if a else None)  # noqa: E731
    res.update(mae=f(maes), rmse=f(rmses), mae_pct=f(mpct), rmse_pct=f(rpct), coord_error_pct=f(coords), cal_error_pct=f(cal_errs),
               point_precision=f(precs), coverage=f(covs), marker_precision=f(mprec), marker_recall=f(mrec))
    res["point_recall"] = f(mrec) if mrec else f(covs)
    res["quality_overall"] = st.charts[0].quality.get("overall") if st.charts else None
    res["warnings"] = [w for c in st.charts for w in c.warnings][:4]
    return res


def validate_all(sample_dir: Path, out_dir: Path) -> pd.DataFrame:
    rows = []
    for p in sorted(sample_dir.glob("*")):
        if p.suffix.lower() not in (".png", ".jpg") or not (sample_dir / (p.stem + ".json")).exists():
            continue
        try:
            rows.append(validate_one(p))
            if p.stem in MANUAL_RUNS:
                rows.append(validate_one(p, MANUAL_RUNS[p.stem], label=p.stem + " (manual axis edges)"))
        except Exception as exc:  # noqa: BLE001
            rows.append(dict(sample=p.stem, notes=[f"FAILED: {exc}"]))
    p = sample_dir / "17_vector_chart.pdf"
    if p.exists():
        try:
            from config.settings import ExtractionSettings as ES
            data = p.read_bytes()
            li = load_image(p)
            o = analyze_image(li, ES(), pdf_bytes=data)
            gt = json.loads((sample_dir / "17_vector_chart.json").read_text())
            ch = o.state.charts[0]
            errs = []
            for g in gt["series"]:
                s = min(ch.series, key=lambda s: np.linalg.norm(np.array(g["color"]) - np.array(s.color)))
                errs.append(np.abs(s.points.y.to_numpy() - np.interp(s.points.x, g["x"], g["y"])).mean() / np.ptp(g["y"]) * 100)
            rows.append(dict(sample="17_vector_chart (PDF vector paths)", series_found=len(ch.series), series_expected=len(gt["series"]),
                             mae_pct=float(np.mean(errs)), detected_type=ch.chart_type, notes=["exact vector vertices"]))
        except Exception as exc:  # noqa: BLE001
            rows.append(dict(sample="17_vector_chart", notes=[f"FAILED: {exc}"]))
    df = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "validation_results.json").write_text(json.dumps(rows, indent=1, default=str), encoding="utf-8")
    df.drop(columns=["notes", "warnings"], errors="ignore").to_csv(out_dir / "validation_results.csv", index=False)
    return df


def to_markdown(df: pd.DataFrame) -> str:
    cols = ["sample", "detected_type", "series_found", "series_expected", "mae_pct", "rmse_pct", "coord_error_pct", "cal_error_pct",
            "point_precision", "point_recall", "coverage", "error_bar_mae_pct_of_value", "band_mae_pct", "seconds"]
    cols = [c for c in cols if c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            cells.append("-" if (v is None or (isinstance(v, float) and np.isnan(v))) else (f"{v:.3f}" if isinstance(v, float) else str(v)))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


if __name__ == "__main__":
    sd = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sample_charts"
    od = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data" / "outputs" / "validation"
    df = validate_all(sd, od)
    md = to_markdown(df)
    (od / "validation_results.md").write_text(md, encoding="utf-8")
    print(md)
