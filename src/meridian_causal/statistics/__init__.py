"""Gaussian conditional-independence evidence without silent regularization."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import atanh, erfc, sqrt
import json

import numpy as np


class InvalidTest(ValueError):
    """A statistical test cannot be interpreted on these observations."""


def _indices(data, x, y, conditioned):
    values = np.asarray(data, dtype=float)
    if values.ndim != 2 or values.shape[0] < 2:
        raise InvalidTest("Expected a matrix with at least two rows")
    conditioned = tuple(conditioned)
    indices = (x, y) + conditioned
    if any(not isinstance(i, (int, np.integer)) or not 0 <= i < values.shape[1] for i in indices):
        raise InvalidTest("Invalid column index")
    if len(set(indices)) != len(indices):
        raise InvalidTest("Tested variables and conditioning columns must be distinct")
    selected = values[:, indices]
    if not np.isfinite(selected).all():
        raise InvalidTest("Missing or nonfinite observations")
    return selected, conditioned


def partial_correlation(data, x, y, conditioned=(), condition_limit=1e12):
    """Pearson correlation of OLS residuals, using centered unit-norm columns.

    Scaling is only numerical: partial correlation is invariant to nonzero
    column rescaling. SVD checks explicitly reject ill-conditioned systems;
    neither ridge regularization nor a pseudoinverse fallback is used.
    """
    if not np.isfinite(condition_limit) or condition_limit <= 1:
        raise InvalidTest("Condition limit must be finite and greater than one")
    selected, conditioned = _indices(data, x, y, conditioned)
    centered = selected - selected.mean(axis=0)
    norms = np.linalg.norm(centered, axis=0)
    if np.any(norms == 0) or not np.isfinite(norms).all():
        raise InvalidTest("Constant column or unrepresentable scale")
    scaled = centered / norms
    singular_values = np.linalg.svd(scaled, compute_uv=False)
    if (len(singular_values) < scaled.shape[1]
            or singular_values[-1] <= singular_values[0] / condition_limit):
        raise InvalidTest("Singular or nearly dependent tested columns (condition limit exceeded)")
    residual = scaled[:, :2]
    if conditioned:
        design = scaled[:, 2:]
        # Full rank was checked on the joint system above.
        coefficient = np.linalg.lstsq(design, residual, rcond=None)[0]
        residual = residual - design @ coefficient
    a, b = residual[:, 0], residual[:, 1]
    denominator = np.linalg.norm(a) * np.linalg.norm(b)
    if denominator <= 0 or not np.isfinite(denominator):
        raise InvalidTest("Zero or invalid residual variance")
    correlation = float(np.dot(a, b) / denominator)
    if not np.isfinite(correlation) or abs(correlation) > 1 + 1e-12:
        raise InvalidTest("Partial correlation outside numerical tolerance")
    # Roundoff can place a mathematically valid value just beyond ±1. The
    # joint rank check already rejected deterministic linear relationships.
    return float(np.clip(correlation, -1 + np.finfo(float).eps, 1 - np.finfo(float).eps))


@dataclass(frozen=True)
class FisherZResult:
    valid: bool
    correlation: float | None
    statistic: float | None
    p_value: float | None
    degrees_of_freedom: int
    reason: str | None = None

    def to_dict(self):
        return asdict(self)


def fisher_z(data, x, y, conditioned=(), condition_limit=1e12):
    """Two-sided Gaussian Fisher Z: sqrt(n - |S| - 3) * atanh(r)."""
    conditioned = tuple(conditioned)
    values = np.asarray(data, dtype=float)
    dof = (values.shape[0] if values.ndim == 2 else 0) - len(conditioned) - 3
    try:
        if dof <= 0:
            raise InvalidTest("Insufficient rows: Fisher Z requires n > |S| + 3")
        correlation = partial_correlation(values, x, y, conditioned, condition_limit)
        statistic = sqrt(dof) * abs(atanh(correlation))
        p_value = erfc(statistic / sqrt(2))
        return FisherZResult(True, correlation, statistic, p_value, dof)
    except (InvalidTest, np.linalg.LinAlgError) as error:
        return FisherZResult(False, None, None, None, dof, str(error))


class CITestCache:
    """A bounded, dataset-scoped cache immune to mutation of its source array.

    Identity includes bytes, dimensions, stable IDs, preprocessing metadata and
    test configuration. Reuse between datasets requires a new cache instance.
    """
    def __init__(self, data, nodes, *, preprocessing=None, condition_limit=1e12, max_entries=10000):
        self.data = np.array(data, dtype=float, order="C", copy=True)
        self.nodes = tuple(nodes)
        if self.data.ndim != 2 or self.data.shape[1] != len(self.nodes):
            raise ValueError("Data columns must match variable IDs")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("Duplicate variable IDs")
        if max_entries < 1 or not np.isfinite(condition_limit) or condition_limit <= 1:
            raise ValueError("Invalid cache or conditioning limit")
        self.data.flags.writeable = False
        self.condition_limit, self.max_entries = condition_limit, max_entries
        descriptor = {"nodes": self.nodes, "shape": self.data.shape, "preprocessing": preprocessing,
                      "condition_limit": condition_limit, "test": "fisher-z-v1"}
        self.dataset_id = sha256(self.data.tobytes() + json.dumps(descriptor, sort_keys=True).encode()).hexdigest()
        self._cache = {}
        self.hits = 0
        self.calculations = 0

    def test(self, x, y, conditioned=()):
        conditioned = tuple(sorted(conditioned))
        key = (tuple(sorted((x, y))), conditioned)
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        try:
            indices = [self.nodes.index(n) for n in (x, y) + conditioned]
        except ValueError as error:
            raise ValueError("Unknown variable in statistical query") from error
        result = fisher_z(self.data, indices[0], indices[1], indices[2:], self.condition_limit)
        self.calculations += 1
        if len(self._cache) >= self.max_entries:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = result
        return result


def data_diagnostics(data, nodes=None):
    """JSON-safe diagnostics. These never modify, impute or drop observations."""
    values = np.asarray(data, dtype=float)
    if values.ndim != 2:
        raise ValueError("Expected rows by columns matrix")
    n, p = values.shape
    names = list(nodes) if nodes is not None else [str(i) for i in range(p)]
    if len(names) != p:
        raise ValueError("Column ID count mismatch")
    finite = np.isfinite(values)
    result = {"rows": n, "columns": p, "missing": int(np.isnan(values).sum()),
              "nonfinite": int((~finite).sum()), "constant_columns": [],
              "near_dependent": False, "condition_number": None, "scales": [], "valid": True}
    if not finite.all() or n < 2 or p < 1:
        result["valid"] = False
        return result
    scales = np.std(values, axis=0, ddof=1)
    result["scales"] = scales.tolist()
    result["constant_columns"] = [names[i] for i in np.flatnonzero(scales == 0)]
    if result["constant_columns"]:
        result["valid"] = False
        return result
    standardized = (values - values.mean(axis=0)) / scales
    condition = float(np.linalg.cond(standardized))
    result["condition_number"] = condition if np.isfinite(condition) else None
    result["near_dependent"] = bool(not np.isfinite(condition) or condition > 1e12 or n <= p)
    result["valid"] = not result["near_dependent"]
    return result
