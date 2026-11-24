import unittest

import numpy as np

from analysis import curve_fitting as CF
from analysis.data_cleaning import clean_xy, flag_outliers, noise_sigma


class TestFitting(unittest.TestCase):
    def setUp(self):
        self.x = np.linspace(0, 8, 80)
        rng = np.random.default_rng(1)
        self.y = 2.0 * np.exp(0.4 * self.x) + rng.normal(0, 0.1, 80)

    def test_exponential_recovered(self):
        r = CF.fit_all(self.x, self.y, ["exp", "poly1", "poly2"])
        best = r["fits"][0]
        self.assertEqual(best.family, "exp")
        self.assertAlmostEqual(best.params["b"]["value"], 0.4, delta=0.01)
        self.assertGreater(best.metrics["r2"], 0.999)

    def test_selection_prefers_simple_model(self):
        r = CF.fit_all(self.x, self.y)
        self.assertIn(r["best"], ("Exponential", "Exponential with offset"))

    def test_metrics_consistency(self):
        m = CF.metrics_for(np.array([1.0, 2, 3, 4]), np.array([1.1, 1.9, 3.2, 3.8]), 2)
        self.assertAlmostEqual(m["rmse"], np.sqrt(m["mse"]))
        self.assertAlmostEqual(m["sse"], 0.1 ** 2 + 0.1 ** 2 + 0.2 ** 2 + 0.2 ** 2)
        self.assertLess(m["adj_r2"], m["r2"])

    def test_parameter_uncertainty_present(self):
        f = CF.fit_all(self.x, self.y, ["exp"])["fits"][0]
        self.assertIsNotNone(f.params["a"]["stderr"])
        self.assertLess(f.params["a"]["ci_low"], f.params["a"]["value"])

    def test_equation_formats(self):
        f = CF.fit_all(self.x, self.y, ["exp"])["fits"][0]
        self.assertIn("exp", f.equation["text"])
        self.assertTrue(f.equation["excel"].startswith("="))
        self.assertTrue(f.equation["python"].startswith("lambda x:"))
        fn = eval(f.equation["python"], {"np": np})
        self.assertAlmostEqual(float(fn(4.0)), float(2.0 * np.exp(1.6)), delta=0.3)

    def test_piecewise_finds_break(self):
        x = np.linspace(0, 10, 100)
        y = np.where(x < 4, 2 * x, 8 + 0.5 * (x - 4))
        f = CF.fit_piecewise(x, y, 2)
        self.assertAlmostEqual(f.params["break1"]["value"], 4.0, delta=0.15)

    def test_custom_model_and_injection_rejected(self):
        r = CF.fit_all(self.x, self.y, ["poly1"], custom=["a*exp(b*x)"])
        self.assertTrue(any(f.family == "custom" for f in r["fits"]))
        for bad in ("__import__('os').system('echo hi')", "a*x; import os", "open('x')", "a.__class__"):
            r = CF.fit_all(self.x, self.y, ["poly1"], custom=[bad])
            self.assertFalse(any(f.family == "custom" for f in r["fits"]), bad)
            self.assertTrue(r["failures"])

    def test_too_few_points(self):
        r = CF.fit_all(np.array([1.0, 2, 3]), np.array([1.0, 2, 3]))
        self.assertTrue(all(f.family in ("poly1",) or f.n_params < 3 for f in r["fits"]))

    def test_cleaning(self):
        x, y, info = clean_xy(__import__("pandas").DataFrame({"x": [3, 1, 1, np.nan, 2], "y": [30, 10, 12, 5, 20]}))
        self.assertEqual(list(x), [1, 2, 3])
        self.assertEqual(y[0], 11.0)
        self.assertEqual(info["merged"], 1)
        yy = np.sin(np.linspace(0, 6, 100))
        yy[50] += 5
        self.assertTrue(flag_outliers(np.arange(100.0), yy)[50])
        self.assertLess(noise_sigma(np.linspace(0, 1, 50)), 1e-9)


if __name__ == "__main__":
    unittest.main()
