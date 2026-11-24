import json
import unittest

import numpy as np

from tests.common import SAMPLES, analyze, ensure_samples, gt, ocr_available
from config import constants as C

NEEDS_OCR = unittest.skipUnless(ocr_available(), "Tesseract not installed")


def mae_pct(series, g):
    p = series.points[series.points.status != C.ST_INTERP].dropna(subset=["x", "y"])
    ok = (p.x >= min(g["x"])) & (p.x <= max(g["x"]))
    p = p[ok]
    err = np.abs(p.y.to_numpy() - np.interp(p.x, g["x"], g["y"]))
    return float(err.mean() / np.ptp(g["y"]) * 100)


@NEEDS_OCR
class TestCurveExtraction(unittest.TestCase):
    def test_single_line_accuracy(self):
        ch = analyze("01_single_linear.png").state.charts[0]
        self.assertEqual(len(ch.series), 1)
        self.assertLess(mae_pct(ch.series[0], gt("01_single_linear")["series"][0]), 1.0)

    def test_multi_curve_with_legend(self):
        ch = analyze("02_multi_curve.png").state.charts[0]
        self.assertEqual(sorted(s.name for s in ch.series), ["Alpha", "Beta", "Gamma"])
        for s in ch.series:
            g = next(e for e in gt("02_multi_curve")["series"] if e["name"] == s.name)
            self.assertLess(mae_pct(s, g), 1.0)

    def test_four_force_curves(self):
        ch = analyze("13_force_four_curves.png").state.charts[0]
        self.assertEqual(sorted(s.name for s in ch.series), ["PA", "PAMCZ1%", "PAMCZ3%", "PAM"] if False else sorted(["PAM", "PAMCZ3%", "PAMCZ1%", "PA"]))
        self.assertIsNone(ch.x_axis.title)

    def test_grid_lines_do_not_create_series(self):
        ch = analyze("10_grid_lines.png").state.charts[0]
        self.assertEqual(len(ch.series), 2)

    def test_close_curves(self):
        ch = analyze("11_close_curves.png").state.charts[0]
        self.assertEqual(len(ch.series), 3)

    def test_log_log(self):
        ch = analyze("06_log_log.png").state.charts[0]
        for s in ch.series:
            g = next(e for e in gt("06_log_log")["series"] if e["name"] == s.name)
            p = s.points.dropna(subset=["x", "y"])
            err = np.abs(np.log10(p.y.to_numpy()) - np.log10(np.interp(p.x, g["x"], g["y"])))
            self.assertLess(float(err.mean()), 0.03)

    def test_markers_and_precision_recall(self):
        ch = analyze("04_markers.png").state.charts[0]
        s = ch.series[0]
        self.assertEqual(s.kind, "line+markers")
        mk = s.points[s.points.status == C.ST_MARKER]
        self.assertEqual(len(mk), 12)
        g = gt("04_markers")["series"][0]["markers"]
        self.assertLess(float(np.abs(np.sort(mk.y.to_numpy()) - np.sort(g["y"])).max()), 0.4)

    def test_error_bars(self):
        s = analyze("05_error_bars.png").state.charts[0].series[0]
        self.assertIsNotNone(s.errors)
        ge = np.array(gt("05_error_bars")["series"][0]["errors"])
        got = (s.errors.y_plus.to_numpy() + s.errors.y_minus.to_numpy()) / 2
        self.assertLess(float(np.mean(np.abs(got - ge) / ge)), 0.10)
        self.assertEqual(s.errors.kind.iloc[0], "unspecified")      # error type is never guessed

    def test_confidence_band(self):
        s = analyze("16_confidence_band.png").state.charts[0].series[0]
        self.assertIsNotNone(s.band)

    def test_dual_axis_assignment(self):
        ch = analyze("12_dual_axis.png").state.charts[0]
        self.assertIsNotNone(ch.y2_axis)
        axes = {s.name: s.axis for s in ch.series}
        self.assertEqual(sorted(axes.values()), ["y", "y2"])

    def test_multi_panel(self):
        st = analyze("08_multi_panel.png").state
        self.assertEqual(len(st.charts), 2)

    def test_low_quality_needs_manual_calibration_then_works(self):
        auto = analyze("09_low_quality.jpg").state.charts[0]
        self.assertTrue(any("manual" in w.lower() or "calibration" in w.lower() for w in auto.warnings + auto.y_axis.warnings))
        man = analyze("09_low_quality.jpg", manual={"panels": {"0": {"x_edges": [0, 10], "y_edges": [0, 10]}}}).state.charts[0]
        self.assertLess(mae_pct(man.series[0], gt("09_low_quality")["series"][0]), 2.0)

    def test_bar_chart(self):
        ch = analyze("14_bar_chart.png").state.charts[0]
        self.assertEqual(ch.chart_type, "bar")
        np.testing.assert_allclose(ch.bars["value"].to_numpy(), gt("14_bar_chart")["bars"]["values"], atol=0.3)

    def test_pie_chart(self):
        ch = analyze("15_pie_chart.png").state.charts[0]
        self.assertEqual(ch.chart_type, "pie")
        np.testing.assert_allclose(ch.pie["fraction"].to_numpy(), gt("15_pie_chart")["pie"]["fractions"], atol=0.01)


class TestNoOCRFallback(unittest.TestCase):
    def test_manual_calibration_without_ocr(self):
        from config.settings import ExtractionSettings
        s = ExtractionSettings(ocr_backend="none")
        out = analyze("01_single_linear.png", settings=s, manual={"panels": {"0": {"x_edges": [0, 10], "y_edges": [0, 30]}}})
        ch = out.state.charts[0]
        self.assertEqual(ch.x_axis.calibration.source, "manual")
        self.assertLess(mae_pct(ch.series[0], gt("01_single_linear")["series"][0]), 1.0)


class TestVectorPDF(unittest.TestCase):
    def test_vertices_extracted_exactly(self):
        from core.image_loader import load_image
        from core.pipeline import analyze_image
        from config.settings import ExtractionSettings
        ensure_samples()
        p = SAMPLES / "17_vector_chart.pdf"
        out = analyze_image(load_image(p), ExtractionSettings(), pdf_bytes=p.read_bytes())
        ch = out.state.charts[0]
        self.assertTrue(all((s.points.status == C.ST_VECTOR).all() for s in ch.series))
        self.assertEqual(len(ch.series), 2)


if __name__ == "__main__":
    unittest.main()
