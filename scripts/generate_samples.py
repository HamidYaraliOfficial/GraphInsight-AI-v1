"""Generate synthetic sample charts WITH ground-truth data (used for validation and the README).

Every chart is synthetic ("Sample Data"). Ground truth is stored next to each image as <name>.json.
Usage:  python scripts/generate_samples.py [output_dir]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TAB = {"blue": "#1f77b4", "orange": "#ff7f0e", "green": "#2ca02c", "red": "#d62728",
       "purple": "#9467bd", "brown": "#8c564b", "black": "#000000"}


def hex2rgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


class GT:
    def __init__(self, name, title, notes=""):
        self.d = dict(name=name, title=title, notes=notes, sample_data=True, series=[], axes={}, panels=[])

    def add(self, name, color, x, y, markers=None, axis="y", panel=0, errors=None):
        e = dict(name=name, color=hex2rgb(color), x=np.asarray(x, float).tolist(), y=np.asarray(y, float).tolist(),
                 axis=axis, panel=panel)
        if markers is not None:
            e["markers"] = dict(x=np.asarray(markers[0], float).tolist(), y=np.asarray(markers[1], float).tolist())
        if errors is not None:
            e["errors"] = np.asarray(errors, float).tolist()
        self.d["series"].append(e)

    def axes(self, fig, ax, panel=0, xscale="linear", yscale="linear", ax2=None):
        fig.canvas.draw()
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        H = fig.get_size_inches()[1] * fig.dpi
        tr = ax.transData.transform
        c = {}
        for key, (xv, yv) in dict(bl=(x0, y0), br=(x1, y0), tl=(x0, y1)).items():
            px, py = tr((xv, yv))
            c[key] = dict(x=float(xv), y=float(yv), px=float(px), py=float(H - py))
        info = dict(panel=panel, xlim=[x0, x1], ylim=[y0, y1], xscale=xscale, yscale=yscale, corners=c)
        if ax2 is not None:
            info["y2lim"] = list(ax2.get_ylim())
        self.d["panels"].append(info)

    def save(self, fig, out: Path, fmt="png", **kw):
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out / f"{self.d['name']}.{fmt}", **kw)
        (out / f"{self.d['name']}.json").write_text(json.dumps(self.d, indent=1), encoding="utf-8")
        plt.close(fig)


def style(ax, grid=False):
    ax.tick_params(direction="out", length=5)
    if grid:
        ax.grid(True, color="#b0b0b0", lw=0.8)


def s01(out):
    g = GT("01_single_linear", "Single linear curve")
    x = np.linspace(0, 10, 400)
    y = 2.5 * x + 3
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.plot(x, y, color=TAB["blue"], lw=2)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Signal (V)"); ax.set_title("Linear response")
    ax.set_xlim(0, 10); ax.set_ylim(0, 30)
    style(ax); g.add("Series 1", TAB["blue"], x, y); g.axes(fig, ax)
    g.save(fig, out, bbox_inches=None)


def s02(out):
    g = GT("02_multi_curve", "Multi-curve")
    x = np.linspace(0, 10, 500)
    fs = {"Alpha": (lambda x: 4 + 3 * np.sin(x / 1.6), TAB["blue"]),
          "Beta": (lambda x: 0.15 * x ** 2 + 0.5, TAB["red"]),
          "Gamma": (lambda x: 9 * (1 - np.exp(-x / 2.5)), TAB["green"])}
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=110)
    for n, (f, c) in fs.items():
        ax.plot(x, f(x), color=c, lw=2, label=n); g.add(n, c, x, f(x))
    ax.set_xlabel("Position (mm)"); ax.set_ylabel("Response (a.u.)"); ax.legend(loc="upper left")
    ax.set_xlim(0, 10); ax.set_ylim(0, 16); style(ax); g.axes(fig, ax)
    g.save(fig, out)


def s03(out):
    g = GT("03_exponential", "Exponential curve")
    x = np.linspace(0, 8, 400)
    y = 2.0 * np.exp(0.45 * x)
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.plot(x, y, color=TAB["orange"], lw=2.2)
    ax.set_xlabel("Time (h)"); ax.set_ylabel("Count (-)"); ax.set_xlim(0, 8); ax.set_ylim(0, 80)
    style(ax); g.add("Series 1", TAB["orange"], x, y); g.axes(fig, ax)
    g.save(fig, out)


def s04(out):
    g = GT("04_markers", "Line with markers")
    xm = np.linspace(1, 12, 12)
    ym = 5 + 1.8 * np.sqrt(xm) * 2 + 0.3 * np.sin(xm * 2)
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.plot(xm, ym, "-o", color=TAB["purple"], lw=1.5, ms=8)
    ax.set_xlabel("Concentration (mg/L)"); ax.set_ylabel("Absorbance (AU)")
    ax.set_xlim(0, 13); ax.set_ylim(0, 20); style(ax)
    g.add("Series 1", TAB["purple"], xm, ym, markers=(xm, ym)); g.axes(fig, ax)
    g.save(fig, out)


def s05(out):
    g = GT("05_error_bars", "Error bars")
    xm = np.arange(1, 9, dtype=float)
    ym = 3 + 2 * xm - 0.1 * xm ** 2
    er = 0.6 + 0.12 * xm
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.errorbar(xm, ym, yerr=er, fmt="o", color=TAB["red"], ms=7, capsize=4, elinewidth=1.6)
    ax.set_xlabel("Dose (mg)"); ax.set_ylabel("Effect (%)"); ax.set_xlim(0, 9); ax.set_ylim(0, 24); style(ax)
    g.add("Series 1", TAB["red"], xm, ym, markers=(xm, ym), errors=er); g.axes(fig, ax)
    g.save(fig, out)


def s06(out):
    g = GT("06_log_log", "Log-log scale")
    x = np.logspace(0, 3, 300)
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=110)
    y1 = 2.0 * x ** 0.8
    y2 = 4000.0 * np.exp(-x / 300.0) + 3
    ax.loglog(x, y1, color=TAB["blue"], lw=2, label="Power law")
    ax.loglog(x, y2, color=TAB["red"], lw=2, label="Decay")
    ax.set_xlabel("Frequency (Hz)"); ax.set_ylabel("Magnitude (dB)"); ax.legend(loc="lower left")
    ax.set_xlim(1, 1000); ax.set_ylim(1, 10000); style(ax)
    g.add("Power law", TAB["blue"], x, y1); g.add("Decay", TAB["red"], x, y2)
    g.axes(fig, ax, xscale="log10", yscale="log10"); g.save(fig, out)


def s07(out):
    g = GT("07_unconventional_axes", "Reversed x-axis, negative y")
    x = np.linspace(-2.0, 3.0, 400)
    y = 40 * np.sin(x * 1.2) - 5 * x
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.plot(x, y, color=TAB["green"], lw=2)
    ax.set_xlim(3.0, -2.0); ax.set_ylim(-60, 60)
    ax.set_xlabel("Potential (V)"); ax.set_ylabel("Current (mA)"); style(ax)
    g.add("Series 1", TAB["green"], x, y); g.axes(fig, ax)
    g.save(fig, out)


def s08(out):
    g = GT("08_multi_panel", "Two panels")
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), dpi=110)
    x = np.linspace(0, 10, 300)
    a = axs[0]
    a.plot(x, np.sin(x) * 3 + 5, color=TAB["blue"], lw=2); a.set_xlim(0, 10); a.set_ylim(0, 10)
    a.set_xlabel("Time (s)"); a.set_ylabel("Voltage (V)"); a.set_title("(a)"); style(a)
    b = axs[1]
    b.plot(x, 12 - 1.1 * x, color=TAB["red"], lw=2); b.set_xlim(0, 10); b.set_ylim(0, 14)
    b.set_xlabel("Distance (m)"); b.set_ylabel("Height (m)"); b.set_title("(b)"); style(b)
    fig.tight_layout()
    g.add("Series 1", TAB["blue"], x, np.sin(x) * 3 + 5, panel=0)
    g.add("Series 1", TAB["red"], x, 12 - 1.1 * x, panel=1)
    g.axes(fig, a, 0); g.axes(fig, b, 1); g.save(fig, out)


def s09(out):
    """Low-quality: small, noisy, blurred, slightly rotated, JPEG-compressed."""
    import cv2
    g = GT("09_low_quality", "Low-quality scan-like image", notes="noise, blur, JPEG, 1.2 deg rotation")
    x = np.linspace(0, 10, 300)
    y = 5 + 3 * np.sin(x / 1.5)
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=80)
    ax.plot(x, y, color=TAB["blue"], lw=1.8); ax.set_xlim(0, 10); ax.set_ylim(0, 10)
    ax.set_xlabel("Time (s)"); ax.set_ylabel("Level (cm)"); style(ax)
    g.add("Series 1", TAB["blue"], x, y); g.axes(fig, ax)
    p = out / "09_low_quality.png"
    fig.savefig(p); plt.close(fig)
    im = cv2.imread(str(p))
    im = cv2.GaussianBlur(im, (3, 3), 0.9)
    rng = np.random.default_rng(3)
    im = np.clip(im.astype(float) + rng.normal(0, 9, im.shape), 0, 255).astype(np.uint8)
    h, w = im.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), 1.2, 1.0)
    im = cv2.warpAffine(im, m, (w, h), borderValue=(255, 255, 255))
    cv2.imwrite(str(out / "09_low_quality.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 38])
    p.unlink()
    g.d["notes"] += "; pixel ground truth not valid (rotated)"
    (out / "09_low_quality.json").write_text(json.dumps(g.d, indent=1), encoding="utf-8")


def s10(out):
    g = GT("10_grid_lines", "Dark grid")
    x = np.linspace(0, 10, 400)
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=110)
    f1, f2 = 3 + 2 * np.sin(x), 9 - 0.8 * x
    ax.plot(x, f1, color=TAB["blue"], lw=2, label="A"); ax.plot(x, f2, color=TAB["orange"], lw=2, label="B")
    ax.grid(True, color="#555555", lw=0.9, ls="-"); ax.legend(loc="upper right")
    ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.set_xlabel("Index (-)"); ax.set_ylabel("Value (-)"); style(ax)
    g.add("A", TAB["blue"], x, f1); g.add("B", TAB["orange"], x, f2); g.axes(fig, ax)
    g.save(fig, out)


def s11(out):
    g = GT("11_close_curves", "Close / crossing curves")
    x = np.linspace(0, 10, 500)
    fig, ax = plt.subplots(figsize=(7.5, 4.8), dpi=110)
    ys = {"C1": (4 + 0.5 * np.sin(x), TAB["blue"]), "C2": (4.4 + 0.2 * x * 0.1 + 0.35 * np.sin(x + 0.8), TAB["red"]),
          "C3": (3.6 + 0.12 * x, TAB["green"])}
    for n, (y, c) in ys.items():
        ax.plot(x, y, color=c, lw=2, label=n); g.add(n, c, x, y)
    ax.set_xlim(0, 10); ax.set_ylim(2, 7); ax.legend(loc="upper left", ncol=3)
    ax.set_xlabel("x (-)"); ax.set_ylabel("y (-)"); style(ax); g.axes(fig, ax)
    g.save(fig, out)


def s12(out):
    g = GT("12_dual_axis", "Dual Y-axis")
    x = np.linspace(0, 10, 400)
    fig, ax = plt.subplots(figsize=(7.8, 4.8), dpi=110)
    y1 = 10 + 8 * np.sin(x / 2.2)
    y2 = 0.3 * x ** 2 * 10
    ax.plot(x, y1, color=TAB["blue"], lw=2)
    ax.set_xlim(0, 10); ax.set_ylim(0, 30); ax.set_xlabel("Time (min)"); ax.set_ylabel("Temperature (C)")
    ax.yaxis.label.set_color(TAB["blue"]); ax.tick_params(axis="y", colors=TAB["blue"])
    ax2 = ax.twinx()
    ax2.plot(x, y2, color=TAB["red"], lw=2)
    ax2.set_ylim(0, 300); ax2.set_ylabel("Pressure (kPa)"); ax2.yaxis.label.set_color(TAB["red"])
    ax2.tick_params(axis="y", colors=TAB["red"], direction="out", length=5)
    ax.tick_params(direction="out", length=5)
    g.add("Temperature", TAB["blue"], x, y1, axis="y"); g.add("Pressure", TAB["red"], x, y2, axis="y2")
    g.axes(fig, ax, ax2=ax2); g.save(fig, out)


def s13(out):
    g = GT("13_force_four_curves", "Force vs displacement, four curves (imitation of the user's test chart)",
           notes="Synthetic imitation: Force (N) axis label only; horizontal axis title intentionally absent")
    fig, ax = plt.subplots(figsize=(7.5, 5.0), dpi=110)
    spec = [("PAM", TAB["blue"], 60, 2.2, 7.0), ("PAMCZ3%", TAB["orange"], 85, 2.6, 9.0),
            ("PAMCZ1%", TAB["green"], 72, 2.4, 8.0), ("PA", TAB["red"], 45, 1.8, 6.0)]
    for n, c, A, xp, xe in spec:
        x = np.linspace(0, xe, 360)
        y = A * (x / xp) * np.exp(1 - x / xp) ** 1.0
        y = y * (1 + 0.015 * np.sin(5 * x))
        ax.plot(x, y, color=c, lw=2, label=n); g.add(n, c, x, y)
    ax.set_ylabel("Force (N)"); ax.set_xlim(0, 10); ax.set_ylim(0, 100); ax.legend(loc="upper right")
    style(ax); g.axes(fig, ax)
    g.save(fig, out)


def s14(out):
    g = GT("14_bar_chart", "Bar chart")
    cats = ["A", "B", "C", "D", "E"]
    vals = np.array([12.0, 18.5, 9.0, 22.0, 15.5])
    fig, ax = plt.subplots(figsize=(6.5, 4.4), dpi=110)
    ax.bar(range(5), vals, color=TAB["blue"], width=0.6); ax.set_xticks(range(5)); ax.set_xticklabels(cats)
    ax.set_ylim(0, 25); ax.set_ylabel("Yield (%)"); style(ax)
    g.d["bars"] = dict(categories=cats, values=vals.tolist(), color=hex2rgb(TAB["blue"]))
    g.axes(fig, ax); g.save(fig, out)


def s15(out):
    g = GT("15_pie_chart", "Pie chart")
    vals = np.array([40.0, 30.0, 20.0, 10.0])
    cols = [TAB["blue"], TAB["orange"], TAB["green"], TAB["red"]]
    fig, ax = plt.subplots(figsize=(5, 5), dpi=110)
    ax.pie(vals, colors=cols, startangle=90, counterclock=False)
    g.d["pie"] = dict(values=vals.tolist(), fractions=(vals / vals.sum()).tolist(), colors=[hex2rgb(c) for c in cols])
    g.save(fig, out)


def s16(out):
    g = GT("16_confidence_band", "Curve with shaded confidence band")
    x = np.linspace(0, 10, 300)
    y = 5 + 0.6 * x + 1.5 * np.sin(x / 1.4)
    w = 0.6 + 0.12 * x
    fig, ax = plt.subplots(figsize=(7, 4.5), dpi=110)
    ax.fill_between(x, y - w, y + w, color=TAB["blue"], alpha=0.25, lw=0)
    ax.plot(x, y, color=TAB["blue"], lw=2)
    ax.set_xlim(0, 10); ax.set_ylim(0, 16); ax.set_xlabel("Day (-)"); ax.set_ylabel("Growth (cm)"); style(ax)
    g.add("Series 1", TAB["blue"], x, y); g.d["series"][0]["band"] = dict(x=x.tolist(), low=(y - w).tolist(), high=(y + w).tolist())
    g.axes(fig, ax); g.save(fig, out)


def s17(out):
    g = GT("17_vector_chart", "Vector PDF")
    x = np.linspace(0, 10, 40)
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    ax.plot(x, np.sin(x) * 5 + 6, color=TAB["red"], lw=1.6, label="S1")
    ax.plot(x, 0.8 * x + 1, color=TAB["blue"], lw=1.6, label="S2")
    ax.set_xlim(0, 10); ax.set_ylim(0, 12); ax.set_xlabel("x (m)"); ax.set_ylabel("y (N)"); ax.legend(loc="upper left")
    style(ax)
    g.add("S1", TAB["red"], x, np.sin(x) * 5 + 6); g.add("S2", TAB["blue"], x, 0.8 * x + 1); g.axes(fig, ax)
    g.save(fig, out, fmt="pdf")


ALL = [s01, s02, s03, s04, s05, s06, s07, s08, s09, s10, s11, s12, s13, s14, s15, s16, s17]


def main(out_dir=None):
    out = Path(out_dir) if out_dir else ROOT / "sample_charts"
    out.mkdir(parents=True, exist_ok=True)
    for fn in ALL:
        fn(out)
        print("generated", fn.__name__)
    print("Samples written to", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
