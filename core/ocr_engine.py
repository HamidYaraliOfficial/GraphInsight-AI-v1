"""OCR layer with a pluggable backend (Tesseract by default) and number-aware helpers.

* ``read_number``  - reads a single tick label (handles unicode minus, thousands separators and
  superscript powers of ten such as 10^3 which Tesseract would otherwise read as "103").
* ``read_text``    - reads titles / axis labels / legend entries.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass

import cv2
import numpy as np

from config.logging_config import get_logger

log = get_logger("ocr")

_WIN_PATHS = [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]

INSTALL_HINT = (
    "Tesseract OCR was not found. Install it:\n"
    "  Windows : https://github.com/UB-Mannheim/tesseract/wiki  (then add it to PATH or set TESSERACT_CMD in .env)\n"
    "  Ubuntu  : sudo apt install tesseract-ocr\n"
    "  macOS   : brew install tesseract\n"
    "Without OCR you can still enter axis tick values manually in the 'Image Processing' page.")


@dataclass
class OCRNumber:
    value: float | None
    raw: str
    conf: float
    is_power10: bool = False


class OCRBackend:
    name = "none"

    @property
    def available(self) -> bool:
        return False

    def read(self, img: np.ndarray, psm: int = 7, whitelist: str | None = None, lang: str | None = None):
        """Return (text, mean_confidence 0-1)."""
        return "", 0.0


class TesseractBackend(OCRBackend):
    name = "tesseract"

    def __init__(self, lang: str = "eng"):
        self.lang = lang
        self._ok = None
        self._pt = None

    def _init(self):
        if self._ok is not None:
            return
        try:
            import pytesseract
            cmd = os.environ.get("TESSERACT_CMD") or shutil.which("tesseract")
            if not cmd:
                for p in _WIN_PATHS:
                    if os.path.exists(p):
                        cmd = p
                        break
            if not cmd:
                self._ok = False
                return
            pytesseract.pytesseract.tesseract_cmd = cmd
            pytesseract.get_tesseract_version()
            self._pt = pytesseract
            self._ok = True
        except Exception as exc:  # noqa: BLE001
            log.warning("Tesseract unavailable: %s", exc)
            self._ok = False

    @property
    def available(self) -> bool:
        self._init()
        return bool(self._ok)

    def languages(self) -> list[str]:
        if not self.available:
            return []
        try:
            return list(self._pt.get_languages(config=""))
        except Exception:  # noqa: BLE001
            return ["eng"]

    def read(self, img, psm=7, whitelist=None, lang=None):
        if not self.available:
            return "", 0.0
        cfg = f"--psm {psm}"
        if whitelist:
            cfg += f" -c tessedit_char_whitelist={whitelist}"
        lang = lang or self.lang
        if lang not in self.languages() and "+" not in lang:
            lang = "eng"
        try:
            d = self._pt.image_to_data(img, lang=lang, config=cfg, output_type=self._pt.Output.DICT)
        except Exception as exc:  # noqa: BLE001
            log.warning("OCR failure: %s", exc)
            return "", 0.0
        words, confs = [], []
        for t, c in zip(d["text"], d["conf"]):
            t = str(t).strip()
            if t:
                words.append(t)
                try:
                    c = float(c)
                except (TypeError, ValueError):
                    c = -1
                if c >= 0:
                    confs.append(c / 100.0)
        return " ".join(words), float(np.mean(confs)) if confs else 0.0


_BACKENDS: dict[str, type[OCRBackend]] = {"tesseract": TesseractBackend, "none": OCRBackend}
_CACHE: dict[tuple, OCRBackend] = {}


def register_backend(name: str, cls: type[OCRBackend]) -> None:
    """Register an alternative OCR engine (e.g. EasyOCR wrapper)."""
    _BACKENDS[name] = cls


def get_backend(name: str = "tesseract", lang: str = "eng") -> OCRBackend:
    key = (name, lang)
    if key not in _CACHE:
        cls = _BACKENDS.get(name, OCRBackend)
        _CACHE[key] = cls(lang) if cls is TesseractBackend else cls()
    return _CACHE[key]


def ocr_status(lang: str = "eng") -> dict:
    be = get_backend("tesseract", lang)
    info = {"available": be.available, "languages": [], "version": None, "hint": "" if be.available else INSTALL_HINT}
    if be.available:
        info["languages"] = be.languages()
        try:
            info["version"] = str(be._pt.get_tesseract_version())
        except Exception:  # noqa: BLE001
            pass
    return info


# ----------------------------------------------------------------- helpers
def _prep(gray: np.ndarray, target_h: int = 44, pad: int = 10) -> np.ndarray:
    if gray.ndim == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape[:2]
    f = max(1.0, target_h / max(h, 1))
    if f > 1.01:
        gray = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
    if gray.mean() < 110:
        gray = 255 - gray
    return cv2.copyMakeBorder(gray, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=255)


def _components(gray: np.ndarray):
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _, st, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    comps = [tuple(int(v) for v in st[i][:4]) for i in range(1, n) if st[i][4] >= 3]
    return sorted(comps, key=lambda c: c[0]), bw


_NUM_RE = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")


def parse_number(text: str) -> float | None:
    t = (text or "").strip().replace(" ", "")
    t = t.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", "-").replace("~", "-")
    if re.fullmatch(r"[+-]?\d{1,3}(,\d{3})+(\.\d+)?", t):
        t = t.replace(",", "")
    else:
        t = t.replace(",", ".")
    t = t.rstrip(".")
    if _NUM_RE.match(t):
        try:
            return float(t)
        except ValueError:
            return None
    return None


def _leading_minus(comps, digit_h: float) -> bool:
    """True if the first component is a short, wide dash located mid-height of the digits."""
    if not comps:
        return False
    x, y, w, h = comps[0]
    return h <= 0.28 * digit_h and w >= 1.4 * h and w <= 1.2 * digit_h


def read_number(gray_crop: np.ndarray, backend: OCRBackend, allow_power10: bool = True) -> OCRNumber:
    """Read one numeric tick label from a tight crop."""
    if gray_crop.size == 0 or not backend.available:
        return OCRNumber(None, "", 0.0)
    g = _prep(gray_crop)
    comps, _ = _components(g)
    if not comps:
        return OCRNumber(None, "", 0.0)
    digit_h = float(np.median([c[3] for c in comps if c[3] > 0.5 * max(c[3] for c in comps)]))
    # ---- superscript power of ten: leading "1","0" followed by smaller raised glyphs
    if allow_power10 and len(comps) >= 3:
        tall = [c for c in comps if c[3] >= 0.8 * digit_h]
        small = [c for c in comps if c[3] < 0.84 * digit_h]
        if len(tall) >= 2 and small:
            base_bottom = np.median([c[1] + c[3] for c in tall[:2]])
            raised = [c for c in small if c[0] > tall[1][0] and (c[1] + c[3]) < base_bottom - 0.25 * digit_h]
            if raised:
                x0 = min(c[0] for c in raised)
                x1 = max(c[0] + c[2] for c in raised)
                y0 = min(c[1] for c in raised)
                y1 = max(c[1] + c[3] for c in raised)
                head = g[:, : max(tall[1][0] + tall[1][2] + 2, 1)]
                head_txt, hc = backend.read(head, 8, "0123456789")
                exp_img = g[max(y0 - 3, 0): y1 + 3, max(x0 - 3, 0): x1 + 3]
                exp_img = _prep(exp_img, 40, 8)
                et, ec = backend.read(exp_img, 8, "0123456789-")
                et = et.replace(" ", "")
                ecomps, _ = _components(exp_img)
                if ecomps and not et.startswith("-"):
                    eh = float(max(c[3] for c in ecomps))
                    if len(ecomps) >= 2 and _leading_minus(ecomps, eh):
                        et = "-" + et
                if head_txt.replace(" ", "").startswith("10") and re.fullmatch(r"-?\d{1,3}", et or ""):
                    return OCRNumber(10.0 ** int(et), f"10^{int(et)}", float(np.mean([hc, ec])), True)
    txt, conf = backend.read(g, 10 if len(comps) == 1 else 7, "0123456789.,-+eE")
    raw = txt.replace(" ", "")
    if comps and _leading_minus(comps, digit_h) and not raw.startswith(("-", "+")):
        raw = "-" + raw
    # drop a stray leading dash when OCR produced one that the geometry does not support
    val = parse_number(raw)
    if val is None and raw.endswith("-"):
        val = parse_number(raw[:-1])
    if val is None:                                    # retry for blurry / tiny glyphs
        big = cv2.resize(gray_crop if gray_crop.ndim == 2 else cv2.cvtColor(gray_crop, cv2.COLOR_RGB2GRAY),
                         None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        big = cv2.GaussianBlur(big, (0, 0), 1.6)
        _, bw = cv2.threshold(big, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        if bw.mean() < 127:
            bw = 255 - bw
        bw = cv2.copyMakeBorder(bw, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)
        for psm in (8, 7, 13):
            t2, c2 = backend.read(bw, psm, "0123456789.,-+eE")
            v2 = parse_number(t2.replace(" ", ""))
            if v2 is not None:
                return OCRNumber(v2, t2.replace(" ", ""), min(c2, 0.5))
    return OCRNumber(val, raw, conf)


def read_text(img: np.ndarray, backend: OCRBackend, psm: int = 7, lang: str | None = None,
              target_h: int = 48) -> tuple[str, float]:
    if img.size == 0 or not backend.available:
        return "", 0.0
    g = _prep(img, target_h)
    txt, conf = backend.read(g, psm, None, lang)
    return txt.strip(), conf
