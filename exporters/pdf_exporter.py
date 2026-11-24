"""PDF report. English (and Persian when arabic-reshaper + python-bidi + a suitable font are available).

For Persian without those packages the exporter converts the Word report with LibreOffice when it is installed;
otherwise it falls back to an English report and says so in the log.
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from analysis.scientific_interpretation import interpret
from config import settings
from config.logging_config import get_logger
from models.chart_types import chart_label
from models.data_models import ProjectState
from . import chart_exporter as CE
from .report_text import axis_range, axis_table, fnum, series_summary_rows, tr

log = get_logger("pdf-export")

_FONT_CANDIDATES = [
    str(settings.FONTS_DIR / "Vazirmatn-Regular.ttf"), str(settings.FONTS_DIR / "Vazir.ttf"),
    r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\arial.ttf", "/Library/Fonts/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
_BOLD = {"tahoma.ttf": "tahomabd.ttf", "arial.ttf": "arialbd.ttf", "DejaVuSans.ttf": "DejaVuSans-Bold.ttf"}


def _register_fonts() -> tuple[str, str] | None:
    for cand in _FONT_CANDIDATES:
        if os.path.exists(cand):
            try:
                pdfmetrics.registerFont(TTFont("GI", cand))
                bold = os.path.join(os.path.dirname(cand), _BOLD.get(os.path.basename(cand), ""))
                if os.path.isfile(bold):
                    pdfmetrics.registerFont(TTFont("GI-Bold", bold))
                else:
                    pdfmetrics.registerFont(TTFont("GI-Bold", cand))
                return "GI", "GI-Bold"
            except Exception as exc:  # noqa: BLE001
                log.warning("font %s not usable: %s", cand, exc)
    return None


def _get_display():
    """python-bidi moved ``get_display`` between releases; support both layouts."""
    try:
        from bidi.algorithm import get_display
    except ImportError:
        from bidi import get_display  # python-bidi >= 0.5
    return get_display


def _persian_available() -> bool:
    try:
        import arabic_reshaper  # noqa: F401
        _get_display()
        return _register_fonts() is not None
    except ImportError:
        return False


def _shape(text: str, rtl: bool) -> str:
    if not rtl:
        return text
    import arabic_reshaper
    return _get_display()(arabic_reshaper.reshape(text))


def _wrap_rtl(text: str, font: str, size: float, width: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if pdfmetrics.stringWidth(_shape(t, True), font, size) <= width or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _libreoffice_pdf(docx: Path, out_pdf: Path) -> bool:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    for p in (r"C:\Program Files\LibreOffice\program\soffice.exe", r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"):
        if not exe and os.path.exists(p):
            exe = p
    if not exe:
        return False
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run([exe, "--headless", "--convert-to", "pdf", "--outdir", td, str(docx)], check=True, timeout=180,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            produced = Path(td) / (docx.stem + ".pdf")
            if produced.exists():
                shutil.copy(produced, out_pdf)
                return True
        except Exception as exc:  # noqa: BLE001
            log.warning("LibreOffice conversion failed: %s", exc)
    return False


def export_pdf(state: ProjectState, path: str | Path, original: np.ndarray | None = None, processed: np.ndarray | None = None,
               lang: str = "en", max_rows: int = 40) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    want_fa = lang == "fa"
    if want_fa and not _persian_available():
        from .word_exporter import export_word
        with tempfile.TemporaryDirectory() as td:
            d = Path(td) / (path.stem + ".docx")
            export_word(state, d, original, processed, "fa", full_tables=False)
            if _libreoffice_pdf(d, path):
                log.info("Persian PDF produced via LibreOffice from the Word report")
                return str(path)
        log.warning("Persian PDF needs arabic-reshaper + python-bidi + a Persian-capable font (or LibreOffice). Falling back to English.")
        want_fa = False
    fonts = _register_fonts() if want_fa else None
    fn, fb = fonts if fonts else ("Helvetica", "Helvetica-Bold")
    L = "fa" if want_fa else "en"
    T = tr(L)
    ss = getSampleStyleSheet()
    al = TA_RIGHT if want_fa else 0
    body = ParagraphStyle("b", parent=ss["BodyText"], fontName=fn, fontSize=9.5, leading=13.5, alignment=al)
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], fontName=fb, fontSize=15, textColor=colors.HexColor("#1F3864"), alignment=al)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName=fb, fontSize=11.5, textColor=colors.HexColor("#1F3864"), alignment=al)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=10)
    ctr = ParagraphStyle("c", parent=body, alignment=TA_CENTER)
    W = A4[0] - 3.4 * cm

    def P(text, style=body):
        if want_fa:
            out = []
            for ln in _wrap_rtl(text, fn, style.fontSize, W - 6):
                out.append(Paragraph(escape(_shape(ln, True)), style))
            return out
        return [Paragraph(escape(text), style)]

    def tbl(header, rows, widths=None, fs=7.5):
        data = [[_shape(str(h), want_fa) for h in header]] + [[_shape(str(v), want_fa) if want_fa and isinstance(v, str) else v for v in r] for r in rows]
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), fn), ("FONTSIZE", (0, 0), (-1, -1), fs),
                               ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3864")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EEF2F8")]),
                               ("ALIGN", (0, 0), (-1, -1), "RIGHT" if want_fa else "LEFT")]))
        return t

    def img(data: bytes, width_cm: float):
        from PIL import Image as PILImage
        w, h = PILImage.open(io.BytesIO(data)).size
        return Image(io.BytesIO(data), width=width_cm * cm, height=width_cm * cm * h / w)

    story = [Spacer(1, 4 * cm), Paragraph("GraphInsight AI", ParagraphStyle("t", parent=ctr, fontName=fb, fontSize=30, textColor=colors.HexColor("#1F3864")))]
    for t_ in P(T["report_title"], ParagraphStyle("t2", parent=ctr, fontName=fb, fontSize=18)):
        story.append(t_)
    story += [Spacer(1, 1 * cm)]
    for t_ in P(f"{T['project']}: {state.name}", ctr) + P(f"{T['developer']}: Hamid Yarali" + (" (حمید یارعلی)" if want_fa else ""), ctr):
        story.append(t_)
    if state.is_sample:
        story += P(T["sample"], ParagraphStyle("sm", parent=ctr, textColor=colors.HexColor("#B00020")))
    story.append(PageBreak())
    for ch in state.charts:
        story += P(T["s1"], h1)
        im = state.image_meta
        rows = [[T["file"], im.get("name")], [T["fmt"], im.get("format")], [T["size"], f"{im.get('width')} x {im.get('height')}"],
                [T["ctype"], chart_label(ch.chart_type, L)], [T["n_series"], len(ch.series)],
                [T["n_points"], sum(len(s.points) for s in ch.series)]]
        story.append(tbl([T["name"], T["value"]], rows, [5 * cm, W - 5 * cm], 9))
        if original is not None:
            from PIL import Image as PILImage
            b = io.BytesIO()
            im_ = PILImage.fromarray(original)
            im_.thumbnail((1400, 1400))
            im_.save(b, "PNG")
            story += [Spacer(1, 6), img(b.getvalue(), 11)] + P(T["orig"], small)
        story += P(T["s2"], h1)
        story.append(tbl([T["name"], T["value"]], [[T["chart_title"], ch.title or T["unknown"]],
                                                     [T["legend"], ", ".join(e["name"] for e in ch.legend if e.get("name")) or ", ".join(s.name for s in ch.series)]],
                         [4 * cm, W - 4 * cm], 8.5))
        hdr, arows = axis_table(ch, T)
        story += [Spacer(1, 4), tbl(hdr, arows, None, 8)]
        story += [Spacer(1, 6), img(CE.fig_bytes(CE.fig_reconstruction(ch), "png", 130), 15)] + P(T["recon"], small)
        if processed is not None:
            story += [img(CE.fig_bytes(CE.fig_overlay(processed, ch), "png", 110), 15)] + P(T["overlay"], small)
        story.append(PageBreak())
        story += P(T["s3"], h1)
        sr = series_summary_rows(ch)
        if sr:
            story.append(tbl([T["series"], T["n_points"], T["start"], T["end"], T["maxv"], T["minv"], T["conf"]],
                             [[r["series"], r["points"], r.get("start"), r.get("end"), r.get("maximum"), r.get("minimum"), r["confidence"]] for r in sr]))
        story += P(T["status_legend"], small)
        for s in ch.series:
            d = s.sorted_points()
            step = max(1, len(d) // max_rows)
            story += [Spacer(1, 6)] + P(f"{s.name} — {T['all_points']} ({T['see_excel']})", h2)
            story.append(tbl(["#", "X", "Y", T["status"], T["conf"]],
                             [[int(r.idx), fnum(r.x, 6), fnum(r.y, 6), r.status, fnum(r.confidence, 3)] for r in d.iloc[::step].itertuples()]))
        story.append(PageBreak())
        story += P(T["s4"], h1)
        an = (ch.analysis or {}).get("series", {})
        for s in ch.series:
            a = an.get(s.name)
            if not a or not a.get("fits"):
                continue
            fm = a["fits"]
            best = next((m for m in fm["models"] if m["name"] == fm["best"]), None)
            story += P(s.name, h2)
            if best:
                story += P(f"{T['best_model']}: {best['name']}", body)
                story.append(Paragraph(escape(best["equation"]["text"]), ParagraphStyle("eq", parent=body, fontName="Courier", fontSize=8, alignment=0)))
                m = best["metrics"]
                story.append(Paragraph(escape(f"R2={fnum(m['r2'], 6)}  adjR2={fnum(m['adj_r2'], 6)}  RMSE={fnum(m['rmse'])}  MAE={fnum(m['mae'])}  AIC={fnum(m['aic'], 6)}  BIC={fnum(m['bic'], 6)}"),
                                       ParagraphStyle("m", parent=small, alignment=0)))
                story.append(tbl([T["params"], T["value"], T["std_err"], T["ci"]],
                                 [[k, fnum(v["value"], 7), fnum(v.get("stderr"), 4), f"[{fnum(v.get('ci_low'), 5)}, {fnum(v.get('ci_high'), 5)}]"]
                                  for k, v in best["params"].items()]))
                story += P(T["fit_note"], small)
            fg = CE.fig_fit(ch, s.name)
            if fg is not None:
                story.append(img(CE.fig_bytes(fg, "png", 110), 13))
        story.append(PageBreak())
        story += P(T["s6"], h1)
        itp = interpret(ch, L)
        for ptxt in itp["paragraphs"]:
            story += P(ptxt, body) + [Spacer(1, 4)]
        story += P(T["s7"], h1)
        q = ch.quality or {}
        story += P(f"{T['quality']}: {fnum(q.get('overall'), 3)} ({q.get('grade', '')})", body)
        story += P(T["sources"], h2)
        for t_ in T["src_list"]:
            story += P("• " + t_, body)
        story += P(T["limits"], h2)
        for t_ in itp["limitations"]:
            story += P("• " + t_, body)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.7 * cm, rightMargin=1.7 * cm, topMargin=1.7 * cm, bottomMargin=1.7 * cm,
                            title=f"GraphInsight AI - {state.name}", author="GraphInsight AI - Hamid Yarali")
    doc.build(story)
    return str(path)
