"""Excel export (XlsxWriter): multi-sheet workbook with real tables, formulas, filters, freeze panes and charts."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import xlsxwriter

from analysis import curve_fitting as CF
from analysis import data_cleaning as DC
from config import constants as C
from models.data_models import ChartResult, ProjectState

LIB = CF.library()


def _num(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return f if np.isfinite(f) else None


def _ax(ax, default: str) -> str:
    """Axis label for chart titles: unknown titles are shown as such, never invented."""
    return ax.display_name if ax is not None and ax.display_name and ax.display_name != "unknown" else default


def _sheet_name(prefix: str, base: str) -> str:
    return (prefix + base)[:31]


class _Fmt:
    def __init__(self, wb):
        base = dict(font_name="Arial", font_size=10)
        self.title = wb.add_format({**base, "bold": True, "font_size": 16, "font_color": "#1F3864"})
        self.sub = wb.add_format({**base, "italic": True, "font_color": "#666666"})
        self.h = wb.add_format({**base, "bold": True, "bg_color": "#1F3864", "font_color": "white", "border": 1, "text_wrap": True, "valign": "vcenter"})
        self.cell = wb.add_format({**base})
        self.wrap = wb.add_format({**base, "text_wrap": True, "valign": "top"})
        self.num = wb.add_format({**base, "num_format": "0.000000"})
        self.pct = wb.add_format({**base, "num_format": "0.0%"})
        self.bold = wb.add_format({**base, "bold": True})
        self.warn = wb.add_format({**base, "font_color": "#B00020", "bold": True})
        self.note = wb.add_format({**base, "italic": True, "font_color": "#555555", "text_wrap": True})
        self.wb = wb
        self._sw = {}

    def swatch(self, hex_color):
        if hex_color not in self._sw:
            self._sw[hex_color] = self.wb.add_format({"bg_color": hex_color, "border": 1})
        return self._sw[hex_color]


def _table(ws, f: _Fmt, r0: int, c0: int, df: pd.DataFrame, name: str | None = None, widths: dict | None = None,
           table: bool = True, numfmt: dict | None = None):
    """Write a DataFrame as an Excel table (or plain block) starting at (r0, c0). Returns last row index."""
    cols = list(df.columns)
    df = df.copy()
    for c in cols:
        if df[c].dtype == object:
            df[c] = df[c].map(lambda v: v if isinstance(v, str) or v is None else str(v) if not isinstance(v, (int, float, np.number)) else v)
    n = len(df)
    if table and n > 0:
        data = [[(None if (isinstance(v, float) and not np.isfinite(v)) else (v.item() if isinstance(v, np.generic) else v)) for v in row]
                for row in df.itertuples(index=False, name=None)]
        eq_cells = [(i, j, v) for i, row in enumerate(data) for j, v in enumerate(row) if isinstance(v, str) and v.startswith("=")]
        ws.add_table(r0, c0, r0 + n, c0 + len(cols) - 1, dict(
            data=data, name=name, columns=[dict(header=str(c), format=(f.num if (numfmt or {}).get(c) == "num" else f.cell)) for c in cols],
            style="Table Style Light 9", autofilter=True))
        for i, j, v in eq_cells:                      # text that merely looks like a formula (equation templates)
            ws.write_string(r0 + 1 + i, c0 + j, v, f.cell)
    else:
        for j, c in enumerate(cols):
            ws.write(r0, c0 + j, str(c), f.h)
        for i, row in enumerate(df.itertuples(index=False, name=None), start=1):
            for j, v in enumerate(row):
                v = v.item() if isinstance(v, np.generic) else v
                if isinstance(v, float) and not np.isfinite(v):
                    v = None
                if isinstance(v, str):
                    ws.write_string(r0 + i, c0 + j, v, f.cell)
                else:
                    ws.write(r0 + i, c0 + j, v, f.cell)
    for j, c in enumerate(cols):
        ws.set_column(c0 + j, c0 + j, (widths or {}).get(c, max(10, min(34, len(str(c)) + 3))))
    return r0 + n


def _kv(ws, f, r, rows):
    for k, v in rows:
        ws.write(r, 0, k, f.bold)
        ws.write(r, 1, "" if v is None else (v if isinstance(v, (int, float, str)) else str(v)), f.wrap)
        r += 1
    return r


def _eval_best(fit: dict, x: np.ndarray) -> np.ndarray:
    fam = fit["family"]
    if fam in LIB:
        vals = [fit["params"][p]["value"] for p in LIB[fam].params]
        return np.asarray(LIB[fam].func(x, *vals), float)
    return np.interp(x, fit["x_fit"], fit["y_fit"]) if fit.get("x_fit") else np.full_like(x, np.nan)


def _excel_template(fit: dict, refs: dict, xref: str) -> str | None:
    fam = fit["family"]
    if fam in LIB:
        t = LIB[fam].excel
        for p, ref in refs.items():
            t = t.replace("{%s}" % p, ref)
        return "=" + CF.excel_formula(t, xref)
    if fam.startswith("piecewise"):
        return CF.excel_formula(fit["equation"]["excel"], xref)
    return None


def _write_chart(wb, f, ws_map, chart: ChartResult, prefix: str, state: ProjectState):
    nm = lambda b: _sheet_name(prefix, b)  # noqa: E731
    an = chart.analysis or {}
    asr = an.get("series", {})
    # ----- Axis_Calibration
    ws = ws_map["Axis_Calibration"]
    row = ws.dim_rowmax + 2 if getattr(ws, "dim_rowmax", None) else 0
    ws.write(row, 0, f"Panel {chart.panel_index + 1}", f.title)
    row += 2
    rows, tick_rows = [], []
    for label, ax in (("X", chart.x_axis), ("Y", chart.y_axis), ("Y2", chart.y2_axis)):
        if ax is None:
            continue
        c = ax.calibration
        rows.append(dict(axis=label, title=ax.title or "unknown", unit=ax.unit or "unknown", scale=c.scale if c else "NOT CALIBRATED",
                         a_pixel_per_unit=_num(c.a) if c else None, b_offset_px=_num(c.b) if c else None,
                         rmse_px=_num(c.rmse_px) if c else None, confidence=_num(c.confidence) if c else None,
                         source=c.source if c else "", n_reference_ticks=len(c.refs) if c else 0,
                         rejected_ticks=len(c.outliers) if c else 0, note=(c.note if c else "; ".join(ax.warnings))))
        for t in ax.ticks:
            used = bool(c and any(abs(t.pixel - p) < 1e-6 for p, _ in c.refs))
            tick_rows.append(dict(axis=label, pixel=t.pixel, ocr_label=t.label, value=t.value, ocr_confidence=t.conf, source=t.source,
                                  used_in_calibration="yes" if used else "no"))
    last = _table(ws, f, row, 0, pd.DataFrame(rows), table=False)
    if tick_rows:
        ws.write(last + 2, 0, "Detected ticks and tick-label OCR", f.bold)
        _table(ws, f, last + 3, 0, pd.DataFrame(tick_rows), table=False)
    ws.write(last + 4 + len(tick_rows) + 1, 0, "Pixel coordinates refer to the pre-processed (scaled) image; x/y values use these calibrations.", f.note)
    # ----- Extracted_Data
    ws = ws_map["Extracted_Data"]
    frames = []
    for s in chart.series:
        d = s.sorted_points().copy()
        d.insert(0, "series", s.name)
        frames.append(d)
    if frames:
        allp = pd.concat(frames, ignore_index=True)
        allp = allp.rename(columns={"x": "X", "y": "Y", "px": "pixel_x", "py": "pixel_y", "status": "point_status"})
        r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
        _table(ws, f, r0, 0, allp, name=_sheet_name("", f"tblData_{prefix.strip('_') or 'P1'}"),
               numfmt={"X": "num", "Y": "num", "pixel_x": "num", "pixel_y": "num", "confidence": "num"})
        ws.freeze_panes(r0 + 1, 0)
    # ----- Series sheets
    pr = ws_map["Model_Parameters"]
    prow = (pr.dim_rowmax + 2) if getattr(pr, "dim_rowmax", None) else 0
    pr.write(prow, 0, f"Panel {chart.panel_index + 1} - best approximate model per series (parameters in column D are used by the Fit formulas of the Series sheets)", f.bold)
    prow += 1
    series_refs = {}
    pr_head = ["series", "model", "parameter", "value", "std_error", "ci95_low", "ci95_high", "note"]
    for j, h in enumerate(pr_head):
        pr.write(prow, j, h, f.h)
    prow += 1
    for s in chart.series:
        a = asr.get(s.name, {})
        fits = (a.get("fits") or {}).get("models") or []
        best = next((m for m in fits if m["name"] == (a.get("fits") or {}).get("best")), None)
        if not best:
            continue
        refs = {}
        for pn, pv in best["params"].items():
            pr.write(prow, 0, s.name, f.cell); pr.write(prow, 1, best["name"], f.cell); pr.write(prow, 2, pn, f.cell)
            pr.write(prow, 3, _num(pv["value"]), f.num); pr.write(prow, 4, _num(pv.get("stderr")), f.num)
            pr.write(prow, 5, _num(pv.get("ci_low")), f.num); pr.write(prow, 6, _num(pv.get("ci_high")), f.num)
            pr.write(prow, 7, "approximate model parameters" if pn == list(best["params"])[0] else "", f.note)
            refs[pn] = "'%s'!$D$%d" % (pr.get_name(), prow + 1)
            prow += 1
        series_refs[s.name] = (best, refs)
    for k, s in enumerate(chart.series, start=1):
        ws = wb.get_worksheet_by_name(nm(f"Series_{k}"))
        d = s.sorted_points().reset_index(drop=True)
        ws.write(0, 0, f"{s.name}", f.title)
        ws.write(1, 0, f"kind={s.kind}  axis={s.axis}  colour={s.hex_color}  series confidence={s.confidence:.2f}  (status: marker = real marker, reconstructed = from line centre-line, interpolated = gap filled)", f.sub)
        ws.write(1, 11, "", f.swatch(s.hex_color))
        hdr = ["idx", "X", "Y", "pixel_x", "pixel_y", "point_status", "confidence", "method", "dY/dX (formula)", "cumulative integral of Y dX (formula)",
               "fit_Y (formula)", "residual (formula)"]
        has_fit = s.name in series_refs
        r0, n = 3, len(d)
        for j, h in enumerate(hdr):
            ws.write(r0, j, h, f.h)
        xs, ys = d.x.to_numpy(float), d.y.to_numpy(float)
        cum = np.r_[0.0, np.cumsum(np.diff(xs) * (ys[1:] + ys[:-1]) / 2)] if n else np.array([])
        grad = np.gradient(ys, xs) if n > 2 and np.all(np.diff(xs) > 0) else np.full(n, np.nan)
        fitvals = _eval_best(series_refs[s.name][0], xs) if has_fit and n else None
        ftpl = None
        for i in range(n):
            r = r0 + 1 + i
            R = r + 1
            ws.write(r, 0, i, f.cell)
            ws.write(r, 1, _num(xs[i]), f.num); ws.write(r, 2, _num(ys[i]), f.num)
            ws.write(r, 3, _num(d.px[i]), f.num); ws.write(r, 4, _num(d.py[i]), f.num)
            ws.write(r, 5, d.status[i], f.cell); ws.write(r, 6, _num(d.confidence[i]), f.num); ws.write(r, 7, d.method[i], f.cell)
            lo, hi = max(R - 1, r0 + 2), min(R + 1, r0 + 1 + n)
            if n > 1:
                ws.write_formula(r, 8, f'=IFERROR((C{hi}-C{lo})/(B{hi}-B{lo}),"")', f.num, _num(grad[i]) if np.isfinite(grad[i]) else "")
            if i == 0:
                ws.write_formula(r, 9, "=0", f.num, 0.0)
            else:
                ws.write_formula(r, 9, f"=J{R - 1}+(B{R}-B{R - 1})*(C{R}+C{R - 1})/2", f.num, _num(cum[i]))
            if has_fit:
                tpl = _excel_template(series_refs[s.name][0], series_refs[s.name][1], f"B{R}")
                if tpl:
                    ws.write_formula(r, 10, tpl, f.num, _num(fitvals[i]))
                    ws.write_formula(r, 11, f"=C{R}-K{R}", f.num, _num(ys[i] - fitvals[i]))
        ws.autofilter(r0, 0, r0 + max(n, 1), len(hdr) - 1)
        ws.freeze_panes(r0 + 1, 0)
        ws.set_column(0, 0, 6); ws.set_column(1, 6, 13); ws.set_column(7, 7, 34); ws.set_column(8, 11, 20)
        if n > 1:
            ch = wb.add_chart({"type": "scatter", "subtype": "straight" if s.kind != "markers" else "marker_only"})
            sn = ws.get_name()
            ch.add_series(dict(name="extracted", categories=[sn, r0 + 1, 1, r0 + n, 1], values=[sn, r0 + 1, 2, r0 + n, 2],
                               line=dict(color=s.hex_color, width=1.5), marker=dict(type="circle", size=3, fill=dict(color=s.hex_color), border=dict(color=s.hex_color))))
            if has_fit and _excel_template(series_refs[s.name][0], series_refs[s.name][1], "B1"):
                ch.add_series(dict(name="fit", categories=[sn, r0 + 1, 1, r0 + n, 1], values=[sn, r0 + 1, 10, r0 + n, 10],
                                   line=dict(color="#000000", width=1.25, dash_type="dash"), marker=dict(type="none")))
            ch.set_title(dict(name=s.name, name_font=dict(size=11)))
            ch.set_x_axis(dict(name=_ax(chart.x_axis, "X (axis title unknown)"))); ch.set_y_axis(dict(name=_ax(chart.y_axis, "Y (axis title unknown)")))
            if chart.x_axis and chart.x_axis.calibration and chart.x_axis.calibration.scale in ("log10", "log2", "ln"):
                ch.set_x_axis(dict(log_base=10, name=_ax(chart.x_axis, "X (axis title unknown)")))
            if chart.y_axis and chart.y_axis.calibration and chart.y_axis.calibration.scale in ("log10", "log2", "ln"):
                ch.set_y_axis(dict(log_base=10, name=_ax(chart.y_axis, "Y (axis title unknown)")))
            ch.set_size({"width": 620, "height": 360})
            ws.insert_chart(3, 13, ch)
    # ----- Curve_Fitting
    ws = ws_map["Curve_Fitting"]
    rows = []
    for s in chart.series:
        a = asr.get(s.name, {})
        fm = a.get("fits") or {}
        for rank, m in enumerate(fm.get("models") or [], start=1):
            mt = m["metrics"]
            rows.append(dict(series=s.name, rank_by_BIC=rank, model=m["name"], selected="YES" if m["name"] == fm.get("best") else "",
                             parameters=m["n_params"], n_points=m["n_points"], R2=_num(mt["r2"]), adjusted_R2=_num(mt["adj_r2"]),
                             RMSE=_num(mt["rmse"]), MAE=_num(mt["mae"]), MSE=_num(mt["mse"]), MAPE_percent=_num(mt.get("mape")),
                             SSE=_num(mt["sse"]), AIC=_num(mt["aic"]), BIC=_num(mt["bic"]), AICc=_num(mt["aicc"]),
                             CV_RMSE=_num(mt.get("cv_rmse")), delta_BIC=_num(mt.get("delta_bic")), BIC_weight=_num(mt.get("bic_weight")),
                             equation=m["equation"]["text"], latex=m["equation"]["latex"], python=m["equation"]["python"],
                             excel=m["equation"]["excel"], valid_x_range=f"{m['valid_range'][0]:.6g} .. {m['valid_range'][1]:.6g}",
                             method=m["method"], residual_durbin_watson=_num(m["residuals"].get("durbin_watson")),
                             residual_shapiro_p=_num(m["residuals"].get("shapiro_p")), warnings="; ".join(m["warnings"])))
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    if rows:
        _table(ws, f, r0, 0, pd.DataFrame(rows), name=_sheet_name("", f"tblFit_{prefix.strip('_') or 'P1'}"),
               widths=dict(equation=60, latex=45, python=55, excel=50, model=26, series=16, warnings=50))
        ws.freeze_panes(r0 + 1, 3)
        notes = next((((asr.get(s.name) or {}).get("fits") or {}).get("notes") for s in chart.series if (asr.get(s.name) or {}).get("fits")), [])
        for i, t in enumerate(notes or []):
            ws.write(r0 + len(rows) + 3 + i, 0, t, f.note)
    else:
        ws.write(r0, 0, "No curve fitting results (run the analysis first).", f.warn)
    # ----- Statistical_Analysis
    ws = ws_map["Statistical_Analysis"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    stat_rows = {}
    for s in chart.series:
        st = (asr.get(s.name) or {}).get("stats")
        if not st:
            continue
        for var in ("x", "y"):
            for k, v in st[var].items():
                stat_rows.setdefault(f"{var}.{k}", {})[s.name] = _num(v)
    if stat_rows:
        df = pd.DataFrame(stat_rows).T.reset_index().rename(columns={"index": "statistic"})
        ws.write(r0, 0, f"Panel {chart.panel_index + 1} - descriptive statistics of extracted values", f.bold)
        last = _table(ws, f, r0 + 1, 0, df, table=False)
        xy = []
        for s in chart.series:
            e = ((asr.get(s.name) or {}).get("stats") or {}).get("xy") or {}
            if e:
                lr = e.get("linear_regression", {})
                xy.append(dict(series=s.name, n=e.get("n"), pearson_r=_num(e.get("pearson_r")), pearson_p=_num(e.get("pearson_p")),
                               spearman_rho=_num(e.get("spearman_rho")), kendall_tau=_num(e.get("kendall_tau")),
                               covariance=_num(e.get("covariance")), slope=_num(lr.get("slope")), intercept=_num(lr.get("intercept")),
                               R2_linear=_num(lr.get("r2")), independent_observations=e.get("independent_observations"),
                               note=e.get("significance_note", e.get("note", ""))))
        if xy:
            ws.write(last + 2, 0, "Correlation and linear regression of Y on X (p-values are NOT meaningful when observations are not independent)", f.bold)
            last = _table(ws, f, last + 3, 0, pd.DataFrame(xy), table=False, widths=dict(note=70))
        for a_, comp in (an.get("comparison") or {}).items():
            pairs = pd.DataFrame(comp.get("pairs", []))
            if len(pairs):
                pairs = pairs.drop(columns=["common_range"], errors="ignore")
                ws.write(last + 2, 0, f"Series comparison (axis {a_})", f.bold)
                last = _table(ws, f, last + 3, 0, pairs, table=False)
            per = pd.DataFrame(comp.get("per_series", {})).T.reset_index().rename(columns={"index": "series"})
            if len(per):
                ws.write(last + 2, 0, f"Per-series measures (axis {a_})", f.bold)
                last = _table(ws, f, last + 3, 0, per, table=False)
        ws.set_column(0, 0, 28)
    else:
        ws.write(r0, 0, "No statistics available (run the analysis first).", f.warn)
    # ----- Derivatives
    ws = ws_map["Derivatives"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    summ, samp = [], []
    for s in chart.series:
        d = (asr.get(s.name) or {}).get("derivative")
        if not d:
            continue
        summ.append(dict(series=s.name, method=d["method"], max_slope=_num(d["max_slope"]["value"]), x_at_max_slope=_num(d["max_slope"]["x"]),
                         min_slope=_num(d["min_slope"]["value"]), x_at_min_slope=_num(d["min_slope"]["x"]), mean_slope=_num(d["mean_slope"]),
                         inflection_points=", ".join(f"{p['x']:.5g}" for p in d["inflection_points"])))
        for xv, yv, d1, d2 in zip(d["x"], d["y_smooth"], d["d1"], d["d2"]):
            samp.append(dict(series=s.name, X=_num(xv), Y_smoothed=_num(yv), dY_dX=_num(d1), d2Y_dX2=_num(d2)))
    if summ:
        ws.write(r0, 0, f"Panel {chart.panel_index + 1} - numerical derivatives (smoothing spline; estimates, noise-sensitive)", f.bold)
        last = _table(ws, f, r0 + 1, 0, pd.DataFrame(summ), table=False, widths=dict(method=60, series=18))
        ws.write(last + 2, 0, "Sampled derivative curves (200 points per series)", f.bold)
        _table(ws, f, last + 3, 0, pd.DataFrame(samp), table=False)
    else:
        ws.write(r0, 0, "No derivative results.", f.warn)
    # ----- Integrals
    ws = ws_map["Integrals"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    rows, cum = [], []
    unit = (an.get("units") or {}).get("area") or "unit unknown (Y-unit x X-unit)"
    for s in chart.series:
        g = (asr.get(s.name) or {}).get("integral") or {}
        if g.get("ok"):
            rows.append(dict(series=s.name, from_x=_num(g["a"]), to_x=_num(g["b"]), trapezoid=_num(g["trapezoid"]), simpson=_num(g["simpson"]),
                             abs_area=_num(g["abs_area"]), area_positive=_num(g["area_positive"]), area_negative=_num(g["area_negative"]),
                             unit=unit, method=g["method"]))
            cum += [dict(series=s.name, X=_num(a_), cumulative_integral=_num(b_)) for a_, b_ in zip(g["cum_x"], g["cum_y"])]
    if rows:
        ws.write(r0, 0, f"Panel {chart.panel_index + 1} - definite integrals / area under curve", f.bold)
        last = _table(ws, f, r0 + 1, 0, pd.DataFrame(rows), table=False, widths=dict(method=70))
        for a_, comp in (an.get("comparison") or {}).items():
            ab = [dict(series_a=p["a"], series_b=p["b"], signed_area=_num(p.get("area_signed")), absolute_area=_num(p.get("area_absolute")))
                  for p in comp.get("pairs", []) if "area_absolute" in p]
            if ab:
                ws.write(last + 2, 0, f"Area between curves (axis {a_})", f.bold)
                last = _table(ws, f, last + 3, 0, pd.DataFrame(ab), table=False)
        ws.write(last + 2, 0, "Cumulative integral", f.bold)
        _table(ws, f, last + 3, 0, pd.DataFrame(cum), table=False)
    else:
        ws.write(r0, 0, "No integral results.", f.warn)
    # ----- Intersections
    ws = ws_map["Intersections"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    ix = an.get("intersections") or []
    ws.write(r0, 0, f"Panel {chart.panel_index + 1} - intersections between curves", f.bold)
    if ix:
        last = _table(ws, f, r0 + 1, 0, pd.DataFrame(ix), table=False)
    else:
        ws.write(r0 + 1, 0, "No intersections found.", f.cell)
        last = r0 + 1
    zc = [dict(series=s.name, zero_crossing_x=_num(v)) for s in chart.series for v in ((asr.get(s.name) or {}).get("features") or {}).get("zero_crossings", [])]
    ws.write(last + 2, 0, "Zero crossings of each series (y = 0)", f.bold)
    if zc:
        _table(ws, f, last + 3, 0, pd.DataFrame(zc), table=False)
    else:
        ws.write(last + 3, 0, "none", f.cell)
    # ----- Error_Analysis
    ws = ws_map["Error_Analysis"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    ws.write(r0, 0, f"Panel {chart.panel_index + 1} - error bars, bands and digitisation uncertainty", f.bold)
    er = []
    for s in chart.series:
        if s.errors is not None and len(s.errors):
            m = s.points.set_index("idx")
            for _, e in s.errors.iterrows():
                p = m.loc[e.idx] if e.idx in m.index else None
                er.append(dict(series=s.name, idx=int(e.idx), X=_num(p.x) if p is not None else None, Y=_num(p.y) if p is not None else None,
                               minus=_num(e.y_minus), plus=_num(e.y_plus), error_type=e.get("kind", "unspecified")))
    last = r0 + 1
    if er:
        ws.write(r0 + 1, 0, "Error bars (type SD / SE / CI is UNSPECIFIED unless stated in the figure caption)", f.note)
        last = _table(ws, f, r0 + 2, 0, pd.DataFrame(er), table=False)
    bd = [dict(series=s.name, points=len(s.band), min_width=_num((s.band.y_high - s.band.y_low).min()), max_width=_num((s.band.y_high - s.band.y_low).max()))
          for s in chart.series if s.band is not None]
    if bd:
        ws.write(last + 2, 0, "Shaded regions (type unspecified)", f.bold)
        last = _table(ws, f, last + 3, 0, pd.DataFrame(bd), table=False)
    un = an.get("uncertainty") or []
    if un:
        ws.write(last + 2, 0, "Digitisation uncertainty (mathematical estimate from pixel size and calibration residual)", f.bold)
        _table(ws, f, last + 3, 0, pd.DataFrame(un), table=False, widths=dict(source=60))
    elif not er and not bd:
        ws.write(last + 1, 0, "No error bars or bands detected; no uncertainty estimate available (axis calibration missing?).", f.cell)
    # ----- Confidence
    ws = ws_map["Confidence"]
    r0 = (ws.dim_rowmax + 2) if getattr(ws, "dim_rowmax", None) else 0
    q = chart.quality or {}
    ws.write(r0, 0, f"Panel {chart.panel_index + 1} - Quality Assessment (overall {q.get('overall')}, grade {q.get('grade')})", f.bold)
    parts = [dict(component=k, score=_num(v)) for k, v in (q.get("parts") or {}).items()]
    last = _table(ws, f, r0 + 1, 0, pd.DataFrame(parts), table=False) if parts else r0 + 1
    rows = []
    for s in chart.series:
        p = s.points
        rows.append(dict(series=s.name, series_confidence=_num(s.confidence), mean_point_confidence=_num(p.confidence.mean()),
                         min_point_confidence=_num(p.confidence.min()), points_below_0_5=int((p.confidence < 0.5).sum()),
                         markers=int((p.status == C.ST_MARKER).sum()), reconstructed=int((p.status == C.ST_RECON).sum()),
                         interpolated=int((p.status == C.ST_INTERP).sum()), manual=int((p.status == C.ST_MANUAL).sum()),
                         vector_vertices=int((p.status == C.ST_VECTOR).sum()), legend_matched=s.legend_matched,
                         coverage=_num(s.extra.get("coverage")), warnings="; ".join(s.warnings)))
    ws.write(last + 2, 0, "Series confidence and point provenance", f.bold)
    last = _table(ws, f, last + 3, 0, pd.DataFrame(rows), table=False, widths=dict(warnings=70, series=18))
    cal = [dict(axis=l, confidence=_num(a.calibration.confidence) if a.calibration else 0.0, rmse_px=_num(a.calibration.rmse_px) if a.calibration else None)
           for l, a in (("X", chart.x_axis), ("Y", chart.y_axis), ("Y2", chart.y2_axis)) if a]
    ws.write(last + 2, 0, "Axis calibration confidence", f.bold)
    _table(ws, f, last + 3, 0, pd.DataFrame(cal), table=False)


def export_excel(state: ProjectState, path: str | Path, lang: str = "en") -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(path), {"nan_inf_to_errors": False, "strings_to_numbers": False})
    wb.set_properties(dict(title=f"GraphInsight AI - {state.name}", author="GraphInsight AI (Hamid Yarali)",
                           comments="Data digitised from a chart image. See Processing_Log and Confidence sheets."))
    f = _Fmt(wb)
    base = ["Overview", "Original_Metadata", "Axis_Calibration", "Extracted_Data"]
    tail = ["Curve_Fitting", "Model_Parameters", "Statistical_Analysis", "Derivatives", "Integrals", "Intersections", "Error_Analysis",
            "Confidence", "Processing_Log"]
    ws_map = {}
    for n in base:
        ws_map[n] = wb.add_worksheet(n)
    max_series = max([len(c.series) for c in state.charts] + [1])
    for c_i, ch in enumerate(state.charts):
        prefix = "" if c_i == 0 else f"P{c_i + 1}_"
        for k in range(1, max(len(ch.series), 1) + 1):
            wb.add_worksheet(_sheet_name(prefix, f"Series_{k}"))
    for n in tail:
        ws_map[n] = wb.add_worksheet(n)
    # ---- Overview
    ws = ws_map["Overview"]
    ws.write(0, 0, "GraphInsight AI - analysis report data / داده‌های تحلیل", f.title)
    ws.write(1, 0, f"Project: {state.name}   |   generated {datetime.now().strftime('%Y-%m-%d %H:%M')}   |   developer: Hamid Yarali (حمید یارعلی)", f.sub)
    ws.merge_range(2, 0, 2, 9, "All values come from image digitisation. Statuses: marker = real marker found in the image; reconstructed = from the curve "
                   "centre-line; interpolated = gap filled; vector_vertex = exact vertex of a vector path; manual = entered by the user.", f.note)
    ws.set_row(2, 42)
    rows = []
    for ch in state.charts:
        npts = sum(len(s.points) for s in ch.series)
        rows.append(dict(panel=ch.panel_index + 1, chart_type=ch.chart_type, type_confidence=_num(ch.type_confidence), title=ch.title or "unknown",
                         x_axis=ch.x_axis.display_name if ch.x_axis else "-", y_axis=ch.y_axis.display_name if ch.y_axis else "-",
                         series=len(ch.series), points=npts, quality_score=_num(ch.quality.get("overall")), quality_grade=ch.quality.get("grade", "")))
    last = _table(ws, f, 4, 0, pd.DataFrame(rows), table=False, widths=dict(x_axis=26, y_axis=26, title=24, chart_type=24, type_confidence=16, quality_grade=14, quality_score=14))
    srows = []
    for ch in state.charts:
        for s in ch.series:
            srows.append(dict(panel=ch.panel_index + 1, series=s.name, colour=s.hex_color, kind=s.kind, axis=s.axis, points=len(s.points),
                              markers=int((s.points.status == C.ST_MARKER).sum()), confidence=_num(s.confidence), legend_matched=s.legend_matched))
    ws.write(last + 2, 0, "Series", f.bold)
    sl = _table(ws, f, last + 3, 0, pd.DataFrame(srows), table=False)
    for i, s in enumerate([s for ch in state.charts for s in ch.series]):
        ws.write(last + 4 + i, 2, srows[i]["colour"], f.swatch(srows[i]["colour"]))
    for w_ in sum([ch.warnings for ch in state.charts], []):
        sl += 1
    wr = [w for ch in state.charts for w in ch.warnings]
    if wr:
        ws.write(sl + 2, 0, "Warnings", f.warn)
        for i, w_ in enumerate(wr):
            ws.write(sl + 3 + i, 0, w_, f.wrap)
    # ---- metadata
    ws = ws_map["Original_Metadata"]
    ws.set_column(0, 0, 28); ws.set_column(1, 1, 90)
    ws.write(0, 0, "Original image and pre-processing", f.title)
    r = _kv(ws, f, 2, [(k, v) for k, v in state.image_meta.items()])
    ws.write(r + 1, 0, "Pre-processing", f.bold)
    r = _kv(ws, f, r + 2, [("scale factor", state.preprocess.get("scale")), ("rotation (deg)", state.preprocess.get("rotation_deg")),
                           ("noise sigma", state.preprocess.get("noise_sigma")), ("processed size", state.preprocess.get("processed_size")),
                           ("steps", "; ".join(state.preprocess.get("steps", [])) or "none")])
    ws.write(r + 1, 0, "Extraction settings", f.bold)
    _kv(ws, f, r + 2, list(state.settings.items()))
    # ---- per chart
    for c_i, ch in enumerate(state.charts):
        _write_chart(wb, f, ws_map, ch, "" if c_i == 0 else f"P{c_i + 1}_", state)
    # ---- Overview chart (all series of first chart)
    ch0 = state.charts[0] if state.charts else None
    if ch0 and any(len(s.points) > 1 for s in ch0.series):
        sc = wb.add_chart({"type": "scatter", "subtype": "straight_with_markers"})
        for k, s in enumerate(ch0.series, start=1):
            if s.kind in ("pie",) or len(s.points) < 2:
                continue
            sn = f"Series_{k}"
            n = len(s.points)
            sc.add_series(dict(name=s.name, categories=[sn, 4, 1, 3 + n, 1], values=[sn, 4, 2, 3 + n, 2], line=dict(color=s.hex_color, width=1.5),
                               marker=dict(type="circle", size=3, fill=dict(color=s.hex_color), border=dict(color=s.hex_color))))
        sc.set_title(dict(name="Extracted series (all)", name_font=dict(size=11)))
        sc.set_x_axis(dict(name=_ax(ch0.x_axis, "X (axis title unknown)")))
        sc.set_y_axis(dict(name=_ax(ch0.y_axis, "Y (axis title unknown)")))
        for ax_info, setter in ((ch0.x_axis, sc.set_x_axis), (ch0.y_axis, sc.set_y_axis)):
            if ax_info and ax_info.calibration and ax_info.calibration.scale in ("log10", "log2", "ln"):
                setter(dict(log_base=10, name=_ax(ax_info, "axis title unknown")))
        sc.set_size({"width": 760, "height": 420})
        ws_map["Overview"].insert_chart(len(rows) + len(srows) + 12, 0, sc)
    # ---- log
    ws = ws_map["Processing_Log"]
    ws.set_column(0, 0, 140)
    ws.write(0, 0, "Processing log", f.title)
    lines = list(state.processing_log) + [f"[panel {c.panel_index + 1}] {l}" for c in state.charts for l in c.log]
    for i, l in enumerate(lines):
        ws.write(2 + i, 0, l, f.cell)
    r = 4 + len(lines)
    ws.write(r, 0, "Data sources used in this workbook", f.bold)
    for i, t in enumerate([f"* {C.SRC_IMAGE}: pixel positions of markers / curve centre-lines (columns pixel_x, pixel_y)",
                           f"* {C.SRC_MATH}: derivatives, integrals, statistics, uncertainty estimates",
                           f"* {C.SRC_FIT}: Curve_Fitting and Model_Parameters (approximate models only)",
                           f"* {C.SRC_INTERP}: points with status 'interpolated' (gap fill)",
                           f"* {C.SRC_MANUAL}: points / calibrations entered by the user"]):
        ws.write(r + 1 + i, 0, t, f.cell)
    for n, w in ws_map.items():
        if n not in ("Processing_Log",):
            w.set_zoom(90)
    wb.close()
    return str(path)
