"""Image pre-processing: scaling, denoising, de-skewing, contrast / background correction."""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from config import constants as C
from config.logging_config import get_logger

log = get_logger("preprocess")


@dataclass
class PreprocessResult:
    original: np.ndarray
    processed: np.ndarray
    scale: float = 1.0
    rotation_deg: float = 0.0
    noise_sigma: float = 0.0
    steps: list = field(default_factory=list)
    warnings: list = field(default_factory=list)

    @property
    def gray(self) -> np.ndarray:
        return cv2.cvtColor(self.processed, cv2.COLOR_RGB2GRAY)


def estimate_noise(gray: np.ndarray) -> float:
    """Immerkaer fast noise sigma estimate."""
    g = gray.astype(np.float32)
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], np.float32)
    conv = cv2.filter2D(g, -1, k)
    h, w = g.shape
    return float(np.sqrt(np.pi / 2) * np.abs(conv[1:-1, 1:-1]).sum() / (6.0 * (w - 2) * (h - 2)))


def estimate_skew(gray: np.ndarray, max_angle: float = 4.0) -> float:
    """Skew angle (deg) by maximising the sharpness of the projection profiles of the dark pixels
    (axes are long straight lines, so the correct angle makes them razor sharp)."""
    h, w = gray.shape
    f = 900.0 / max(h, w)
    small = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else gray
    small = cv2.GaussianBlur(small, (3, 3), 0)
    thr = min(150, float(np.percentile(small, 8)) + 40)
    mask = (small < thr).astype(np.float32)
    if mask.sum() < 50:
        return 0.0
    hh, ww = mask.shape

    def score(angle: float) -> float:
        m = cv2.getRotationMatrix2D((ww / 2, hh / 2), angle, 1.0)
        r = cv2.warpAffine(mask, m, (ww, hh), flags=cv2.INTER_LINEAR)
        return float(np.var(r.sum(axis=1)) + np.var(r.sum(axis=0)))

    coarse = np.arange(-max_angle, max_angle + 1e-6, 0.25)
    sc = [score(a) for a in coarse]
    best = float(coarse[int(np.argmax(sc))])
    fine = np.arange(best - 0.25, best + 0.2501, 0.05)
    sf = [score(a) for a in fine]
    best = float(fine[int(np.argmax(sf))])
    s0 = score(0.0)
    if abs(best) < 0.2 or max(sf) < 1.03 * s0:
        return 0.0
    return -best if False else best


def rotate_bound(img: np.ndarray, angle: float) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - w / 2
    m[1, 2] += nh / 2 - h / 2
    return cv2.warpAffine(img, m, (nw, nh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                          borderValue=(255, 255, 255))


def flatten_background(rgb: np.ndarray) -> np.ndarray:
    """Divide by a large-scale background estimate (fixes uneven scan illumination)."""
    bg = cv2.medianBlur(cv2.resize(rgb, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA), 31)
    bg = cv2.resize(bg, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_LINEAR)
    out = rgb.astype(np.float32) / np.maximum(bg.astype(np.float32), 1) * 255.0
    return np.clip(out, 0, 255).astype(np.uint8)


def preprocess(rgb: np.ndarray, denoise=True, deskew=True, enhance=True, upscale_small=True,
               manual_rotation: float = 0.0) -> PreprocessResult:
    res = PreprocessResult(original=rgb, processed=rgb.copy())
    img = rgb.copy()
    h, w = img.shape[:2]

    # 1. scale
    longest = max(h, w)
    if longest > C.MAX_IMAGE_SIDE:
        f = C.MAX_IMAGE_SIDE / longest
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)
        res.scale *= f
        res.steps.append(f"downscaled x{f:.3f} (image larger than {C.MAX_IMAGE_SIDE}px)")
    elif upscale_small and longest < 1100:
        f = min(3.0, max(1.5, 1400 / longest))
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_CUBIC)
        res.scale *= f
        res.steps.append(f"upscaled x{f:.2f} (low resolution input)")
        res.warnings.append("Low-resolution image: accuracy is limited by the original pixel grid.")

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    # 2. noise
    sigma = estimate_noise(gray)
    res.noise_sigma = sigma
    if denoise and sigma > 2.0:
        if sigma > 6.0:
            img = cv2.fastNlMeansDenoisingColored(img, None, 5, 5, 5, 15)
            res.steps.append(f"non-local-means denoising (sigma~{sigma:.1f})")
        else:
            img = cv2.bilateralFilter(img, 5, 20, 20)
            res.steps.append(f"bilateral denoising (sigma~{sigma:.1f})")
    # 3. background / contrast
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    if enhance:
        if np.percentile(gray, 90) < 215 and np.percentile(gray, 90) > 120:   # grey / uneven paper background
            img = flatten_background(img)
            res.steps.append("background flattening")
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        span = float(np.percentile(gray, 99) - np.percentile(gray, 1))
        if span < 150:
            lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            lab[:, :, 0] = clahe.apply(lab[:, :, 0])
            img = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            res.steps.append(f"CLAHE contrast enhancement (dynamic range {span:.0f})")
    # 4. rotation
    angle = manual_rotation
    if deskew and manual_rotation == 0.0:
        angle = estimate_skew(cv2.cvtColor(img, cv2.COLOR_RGB2GRAY))
    if abs(angle) > 0.25:
        img = rotate_bound(img, angle)
        res.rotation_deg = float(angle)
        res.steps.append(f"rotated by {angle:.2f} deg (skew correction)")
    res.processed = img
    log.info("Preprocess: %s", "; ".join(res.steps) or "no change")
    return res
