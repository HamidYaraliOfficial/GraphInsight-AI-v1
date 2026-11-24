"""Word (.docx) report with python-docx; full RTL support for Persian."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from PIL import Image

from analysis.scientific_interpretation import interpret
from config import constants as C
from models.chart_types import chart_label
from models.data_models import ChartResult, ProjectState
from . import chart_exporter as CE
from .report_text import axis_range, axis_table, fnum, series_summary_rows, tr

FONT_FA = "Tahoma"
FONT_EN = "Calibri"


def _png(arr: np.ndarray, max_side: int = 1600) -> io.BytesIO:
    im = Image.fromarray(arr)
    im.thumbnail((max_side, max_side))
    b = io.BytesIO()
    im.save(b, "PNG")
    b.seek(0)
    return b


class Writer:
    def __init__(self, lang: str):
        self.lang = "fa" if lang == "fa" else "en"
        self.rtl = self.lang == "fa"
        self.T = tr(lang)
        self.doc = Document()
        sec = self.doc.sections[0]
        sec.left_margin = sec.right_margin = Cm(2.0)
        sec.top_margin = sec.bottom_margin = Cm(2.0)
        st = self.doc.styles["Normal"]
        st.font.name = FONT_EN
        st.font.size = Pt(10.5)
        rpr = st.element.get_or_add_rPr()
        rf = rpr.find(qn("w:rFonts"))
        if rf is None:
            rf = OxmlElement("w:rFonts")
            rpr.append(rf)
        for a in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
            rf.set(qn(a), FONT_FA if self.rtl else FONT_EN)
        for name in ("Heading 1", "Heading 2", "Heading 3", "Title"):
            h = self.doc.styles[name]
            h.font.name = FONT_FA if self.rtl else FONT_EN
            h.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)
            hr = h.element.get_or_add_rPr()
            hrf = hr.find(qn("w:rFonts"))
            if hrf is None:
                hrf = OxmlElement("w:rFonts")
                hr.append(hrf)
            for a in ("w:ascii", "w:hAnsi", "w:cs"):
                hrf.set(qn(a), FONT_FA if self.rtl else FONT_EN)

    # ------------------------------------------------------------ primitives
    def _rtl_par(self, p):
        if self.rtl:
            pPr = p._p.get_or_add_pPr()
            pPr.append(OxmlElement("w:bidi"))
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    def _rtl_run(self, r):
        if self.rtl:
            rPr = r._r.get_or_add_rPr()
            rPr.append(OxmlElement("w:rtl"))
            f = rPr.find(qn("w:rFonts"))
            if f is None:
                f = OxmlElement("w:rFonts")
                rPr.append(f)
            f.set(qn("w:cs"), FONT_FA)

    def par(self, text="", bold=False, italic=False, size=None, align=None, color=None, ltr=False):
        p = self.doc.add_paragraph()
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor(*color)
        if not ltr:
            self._rtl_par(p)
            self._rtl_run(r)
        if align is not None:
            p.alignment = align
        return p

    def heading(self, text, level=1):
        h = self.doc.add_heading(text, level=level)
        self._rtl_par(h)
        for r in h.runs:
            self._rtl_run(r)
        return h

    def table(self, header: list[str], rows: list[list], widths=None, font=8.5):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.style = "Light Grid Accent 1"
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        if self.rtl:
            tblPr = t._tbl.tblPr
            tblPr.append(OxmlElement("w:bidiVisual"))
        for i, h in enumerate(header):
            c = t.rows[0].cells[i]
            c.text = ""
            r = c.paragraphs[0].add_run(str(h))
            r.bold = True
            r.font.size = Pt(font)
            self._rtl_run(r)
        for row in rows:
            cells = t.add_row().cells
            for i, v in enumerate(row):
                cells[i].text = ""
                r = cells[i].paragraphs[0].add_run("" if v is None else str(v))
                r.font.size = Pt(font)
        if widths:
            for row in t.rows:
                for i, w in enumerate(widths):
                    row.cells[i].width = Cm(w)
        self.doc.add_paragraph()
        return t

    def image(self, data, width_cm=16.0, caption=None):
        if isinstance(data, (bytes, bytearray)):
            data = io.BytesIO(data)
        if data is None:
            return
        self.doc.add_picture(data, width=Cm(width_cm))
        self.doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        if caption:
            self.par(caption, italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER)

    def kv(self, rows):
        self.table([self.T["name"], self.T["value"]], rows, widths=[5.0, 11.5], font=9)


def export_word(state: ProjectState, path: str | Path, original: np.ndarray | None = None, processed: np.ndarray | None = None,
                lang: str = "fa", full_tables: bool = True) -> str:
    W = Writer(lang)
    T, L = W.T, W.lang
    # ------------------------------------------------ title page
    for _ in range(4):
        W.doc.add_paragraph()
    W.par("GraphInsight AI", bold=True, size=30, align=WD_ALIGN_PARAGRAPH.CENTER, color=(0x1F, 0x38, 0x64), ltr=True)
    W.par(T["report_title"], bold=True, size=20, align=WD_ALIGN_PARAGRAPH.CENTER)
    W.par(T["subtitle"], size=12, align=WD_ALIGN_PARAGRAPH.CENTER, italic=True)
    W.doc.add_paragraph()
    W.par(f"{T['project']}: {state.name}", size=13, align=WD_ALIGN_PARAGRAPH.CENTER)
    W.par(f"{T['date']}: {datetime.now().strftime('%Y-%m-%d %H:%M')}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    W.par(f"{T['developer']}: {'حمید یارعلی (Hamid Yarali)' if L == 'fa' else 'Hamid Yarali'}", size=11, align=WD_ALIGN_PARAGRAPH.CENTER)
    if state.is_sample:
        W.par(T["sample"], bold=True, size=11, align=WD_ALIGN_PARAGRAPH.CENTER, color=(0xB0, 0x00, 0x20))
    W.doc.add_page_break()

    for ch in state.charts:
        multi = len(state.charts) > 1
        if multi:
            W.heading(f"{T['panel']} {ch.panel_index + 1}", 1)
        # ---------------------------------------------- 1. image info
        W.heading(T["s1"], 1)
        im = state.image_meta
        W.kv([(T["file"], im.get("name")), (T["fmt"], im.get("format")), (T["size"], f"{im.get('width')} × {im.get('height')}"),
              (T["dpi"], (" × ".join(f"{float(v):.0f}" for v in im["dpi"]) if im.get("dpi") else T["unknown"])), (T["ctype"], f"{chart_label(ch.chart_type, L)} (p = {fnum(ch.type_confidence, 2)})"),
              (T["n_axes"], 2 + int(ch.y2_axis is not None)), (T["n_series"], len(ch.series)),
              (T["n_points"], sum(len(s.points) for s in ch.series)),
              (T["preproc"], "; ".join(state.preprocess.get("steps", [])) or T["none"])])
        if original is not None:
            W.image(_png(original), 13.5, T["orig"])
        if processed is not None:
            W.image(CE.fig_bytes(CE.fig_overlay(processed, ch), "png", 130), 15.0, T["overlay"])
        # ---------------------------------------------- 2. chart info
        W.heading(T["s2"], 1)
        W.kv([(T["chart_title"], ch.title or T["unknown"]),
              (T["legend"], ", ".join(f"{e['name']}" for e in ch.legend) or ", ".join(s.name for s in ch.series) or T["unknown"])])
        hdr, arows = axis_table(ch, T)
        W.table(hdr, arows, font=8.5)
        W.image(CE.fig_bytes(CE.fig_reconstruction(ch), "png", 140), 15.0, T["recon"])
        # ---------------------------------------------- 3. numeric data
        W.heading(T["s3"], 1)
        sr = series_summary_rows(ch)
        if sr:
            W.table([T["series"], T["n_points"], T["start"], T["end"], T["maxv"], T["minv"], T["conf"]],
                    [[r["series"], r["points"], r.get("start"), r.get("end"), r.get("maximum"), r.get("minimum"), r["confidence"]] for r in sr],
                    font=8)
        ix = (ch.analysis or {}).get("intersections") or []
        W.par(f"{T['intersections']}: " + ("; ".join(f"{r['series_a']}×{r['series_b']} @ X={fnum(r['x'])}" for r in ix[:12]) if ix else T["none"]), size=9.5)
        W.par(T["status_legend"], italic=True, size=8.5)
        if ch.bars is not None and len(ch.bars):
            cols = [c for c in ("series", "category", "x_low", "x_high", "value", "top", "base") if c in ch.bars.columns]
            W.table(cols, [[fnum(v) if isinstance(v, float) else v for v in r] for r in ch.bars[cols].itertuples(index=False)], font=8)
        if ch.pie is not None and len(ch.pie):
            W.table(["sector", "angle start", "angle end", "%"], [[r.sector, fnum(r.angle_start_deg, 4), fnum(r.angle_end_deg, 4), fnum(r.percent, 4)]
                                                                     for r in ch.pie.itertuples()], font=8.5)
        if full_tables:
            for s in ch.series:
                W.heading(f"{T['all_points']} — {s.name}", 3)
                d = s.sorted_points()
                W.table(["#", "X", "Y", "px", "py", T["status"], T["conf"]],
                        [[int(r.idx), fnum(r.x, 6), fnum(r.y, 6), fnum(r.px, 6), fnum(r.py, 6), r.status, fnum(r.confidence, 3)] for r in d.itertuples()],
                        widths=[1.2, 2.6, 2.6, 2.2, 2.2, 3.0, 1.8], font=7.5)
        else:
            W.par(T["see_excel"], italic=True)
        # ---------------------------------------------- 4. math
        W.heading(T["s4"], 1)
        an = (ch.analysis or {}).get("series", {})
        for s in ch.series:
            a = an.get(s.name)
            if not a or not a.get("fits"):
                continue
            W.heading(s.name, 2)
            fm = a["fits"]
            best = next((m for m in fm["models"] if m["name"] == fm["best"]), None)
            if best:
                W.par(f"{T['best_model']}: {best['name']}", bold=True)
                W.par(best["equation"]["text"], ltr=True, size=10)
                eq_png = CE.equation_png(best["equation"]["latex"], best["equation"]["text"])
                if eq_png:
                    W.image(eq_png, 11.0)
                W.par("LaTeX: " + best["equation"]["latex"], size=8.5, ltr=True)
                W.par("Python: " + best["equation"]["python"], size=8.5, ltr=True)
                W.par("Excel: " + best["equation"]["excel"], size=8.5, ltr=True)
                W.table([T["params"], T["value"], T["std_err"], T["ci"]],
                        [[k, fnum(v["value"], 7), fnum(v.get("stderr"), 4), f"[{fnum(v.get('ci_low'), 5)}, {fnum(v.get('ci_high'), 5)}]"]
                         for k, v in best["params"].items()], font=8.5)
                m = best["metrics"]
                W.par(f"R² = {fnum(m['r2'], 6)} | adj.R² = {fnum(m['adj_r2'], 6)} | RMSE = {fnum(m['rmse'])} | MAE = {fnum(m['mae'])} | "
                      f"AIC = {fnum(m['aic'], 6)} | BIC = {fnum(m['bic'], 6)} | CV-RMSE = {fnum(m.get('cv_rmse'))} | n = {best['n_points']}", size=9, ltr=True)
                W.par(T["fit_note"], italic=True, size=9)
            W.table([T["rank"], T["model"], "k", "R²", "RMSE", "BIC", "ΔBIC", "✔"],
                    [[i + 1, m["name"], m["n_params"], fnum(m["metrics"]["r2"], 5), fnum(m["metrics"]["rmse"], 4), fnum(m["metrics"]["bic"], 5),
                      fnum(m["metrics"].get("delta_bic"), 3), "✔" if m["name"] == fm["best"] else ""] for i, m in enumerate(fm["models"][:12])], font=8)
            fg = CE.fig_fit(ch, s.name)
            if fg is not None:
                W.image(CE.fig_bytes(fg, "png", 130), 14.5)
            d = a.get("derivative")
            if d:
                W.par(f"{T['slope']}: max {fnum(d['max_slope']['value'])} @ X={fnum(d['max_slope']['x'])}; min {fnum(d['min_slope']['value'])} @ X={fnum(d['min_slope']['x'])}; "
                      f"mean {fnum(d['mean_slope'])}; inflection X = {', '.join(fnum(p['x']) for p in d['inflection_points']) or T['none']}", size=9.5)
                dg = CE.fig_derivative(ch, s.name)
                if dg is not None:
                    W.image(CE.fig_bytes(dg, "png", 120), 13.0)
            g = a.get("integral") or {}
            if g.get("ok"):
                W.par(f"{T['integral']}: ∫ Y dX = {fnum(g['trapezoid'], 6)} (trapezoid), {fnum(g['simpson'], 6)} (Simpson), "
                      f"X = {fnum(g['a'])} … {fnum(g['b'])}", size=9.5)
            ft = a.get("features") or {}
            if ft:
                W.par(f"{T['crit']}: " + ("; ".join(f"{t['type']} ({fnum(t['x'])}, {fnum(t['y'])})" for t in ft.get("turning_points", [])[:8]) or T["none"]), size=9.5)
        # ---------------------------------------------- 5. statistics
        W.heading(T["s5"], 1)
        rows = []
        for s in ch.series:
            st = (an.get(s.name) or {}).get("stats")
            if st:
                y = st["y"]
                rows.append([s.name, y["n"], fnum(y["mean"]), fnum(y["median"]), fnum(y["std"]), fnum(y["variance"]), fnum(y["min"]), fnum(y["max"]),
                             fnum(y.get("skewness"), 3), fnum(y.get("kurtosis_excess"), 3)])
        if rows:
            W.table([T["series"], T["n"], T["mean"], T["median"], T["std"], T["variance"], "min", "max", "skew", "kurt"], rows, font=7.5)
            for s in ch.series:
                xy = ((an.get(s.name) or {}).get("stats") or {}).get("xy") or {}
                if xy.get("pearson_r") is not None:
                    W.par(f"{s.name}: Pearson r = {fnum(xy['pearson_r'], 4)}, Spearman ρ = {fnum(xy['spearman_rho'], 4)}, Kendall τ = {fnum(xy['kendall_tau'], 4)}; "
                          f"{xy.get('significance_note', '')}", size=8.5)
        comp = next(iter(((ch.analysis or {}).get("comparison") or {}).values()), None)
        if comp and comp.get("pairs"):
            W.heading(T["corr"], 2)
            W.table(["A", "B", "mean diff", "max |diff|", "X@max", "RMSD", "Pearson r", "shape sim.", "area |A-B|"],
                    [[p["a"], p["b"], fnum(p.get("mean_difference")), fnum(p.get("max_abs_difference")), fnum(p.get("x_at_max_difference")), fnum(p.get("rmsd")),
                      fnum(p.get("pearson_r"), 4), fnum(p.get("shape_similarity"), 4), fnum(p.get("area_absolute"))] for p in comp["pairs"] if p.get("common_range")],
                    font=7.5)
            cf = CE.fig_comparison(ch)
            if cf is not None:
                W.image(CE.fig_bytes(cf, "png", 120), 14.0)
        # ---------------------------------------------- 6. interpretation
        W.heading(T["s6"], 1)
        itp = interpret(ch, L)
        for ptxt in itp["paragraphs"]:
            W.par(ptxt, size=10.5)
        # ---------------------------------------------- 7. quality
        W.heading(T["s7"], 1)
        q = ch.quality or {}
        W.par(f"{T['quality']}: {fnum(q.get('overall'), 3)} ({q.get('grade', '')})", bold=True)
        if q.get("parts"):
            W.table([T["name"], T["value"]], [[k, fnum(v, 3)] for k, v in q["parts"].items()], widths=[7, 4], font=9)
        if ch.warnings:
            for w_ in ch.warnings:
                W.par("⚠ " + w_, size=9, color=(0xB0, 0x00, 0x20), ltr=True)
        W.heading(T["sources"], 2)
        for t in T["src_list"]:
            W.par("• " + t, size=9.5)
        W.heading(T["limits"], 2)
        for t in itp["limitations"]:
            W.par("• " + t, size=9.5)
        if multi:
            W.doc.add_page_break()
    W.par("")
    W.par("GraphInsight AI — " + ("سازنده: حمید یارعلی" if L == "fa" else "Developer: Hamid Yarali"), italic=True, size=8.5, align=WD_ALIGN_PARAGRAPH.CENTER)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    W.doc.save(str(path))
    return str(path)
