import unittest

import numpy as np

from tests.common import analyze, gt, ocr_available
from core.axis_detector import split_title_unit
from core.coordinate_transform import PlotTransform, calibration_from_box, fit_calibration
from core.ocr_engine import parse_number


class TestCalibrationMath(unittest.TestCase):
    def test_linear_exact(self):
        c = fit_calibration([100, 200, 300], [0, 10, 20])
        self.assertEqual(c.scale, "linear")
        self.assertAlmostEqual(float(c.pixel_to_value(250)), 15.0, places=6)
        self.assertAlmostEqual(float(c.value_to_pixel(15.0)), 250.0, places=6)

    def test_reversed_axis(self):
        c = fit_calibration([100, 300], [20, 0])
        self.assertAlmostEqual(float(c.pixel_to_value(200)), 10.0, places=6)

    def test_log_axis_detected(self):
        c = fit_calibration([100, 200, 300, 400], [1, 10, 100, 1000])
        self.assertEqual(c.scale, "log10")
        self.assertAlmostEqual(float(c.pixel_to_value(250)), 10 ** 1.5, places=4)

    def test_outlier_rejected(self):
        c = fit_calibration([100, 200, 300, 400, 500], [0, 1, 2, 3, 9])
        self.assertEqual(len(c.outliers), 1)
        self.assertAlmostEqual(float(c.pixel_to_value(250)), 1.5, places=6)

    def test_piecewise(self):
        c = fit_calibration([0, 10, 20, 100], [0, 1, 2, 3], scale="piecewise")
        self.assertAlmostEqual(float(c.pixel_to_value(60)), 2.5, places=6)

    def test_too_few_ticks(self):
        self.assertIsNone(fit_calibration([100], [1]))
        self.assertIsNone(fit_calibration([100, 100], [1, 2]))

    def test_box_calibration_and_roundtrip(self):
        c = calibration_from_box(50, 450, 0, 10)
        tf = PlotTransform(c, calibration_from_box(300, 100, 0, 5))
        px, py = tf.to_pixel(np.array([5.0]), np.array([2.5]))
        x, y = tf.to_data(px, py)
        self.assertAlmostEqual(float(x[0]), 5.0)
        self.assertAlmostEqual(float(y[0]), 2.5)

    def test_serialisation(self):
        from core.coordinate_transform import AxisCalibration
        c = fit_calibration([100, 200, 300], [1, 10, 100])
        c2 = AxisCalibration.from_dict(c.to_dict())
        self.assertEqual(c2.scale, c.scale)
        self.assertAlmostEqual(float(c2.pixel_to_value(150)), float(c.pixel_to_value(150)))


class TestParsing(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(parse_number("12"), 12.0)
        self.assertEqual(parse_number("\u22122.5"), -2.5)
        self.assertEqual(parse_number("1,000"), 1000.0)
        self.assertEqual(parse_number("0,5"), 0.5)
        self.assertEqual(parse_number("1e-3"), 0.001)
        self.assertIsNone(parse_number("abc"))

    def test_title_unit(self):
        self.assertEqual(split_title_unit("Force (N)"), ("Force", "N"))
        self.assertEqual(split_title_unit("Time / s"), ("Time", "s"))
        self.assertEqual(split_title_unit("Level"), ("Level", None))
        self.assertEqual(split_title_unit(None), (None, None))


@unittest.skipUnless(ocr_available(), "Tesseract not installed")
class TestAxisDetectionOCR(unittest.TestCase):
    def test_linear_axes_titles_and_error(self):
        out = analyze("01_single_linear.png")
        ch = out.state.charts[0]
        self.assertEqual(ch.x_axis.unit, "s")
        self.assertIn("Signal", ch.y_axis.title)
        self.assertLess(ch.x_axis.calibration.rmse_px, 1.0)
        g = gt("01_single_linear")["panels"][0]
        sc = out.state.preprocess["scale"]
        c = g["corners"]["br"]
        self.assertAlmostEqual(float(ch.x_axis.calibration.pixel_to_value(c["px"] * sc)), c["x"], delta=0.05)

    def test_log_axes(self):
        out = analyze("06_log_log.png")
        ch = out.state.charts[0]
        self.assertEqual(ch.x_axis.calibration.scale, "log10")
        self.assertEqual(ch.y_axis.calibration.scale, "log10")

    def test_reversed_axis(self):
        out = analyze("07_unconventional_axes.png")
        cal = out.state.charts[0].x_axis.calibration
        self.assertLess(cal.a, 0)           # values decrease to the right

    def test_unknown_title_stays_unknown(self):
        out = analyze("13_force_four_curves.png")
        ch = out.state.charts[0]
        self.assertIsNone(ch.x_axis.title)
        self.assertEqual(ch.y_axis.unit, "N")


if __name__ == "__main__":
    unittest.main()
