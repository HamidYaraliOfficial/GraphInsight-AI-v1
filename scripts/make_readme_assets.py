"""Create the images used by README.md / README_FA.md from REAL engine output (no mock-ups).

Usage:  python scripts/make_readme_assets.py     (run scripts/make_sample_outputs.py and scripts/run_validation.py first)
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
IMG = ROOT / "docs" / "images"
IMG.mkdir(parents=True, exist_ok=True)

from analysis.mathematical_analysis import analyze_chart  # noqa: E402
from config import constants as C  # noqa: E402
from config.settings import ExtractionSettings  # noqa: E402
from core.curve_detector import find_color_clusters  # noqa: E402
from core.image_loader import load_image  # noqa: E402
from core.pipeline import analyze_image  # noqa: E402
from core.plot_area_detector import PlotBox  # noqa: E402
from exporters import chart_exporter as CE  # noqa: E402


def run(name, manual=None):
    out = analyze_image(load_image(ROOT / "sample_charts" / name), ExtractionSettings(), manual=manual or {})
    for ch in out.state.charts:
        analyze_chart(ch)
    return out


def save(fig, name, dpi=130):
    fig.savefig(IMG / name, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("wrote", name)


def architecture():
    fig, ax = plt.subplots(figsize=(13, 6.2))
    ax.set_xlim(0, 13); ax.set_ylim(0, 6.2); ax.axis("off"); ax.grid(False)
    cols = {"in": "#DCE9FF", "core": "#E3F6EA", "an": "#FFF1D6", "out": "#F3E3FA", "ui": "#FFE3E3"}

    def box(x, y, w, h, t, c):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12", fc=cols[c], ec="#44546A", lw=1.2))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8.6)

    def arrow(x0, y0, x1, y1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=12, color="#44546A", lw=1.2))
    box(0.2, 2.5, 1.9, 1.2, "Input\nPNG JPG TIFF BMP WEBP\nSVG PDF (vector)", "in")
    box(2.6, 4.4, 2.6, 1.3, "image_loader · pdf_processor\nimage_preprocessor\n(denoise, deskew, contrast)", "core")
    box(2.6, 2.6, 2.6, 1.3, "plot_area_detector\naxis_detector (ticks + OCR)\naxis_calibration", "core")
    box(2.6, 0.7, 2.6, 1.3, "curve_detector (colours)\nlegend_detector · marker_detector\nerror_bar_detector", "core")
    box(5.7, 2.6, 2.6, 1.3, "curve_digitizer\nbar / pie extractors\nconfidence_estimator", "core")
    box(5.7, 4.4, 2.6, 1.3, "chart_detector\n(type + support level)", "core")
    box(8.8, 4.4, 2.0, 1.3, "curve_fitting\nmodel_selection", "an")
    box(8.8, 2.6, 2.0, 1.3, "derivatives · integrals\nstatistics · correlation\nintersections", "an")
    box(8.8, 0.7, 2.0, 1.3, "uncertainty\nscientific_\ninterpretation", "an")
    box(11.2, 3.4, 1.65, 1.7, "Exporters\nExcel · Word · PDF\nCSV · JSON · PNG\nSVG · TXT · ZIP", "out")
    box(11.2, 0.7, 1.65, 1.9, "Streamlit\ndashboard\n(10 pages, RTL)\n+ SQLite storage", "ui")
    for a in [(2.1, 3.1, 2.6, 5.0), (2.1, 3.1, 2.6, 3.25), (3.9, 4.4, 3.9, 3.9), (3.9, 2.6, 3.9, 2.0), (5.2, 3.25, 5.7, 3.25),
              (5.2, 1.35, 5.7, 2.8), (7.0, 3.9, 7.0, 4.4), (8.3, 3.25, 8.8, 3.25), (8.3, 3.0, 8.8, 1.5), (8.3, 3.7, 8.8, 4.9),
              (10.8, 3.25, 11.2, 4.0), (10.8, 5.0, 11.2, 4.7), (10.8, 1.4, 11.2, 1.6), (12.0, 3.4, 12.0, 2.6)]:
        arrow(*a)
    ax.text(6.5, 6.0, "GraphInsight AI - modular architecture", ha="center", fontsize=13, weight="bold", color="#1F3864")
    ax.text(6.5, 0.15, "all processing is local · no cloud service · developer: Hamid Yarali", ha="center", fontsize=8.5, color="#555")
    save(fig, "architecture.png")


def sample_grid():
    names = ["01_single_linear.png", "02_multi_curve.png", "06_log_log.png", "05_error_bars.png", "12_dual_axis.png", "13_force_four_curves.png",
             "14_bar_chart.png", "15_pie_chart.png", "16_confidence_band.png", "08_multi_panel.png", "09_low_quality.jpg", "10_grid_lines.png"]
    fig, axs = plt.subplots(3, 4, figsize=(15, 9))
    for ax, n in zip(axs.ravel(), names):
        ax.imshow(plt.imread(ROOT / "sample_charts" / n) if not n.endswith(".jpg") else load_image(ROOT / "sample_charts" / n).rgb)
        ax.set_title(n, fontsize=9); ax.axis("off")
    fig.suptitle("Synthetic sample charts with ground truth (Sample Data)", fontsize=13)
    fig.tight_layout()
    save(fig, "sample_charts_grid.png", 110)


def pipeline_stages():
    out = run("13_force_four_curves.png")
    ch = out.state.charts[0]
    pp_rgb = out.processed
    box = PlotBox.from_dict(ch.box)
    clusters, crop = find_color_clusters(pp_rgb, box)
    from core.legend_detector import detect_legend
    from core.ocr_engine import get_backend
    import cv2
    detect_legend(pp_rgb, cv2.cvtColor(pp_rgb, cv2.COLOR_RGB2GRAY), box, crop, clusters, get_backend("tesseract"))
    clusters = [c for c in clusters if not c.neutral]
    fig, axs = plt.subplots(2, 3, figsize=(16, 9.4))
    axs = axs.ravel()
    axs[0].imshow(out.original); axs[0].set_title("1  original image")
    axs[1].imshow(pp_rgb); axs[1].set_title("2  pre-processed (+scale) and detected plot area / ticks")
    axs[1].add_patch(plt.Rectangle((box.x0, box.y0), box.w, box.h, fill=False, ec="#00A86B", lw=2, ls="--"))
    for ax_ in (ch.x_axis, ch.y_axis):
        for t in ax_.ticks:
            if ax_.orientation == "x":
                axs[1].plot([t.pixel] * 2, [ax_.line_pos, ax_.line_pos + 16], color="#E91E63", lw=1.5)
            else:
                axs[1].plot([ax_.line_pos, ax_.line_pos - 16], [t.pixel] * 2, color="#E91E63", lw=1.5)
    comp = np.full((crop.h, crop.w, 3), 255, np.uint8)
    for cl in clusters:
        comp[cl.mask > 0] = cl.rgb
    axs[2].imshow(comp); axs[2].set_title(f"3  colour clusters -> series masks ({len(clusters)} series colours, legend erased)")
    axs[3].imshow(pp_rgb)
    for s in ch.series:
        axs[3].plot(s.points.px, s.points.py, ".", ms=2.2, color=s.hex_color, mec="black", mew=0.2)
    axs[3].set_title("4  sub-pixel centre-lines, adaptive sampling")
    rec = CE.fig_reconstruction(ch, figsize=(5.5, 4.2))
    rec.canvas.draw()
    axs[4].imshow(np.asarray(rec.canvas.buffer_rgba())); plt.close(rec); axs[4].set_title("5  chart reconstructed from data (axis title 'unknown' kept)")
    best_rows = []
    an = ch.analysis["series"]
    for s in ch.series:
        b = next(m for m in an[s.name]["fits"]["models"] if m["name"] == an[s.name]["fits"]["best"])
        best_rows.append(f"{s.name}: {b['name']}  R²={b['metrics']['r2']:.4f}")
    axs[5].axis("off")
    axs[5].text(0.0, 0.95, "6  analysis results\n\n" + "\n".join(best_rows) + "\n\n(approximate models, not the true law)\n\npeak force per curve:\n" +
                "\n".join(f"{s.name}: {an[s.name]['metrics']['peak_value']:.1f} N @ x={an[s.name]['metrics']['x_at_peak']:.2f}" for s in ch.series),
                va="top", fontsize=11, family="DejaVu Sans")
    for a in axs[:5]:
        a.set_axis_off(); a.grid(False)
    for a, t in zip(axs[:5], [None] * 5):
        pass
    fig.tight_layout()
    save(fig, "pipeline_stages.png", 105)
    return out


def figures_from_samples():
    out = run("13_force_four_curves.png")
    ch = out.state.charts[0]
    save(CE.fig_reconstruction(ch, figsize=(8, 5)), "force_reconstruction.png")
    save(CE.fig_overlay(out.processed, ch, figsize=(9, 6)), "force_overlay.png", 100)
    s = ch.series_by_name("PAM")
    save(CE.fig_fit(ch, "PAM"), "force_fit_PAM.png")
    save(CE.fig_derivative(ch, "PAM"), "force_derivative_PAM.png")
    save(CE.fig_comparison(ch), "force_comparison.png")
    o = run("08_multi_panel.png")
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.6))
    for ax, c in zip(axs, o.state.charts):
        ax.imshow(o.processed); ax.set_axis_off(); ax.grid(False)
        b = c.box
        ax.add_patch(plt.Rectangle((b["x0"], b["y0"]), b["x1"] - b["x0"], b["y1"] - b["y0"], fill=False, ec="#00A86B", lw=2, ls="--"))
        for s in c.series:
            ax.plot(s.points.px, s.points.py, ".", ms=2.5, color=s.hex_color, mec="black", mew=0.2)
        ax.set_title(f"panel {c.panel_index + 1}: {c.x_axis.display_name} / {c.y_axis.display_name}")
    fig.tight_layout(); save(fig, "multi_panel.png", 100)
    o = run("05_error_bars.png")
    c = o.state.charts[0]
    fig, axs = plt.subplots(1, 2, figsize=(14, 4.6))
    axs[0].imshow(o.processed); axs[0].set_axis_off(); axs[0].grid(False)
    for s in c.series:
        m = s.points[s.points.status == C.ST_MARKER]
        axs[0].plot(m.px, m.py, "o", mfc="none", mec="black", ms=11, mew=1.5)
    axs[0].set_title("markers detected (circles)")
    fig2 = CE.fig_reconstruction(c, figsize=(6.5, 4.4)); fig2.canvas.draw()
    axs[1].imshow(np.asarray(fig2.canvas.buffer_rgba())); plt.close(fig2); axs[1].set_axis_off(); axs[1].grid(False)
    axs[1].set_title("reconstructed with extracted error bars (type unspecified)")
    fig.tight_layout(); save(fig, "error_bars.png", 100)
    for n, stem in (("06_log_log.png", "log_log"), ("12_dual_axis.png", "dual_axis"), ("16_confidence_band.png", "band")):
        o = run(n)
        save(CE.fig_reconstruction(o.state.charts[0], figsize=(7.5, 4.6)), f"{stem}_reconstruction.png")


def validation_plot():
    p = ROOT / "data" / "outputs" / "validation" / "validation_results.json"
    if not p.exists():
        return
    rows = [r for r in json.loads(p.read_text()) if r.get("mae_pct") is not None]
    names = [r["sample"].replace("(manual axis edges)", "(manual)") for r in rows]
    fig, ax = plt.subplots(figsize=(11, 5.2))
    y = np.arange(len(rows))
    ax.barh(y, [r["mae_pct"] for r in rows], color="#1F6FEB")
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=8); ax.invert_yaxis()
    ax.set_xlabel("mean absolute error  (% of the true value range of the curve; bars: % of the largest bar; pie: percentage points)")
    ax.set_title("Extraction accuracy on synthetic charts with known ground truth")
    for i, r in enumerate(rows):
        ax.text(r["mae_pct"] + 0.01, i, f"{r['mae_pct']:.2f}%", va="center", fontsize=8)
    fig.tight_layout(); save(fig, "validation_summary.png", 120)


def doc_previews():
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("LibreOffice not found - skipping document previews")
        return
    import pypdfium2 as pdfium
    src = ROOT / "sample_outputs" / "force_four_curves"
    tmp = ROOT / "data" / "outputs" / "_preview"
    tmp.mkdir(parents=True, exist_ok=True)

    def find_page(d, needle, start=0):
        for i in range(start, len(d)):
            try:
                if needle in d[i].get_textpage().get_text_range():
                    return i
            except Exception:  # noqa: BLE001
                pass
        return None

    def render(pdf_path, pages, stem, scale=1.1):
        d = pdfium.PdfDocument(str(pdf_path))
        if pages == "auto":
            m = find_page(d, "Polynomial") or find_page(d, "Exponential") or 4
            pages = [0, 1, m, max(len(d) - 2, 0)]
        for k, pn in enumerate(pages, start=1):
            if pn < len(d):
                d[pn].render(scale=scale).to_pil().convert("RGB").save(IMG / f"{stem}_{k}.png")
                print("wrote", f"{stem}_{k}.png")
    for f_, stem in (("force_four_curves_report_fa.docx", "word_fa"), ("force_four_curves_report_en.docx", "word_en")):
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(src / f_)], capture_output=True, timeout=240)
        render(tmp / (Path(f_).stem + ".pdf"), "auto", stem)
    render(src / "force_four_curves_report_en.pdf", [0, 2], "pdf_en")
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(tmp), str(src / "force_four_curves_data.xlsx")], capture_output=True, timeout=240)
    render(tmp / "force_four_curves_data.pdf", [0, 1], "excel")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    architecture(); sample_grid(); pipeline_stages(); figures_from_samples(); validation_plot(); doc_previews()
