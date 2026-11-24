"""Safe image loading (PNG/JPG/TIFF/BMP/WEBP/SVG/PDF) with validation."""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from config import constants as C
from config.logging_config import get_logger

log = get_logger("loader")

_MAGIC = {
    ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8"], ".jpeg": [b"\xff\xd8"],
    ".tif": [b"II*\x00", b"MM\x00*"], ".tiff": [b"II*\x00", b"MM\x00*"],
    ".bmp": [b"BM"], ".webp": [b"RIFF"], ".pdf": [b"%PDF"],
}


class ImageLoadError(Exception):
    """Raised with a user-readable message when a file cannot be loaded."""


@dataclass
class LoadedImage:
    rgb: np.ndarray                      # H x W x 3 uint8
    name: str
    fmt: str
    width: int
    height: int
    dpi: tuple | None = None
    source_path: str | None = None
    meta: dict = field(default_factory=dict)


def validate_file(name: str, data: bytes) -> str:
    """Validate extension, size and magic bytes; return the lower-case extension. Files are never executed."""
    ext = Path(name).suffix.lower()
    if ext not in C.SUPPORTED_EXT:
        raise ImageLoadError(f"Unsupported file type '{ext}'. Supported: {', '.join(C.SUPPORTED_EXT)}")
    if len(data) == 0:
        raise ImageLoadError("The file is empty.")
    if len(data) > C.MAX_FILE_MB * 1024 * 1024:
        raise ImageLoadError(f"File is larger than {C.MAX_FILE_MB} MB.")
    if ext in _MAGIC and not any(data.startswith(m) for m in _MAGIC[ext]):
        raise ImageLoadError(f"The content of '{name}' does not look like a valid {ext} file.")
    if ext == ".svg" and b"<svg" not in data[:4096].lower() and b"<svg" not in data.lower():
        raise ImageLoadError("The file does not look like a valid SVG.")
    return ext


def _flatten_alpha(im: Image.Image) -> Image.Image:
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg.convert("RGB")
    return im.convert("RGB")


def _render_svg(data: bytes, scale: float = 3.0) -> np.ndarray:
    try:
        import cairosvg  # type: ignore
        png = cairosvg.svg2png(bytestring=data, scale=scale, background_color="white")
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    except ImportError:
        pass
    try:  # secondary option: svglib + reportlab
        from svglib.svglib import svg2rlg  # type: ignore
        from reportlab.graphics import renderPM
        drawing = svg2rlg(io.BytesIO(data))
        png = renderPM.drawToString(drawing, fmt="PNG", dpi=72 * scale)
        return np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
    except Exception as exc:  # noqa: BLE001
        raise ImageLoadError(
            "SVG rendering needs the optional package 'cairosvg' (pip install cairosvg) or 'svglib'. "
            f"Alternatively export the figure as PNG/PDF. Details: {exc}") from exc


def load_image_bytes(data: bytes, name: str, pdf_page: int = 0, pdf_scale: float = 3.0) -> LoadedImage:
    ext = validate_file(name, data)
    dpi = None
    if ext == ".pdf":
        from .pdf_processor import render_pdf_page_bytes
        rgb = render_pdf_page_bytes(data, pdf_page, pdf_scale)
    elif ext == ".svg":
        rgb = _render_svg(data)
    else:
        try:
            im = Image.open(io.BytesIO(data))
            dpi = im.info.get("dpi")
            im.seek(0)
            im = ImageOps.exif_transpose(im)
            rgb = np.asarray(_flatten_alpha(im))
        except Exception as exc:  # noqa: BLE001
            raise ImageLoadError(f"Could not decode '{name}': {exc}") from exc
    h, w = rgb.shape[:2]
    log.info("Loaded %s (%dx%d)", name, w, h)
    return LoadedImage(rgb=np.ascontiguousarray(rgb), name=Path(name).name, fmt=ext.lstrip(".").upper(),
                       width=w, height=h, dpi=tuple(dpi) if dpi else None)


def load_image(path: str | Path, pdf_page: int = 0, pdf_scale: float = 3.0) -> LoadedImage:
    path = Path(path)
    if not path.exists():
        raise ImageLoadError(f"File not found: {path}")
    li = load_image_bytes(path.read_bytes(), path.name, pdf_page, pdf_scale)
    li.source_path = str(path)
    return li
