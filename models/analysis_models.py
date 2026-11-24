"""Dataclasses for analysis results (curve fits etc.)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .data_models import to_jsonable


@dataclass
class FitResult:
    name: str                       # e.g. "Exponential"
    family: str                     # key in the model library
    n_params: int
    params: dict                    # {"a": {"value":..,"stderr":..,"ci_low":..,"ci_high":..}}
    equation: dict                  # {"text","latex","python","excel"}
    metrics: dict                   # r2, adj_r2, rmse, mae, mse, mape, sse, aic, bic, aicc, cv_rmse
    residuals: dict = field(default_factory=dict)
    valid_range: tuple = (0.0, 0.0)
    n_points: int = 0
    method: str = ""
    converged: bool = True
    warnings: list = field(default_factory=list)
    x_fit: list = field(default_factory=list)
    y_fit: list = field(default_factory=list)
    source: str = "statistical fit"

    def to_dict(self):
        return to_jsonable(dict(name=self.name, family=self.family, n_params=self.n_params, params=self.params,
                                equation=self.equation, metrics=self.metrics, residuals=self.residuals,
                                valid_range=list(self.valid_range), n_points=self.n_points, method=self.method,
                                converged=self.converged, warnings=self.warnings, x_fit=self.x_fit,
                                y_fit=self.y_fit, source=self.source))
