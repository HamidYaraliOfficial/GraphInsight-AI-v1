"""OPTIONAL: save real screenshots of the dashboard pages into docs/images/ui_*.png.

Requires the running environment of the app plus Playwright:
    pip install playwright && playwright install chromium
    python scripts/capture_screenshots.py

The script starts Streamlit on port 8599, loads a sample chart through the UI, visits every page and takes a screenshot.
NOTE: this script could not be executed in the environment where the release was assembled (no Streamlit / no network);
it is provided as a convenience and may need small adjustments if the UI texts change.
"""
from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
sys.path.insert(0, str(ROOT))

from dashboard.i18n import STR  # noqa: E402

PORT = 8599
URL = f"http://127.0.0.1:{PORT}"
PAGES = ["overview", "new", "imgproc", "digitize", "explorer", "math", "stats", "viz", "reports", "history"]


def wait_server(timeout: int = 90) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(URL + "/_stcore/health", timeout=2)
            return
        except Exception:  # noqa: BLE001
            time.sleep(1)
    raise RuntimeError("Streamlit did not start")


def main() -> None:
    from playwright.sync_api import sync_playwright
    OUT.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"), "--server.headless=true",
                             f"--server.port={PORT}", "--server.address=127.0.0.1"], cwd=ROOT)
    try:
        wait_server()
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            page.goto(URL)
            page.wait_for_timeout(4000)
            fa = STR["fa"]

            def goto(key):
                page.get_by_text(fa["nav_" + key], exact=False).first.click()
                page.wait_for_timeout(2500)

            goto("new")
            try:
                page.get_by_role("tab", name=fa["try_sample"]).click()
                page.wait_for_timeout(800)
                page.get_by_text("01_single_linear.png").first.click()
                page.keyboard.type("13_force")
                page.keyboard.press("Enter")
                page.wait_for_timeout(1500)
                page.get_by_role("button", name=fa["start_analysis"]).last.click()
                page.get_by_text(fa["done"]).first.wait_for(timeout=180000)
            except Exception as exc:  # noqa: BLE001
                print("could not load the sample automatically:", exc)
            for i, key in enumerate(PAGES, start=1):
                goto(key)
                if key == "math":
                    try:
                        page.get_by_role("button", name=fa["run_analysis"]).first.click()
                        page.wait_for_timeout(15000)
                    except Exception:  # noqa: BLE001
                        pass
                page.screenshot(path=str(OUT / f"ui_{i:02d}_{key}.png"), full_page=True)
                print("saved", f"ui_{i:02d}_{key}.png")
            browser.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
