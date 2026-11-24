import unittest

import numpy as np

from analysis import correlation_analysis as CA
from analysis import derivative_analysis as DA
from analysis import integral_analysis as IA
from analysis import intersection_analysis as IX
from analysis import statistical_analysis as SA


class TestDescriptive(unittest.TestCase):
    def test_describe(self):
        d = SA.describe(np.arange(1, 11, dtype=float))
        self.assertAlmostEqual(d["mean"], 5.5)
        self.assertAlmostEqual(d["median"], 5.5)
        self.assertAlmostEqual(d["std"], np.std(np.arange(1, 11), ddof=1))
        self.assertAlmostEqual(d["q1"], 3.25)

    def test_dense_points_flag_significance(self):
        x = np.linspace(0, 1, 50)
        r = SA.xy_statistics(x, 2 * x + 1, independent=False)
        self.assertFalse(r["significance_available"])
        self.assertAlmostEqual(r["pearson_r"], 1.0, places=6)
        r2 = SA.xy_statistics(x, 2 * x + 1 + np.random.default_rng(0).normal(0, 0.1, 50), independent=True)
        self.assertTrue(r2["significance_available"])

    def test_constant_series_has_no_fake_statistics(self):
        r = SA.xy_statistics(np.arange(10.0), np.ones(10), independent=True)
        self.assertNotIn("pearson_p", r)


class TestCalculus(unittest.TestCase):
    def test_derivative_of_sine(self):
        x = np.linspace(0, 2 * np.pi, 300)
        r = DA.derivative_report(x, np.sin(x))
        err = np.abs(r["d1"] - np.cos(r["xg"]))
        self.assertLess(float(np.median(err)), 0.02)
        self.assertEqual(len(r["inflection_points"]) >= 1, True)
        self.assertAlmostEqual(r["max_slope"]["value"], 1.0, delta=0.05)

    def test_integral_of_sine(self):
        x = np.linspace(0, np.pi, 200)
        g = IA.integrate_series(x, np.sin(x))
        self.assertAlmostEqual(g["trapezoid"], 2.0, delta=1e-3)
        self.assertAlmostEqual(g["simpson"], 2.0, delta=1e-4)
        self.assertAlmostEqual(g["cum_y"][-1], g["trapezoid"], places=9)

    def test_area_between(self):
        x = np.linspace(0, 1, 100)
        r = IA.area_between(x, x, x, np.zeros_like(x))
        self.assertAlmostEqual(r["signed"], 0.5, delta=1e-3)


class TestComparison(unittest.TestCase):
    def test_intersections(self):
        x = np.linspace(0, 10, 200)
        ix = IX.intersections({"a": (x, x), "b": (x, 10 - x)})
        self.assertEqual(len(ix), 1)
        self.assertAlmostEqual(ix[0]["x"], 5.0, delta=0.02)

    def test_zero_crossings(self):
        x = np.linspace(0, 2 * np.pi, 400)
        zc = IX.zero_crossings(x, np.sin(x))
        self.assertTrue(any(abs(v - np.pi) < 0.02 for v in zc))

    def test_compare_series(self):
        x = np.linspace(0, 10, 100)
        c = CA.compare_series({"a": (x, x), "b": (x, 2 * x)})
        self.assertEqual(c["ranking"]["max"][0], "b")
        self.assertAlmostEqual(c["pairs"][0]["pearson_r"], 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
