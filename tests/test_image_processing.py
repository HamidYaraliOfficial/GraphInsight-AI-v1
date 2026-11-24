import unittest

import numpy as np

from tests.common import ROOT, SAMPLES, analyze, ensure_samples  # noqa: F401
from core.image_loader import ImageLoadError, load_image, load_image_bytes, validate_file
from core.image_preprocessor import estimate_noise, preprocess, rotate_bound
from core.plot_area_detector import detect_panels


class TestLoader(unittest.TestCase):
    def test_rejects_bad_extension(self):
        with self.assertRaises(ImageLoadError):
            validate_file("evil.exe", b"MZ....")

    def test_rejects_fake_png(self):
        with self.assertRaises(ImageLoadError):
            validate_file("x.png", b"not really a png")

    def test_rejects_empty(self):
        with self.assertRaises(ImageLoadError):
            validate_file("x.png", b"")

    def test_loads_png_and_jpg(self):
        ensure_samples()
        a = load_image(SAMPLES / "01_single_linear.png")
        b = load_image(SAMPLES / "09_low_quality.jpg")
        self.assertEqual(a.rgb.ndim, 3)
        self.assertEqual(b.fmt, "JPG")

    def test_loads_pdf(self):
        ensure_samples()
        li = load_image(SAMPLES / "17_vector_chart.pdf")
        self.assertGreater(li.width, 500)


class TestPreprocess(unittest.TestCase):
    def test_deskew_restores_axes(self):
        ensure_samples()
        li = load_image(SAMPLES / "01_single_linear.png")
        tilted = rotate_bound(li.rgb, 1.5)
        pp = preprocess(tilted, denoise=False)
        self.assertLess(abs(pp.rotation_deg + 1.5), 0.4)
        boxes = detect_panels(pp.gray, pp.processed)
        self.assertGreaterEqual(boxes[0].confidence, 0.9)

    def test_noise_estimate_increases_with_noise(self):
        rng = np.random.default_rng(0)
        base = np.full((200, 200), 128, np.uint8)
        noisy = np.clip(base + rng.normal(0, 10, base.shape), 0, 255).astype(np.uint8)
        self.assertGreater(estimate_noise(noisy), estimate_noise(base) + 5)


class TestPlotArea(unittest.TestCase):
    def test_single_panel(self):
        ensure_samples()
        li = load_image(SAMPLES / "02_multi_curve.png")
        pp = preprocess(li.rgb)
        boxes = detect_panels(pp.gray, pp.processed)
        self.assertEqual(len(boxes), 1)
        self.assertTrue(boxes[0].framed)

    def test_two_panels(self):
        ensure_samples()
        li = load_image(SAMPLES / "08_multi_panel.png")
        pp = preprocess(li.rgb)
        self.assertEqual(len(detect_panels(pp.gray, pp.processed)), 2)


if __name__ == "__main__":
    unittest.main()
