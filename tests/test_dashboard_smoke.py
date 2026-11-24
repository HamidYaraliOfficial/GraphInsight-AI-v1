"""Smoke test of every dashboard page against the real engine, using a fake Streamlit (skipped if Streamlit is installed)."""
from __future__ import annotations

import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

REAL_STREAMLIT = importlib.util.find_spec("streamlit") is not None


@unittest.skipIf(REAL_STREAMLIT, "real Streamlit installed - run the app manually instead")
class DashboardSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import fake_streamlit
        cls.st = fake_streamlit.install()
        from config.settings import ExtractionSettings
        from core.image_loader import load_image
        from dashboard.session import AppSession, run_analysis
        from storage.database import Database
        from storage.project_manager import ProjectManager
        cls.td = Path(tempfile.mkdtemp())
        cls.app = AppSession(pm=ProjectManager(Database(cls.td / "t.db"), cls.td / "projects"))
        run_analysis(cls.app, load_image(ROOT / "sample_charts" / "02_multi_curve.png"), name="smoke", is_sample=True)

    def _render(self, name):
        mod = importlib.import_module(f"dashboard.{name}")
        mod.render(self.app)

    def test_pages_render_without_errors(self):
        for name in ["home", "upload", "image_processing", "digitization", "data_explorer", "mathematical_analysis",
                     "statistical_analysis", "visualization", "reports", "history"]:
            with self.subTest(page=name):
                self._render(name)

    def test_pages_after_analysis(self):
        from analysis.mathematical_analysis import analyze_chart
        analyze_chart(self.app.chart, dict(quick=True))
        for name in ["mathematical_analysis", "statistical_analysis", "reports", "visualization"]:
            with self.subTest(page=name):
                self._render(name)

    def test_pages_without_project(self):
        from dashboard.session import AppSession
        from storage.database import Database
        from storage.project_manager import ProjectManager
        empty = AppSession(pm=ProjectManager(Database(self.td / "e.db"), self.td / "p2"))
        for name in ["home", "image_processing", "digitization", "data_explorer", "mathematical_analysis", "statistical_analysis",
                     "visualization", "reports", "history"]:
            with self.subTest(page=name):
                importlib.import_module(f"dashboard.{name}").render(empty)


if __name__ == "__main__":
    unittest.main()
