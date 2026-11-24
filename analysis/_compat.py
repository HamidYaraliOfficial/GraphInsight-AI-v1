"""Small compatibility helpers so that the code runs on NumPy 1.x (Python 3.8+) and NumPy 2.x."""
from __future__ import annotations

import numpy as np

# numpy.trapezoid exists from NumPy 2.0; numpy.trapz was removed in later 2.x releases
trapezoid = getattr(np, "trapezoid", None) or getattr(np, "trapz")


def first(result):
    """First element (statistic / correlation) of a scipy.stats result (tuple-like in every SciPy version)."""
    return float(result[0])


def second(result):
    """Second element (p-value) of a scipy.stats result."""
    return float(result[1])
