import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.common import analyze, ocr_available


@unittest.skipUnless(ocr_available(), "Tesseract not installed")
class TestExports(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.out = analyze("02_multi_curve.png")
        cls.td = Path(tempfile.mkdtemp())
        from exporters.export_manager import export_all
        cls.made = export_all(cls.out.state, cls.td, ["docx", "xlsx", "pdf", "csv", "json", "png", "svg", "txt", "zip"], "en",
                              cls.out.original, cls.out.processed, dict(quick=True))

    def test_no_errors(self):
        self.assertNotIn("_errors", self.made)

    def test_excel_structure(self):
        import openpyxl
        wb = openpyxl.load_workbook(self.made["data.xlsx"])
        for sheet in ["Overview", "Original_Metadata", "Axis_Calibration", "Extracted_Data", "Series_1", "Series_3", "Curve_Fitting",
                      "Model_Parameters", "Statistical_Analysis", "Derivatives", "Integrals", "Intersections", "Error_Analysis",
                      "Confidence", "Processing_Log"]:
            self.assertIn(sheet, wb.sheetnames)
        ws = wb["Series_1"]
        self.assertEqual(ws.freeze_panes, "A5")
        self.assertTrue(ws.auto_filter.ref)
        formulas = [c.value for row in ws.iter_rows(min_row=5, max_row=8) for c in row if isinstance(c.value, str) and c.value.startswith("=")]
        self.assertTrue(formulas)

    def test_word_opens_and_has_sections(self):
        from docx import Document
        d = Document(self.made["report.docx"])
        text = "\n".join(p.text for p in d.paragraphs)
        self.assertIn("GraphInsight AI", text)
        self.assertIn("Hamid Yarali", text)
        self.assertGreater(len(d.tables), 3)
        self.assertGreater(len(d.inline_shapes), 2)

    def test_pdf_header(self):
        self.assertTrue(Path(self.made["report.pdf"]).read_bytes().startswith(b"%PDF"))

    def test_csv_per_series_and_combined(self):
        names = [Path(p).name for k, p in self.made.items() if k.endswith(".csv")]
        self.assertTrue(any("all_series" in n for n in names))
        self.assertEqual(sum("series_" in n and "all_series" not in n for n in names), 3)

    def test_json_roundtrip(self):
        from exporters.json_exporter import load_project_json
        st = load_project_json(self.made["project.json"])
        self.assertEqual(len(st.charts[0].series), 3)
        self.assertEqual(len(st.charts[0].series[0].points), len(self.out.state.charts[0].series[0].points))
        self.assertAlmostEqual(st.charts[0].x_axis.calibration.a, self.out.state.charts[0].x_axis.calibration.a)

    def test_zip_contains_files(self):
        with zipfile.ZipFile(self.made["all_outputs.zip"]) as z:
            names = z.namelist()
        self.assertIn("manifest.json", names)
        self.assertTrue(any(n.endswith(".xlsx") for n in names))

    def test_persian_word_report(self):
        from exporters.word_exporter import export_word
        p = export_word(self.out.state, self.td / "fa.docx", self.out.original, self.out.processed, "fa", full_tables=False)
        from docx import Document
        text = "\n".join(x.text for x in Document(p).paragraphs)
        self.assertIn("گزارش علمی", text)
        self.assertIn("حمید یارعلی", text)


class TestStorage(unittest.TestCase):
    def test_project_lifecycle_and_undo(self):
        from config.settings import ExtractionSettings
        from core import manual_edit as ME
        from storage.database import Database
        from storage.history_manager import HistoryManager
        from storage.project_manager import ProjectManager
        import numpy as np
        from models.data_models import ProjectState, ChartResult, Series, AxisInfo
        import pandas as pd
        from core.coordinate_transform import fit_calibration
        td = Path(tempfile.mkdtemp())
        pm = ProjectManager(Database(td / "t.db"), td / "projects")
        pts = pd.DataFrame(dict(idx=[0.0, 1.0], x=[1.0, 2.0], y=[1.0, 4.0], px=[10.0, 20.0], py=[50.0, 20.0], status="reconstructed",
                                confidence=0.9, method="m"))
        ch = ChartResult(x_axis=AxisInfo(calibration=fit_calibration([0, 100], [0, 10])),
                         y_axis=AxisInfo(orientation="y", calibration=fit_calibration([100, 0], [0, 10])), series=[Series("s", points=pts)])
        st = ProjectState(name="demo", charts=[ch])
        img = np.full((20, 30, 3), 255, np.uint8)
        pm.create(st, img, img)
        hm = HistoryManager()
        hm.push(st, "add")
        ME.add_point(st, st.chart, "s", 3.0, 9.0)
        self.assertEqual(len(st.chart.series[0].points), 3)
        self.assertEqual(st.chart.series[0].points.status.iloc[-1], "manual")
        back, label = hm.undo(st)
        self.assertEqual(len(back.chart.series[0].points), 2)
        new = pm.copy(st.project_id)
        z = pm.export_zip(st.project_id, td / "p.zip")
        imp = pm.import_zip(z)
        self.assertEqual(len(pm.list()), 3)
        pm.delete(new)
        self.assertEqual(len(pm.list()), 2)
        s2, o, p = pm.open(imp)
        self.assertEqual(s2.name, "demo")

    def test_zip_slip_blocked(self):
        from storage.database import Database
        from storage.project_manager import ProjectManager
        td = Path(tempfile.mkdtemp())
        pm = ProjectManager(Database(td / "t.db"), td / "projects")
        z = td / "evil.zip"
        with zipfile.ZipFile(z, "w") as zf:
            zf.writestr("project.json", json.dumps({"format": "graphinsight-project"}))
            zf.writestr("../../evil.txt", "x")
        with self.assertRaises(ValueError):
            pm.import_zip(z)


if __name__ == "__main__":
    unittest.main()
