"""Small, validated linear SCMs; no matrix inverses or latent-variable claims."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from itertools import combinations
import copy
import time

import numpy as np

from meridian_causal.graphs import Graph, d_separated
from meridian_causal.serialization import validate_json_tree


MAX_VARIABLES = 15


def _array(value, shape, label):
    # Check sequence dimensions before conversion, including imported JSON.
    if isinstance(value, np.ndarray):
        if value.shape != shape:
            raise ValueError(f"{label} must have shape {shape}.")
    else:
        if not isinstance(value, (list, tuple)) or len(value) != shape[0]:
            raise ValueError(f"{label} must have shape {shape}.")
        if len(shape) == 2 and any(not isinstance(row, (list, tuple, np.ndarray)) or len(row) != shape[1] for row in value):
            raise ValueError(f"{label} must have shape {shape}.")
        scalars=(element for row in value for element in row) if len(shape)==2 else iter(value)
        if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) for v in scalars):
            raise ValueError(f'{label} must contain real numerical values, without booleans or strings.')
    try:
        raw = np.asarray(value)
        if raw.dtype.kind not in 'iuf':
            raise ValueError('Only real numeric values are supported.')
        result = np.array(raw, dtype=float, copy=True)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must contain numerical values.") from exc
    if result.shape != shape or not np.isfinite(result).all():
        raise ValueError(f"{label} must have shape {shape} and finite values.")
    result.setflags(write=False)
    return result


def _data(value, d, *, min_rows=1):
    result = np.asarray(value, dtype=float)
    if result.ndim != 2 or result.shape[1] != d or result.shape[0] < min_rows:
        raise ValueError(f"Data must have {d} columns and at least {min_rows} rows.")
    if result.shape[0] > 1_000_000 or not np.isfinite(result).all():
        raise ValueError("Data must be finite and contain at most 1,000,000 rows.")
    return result


@dataclass(frozen=True, eq=False)
class LinearSCM:
    nodes: tuple[str, ...]
    B: np.ndarray
    intercept: np.ndarray
    noise_variances: np.ndarray
    provenance: str = "user-specified"
    fit_metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.nodes, (list, tuple)) or not 1 <= len(self.nodes) <= MAX_VARIABLES:
            raise ValueError(f"A model must contain 1–{MAX_VARIABLES} variable IDs.")
        nodes = tuple(self.nodes)
        if any(not isinstance(node, str) or not node or len(node) > 200 for node in nodes) or len(set(nodes)) != len(nodes):
            raise ValueError("Variable IDs must be unique nonempty strings of at most 200 characters.")
        if not isinstance(self.provenance, str) or not self.provenance or len(self.provenance)>200:
            raise ValueError("Model provenance must be a nonempty string.")
        d = len(nodes)
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "B", _array(self.B, (d, d), "B"))
        object.__setattr__(self, "intercept", _array(self.intercept, (d,), "intercept"))
        object.__setattr__(self, "noise_variances", _array(self.noise_variances, (d,), "noise_variances"))
        if np.any(np.diag(self.B) != 0):
            raise ValueError("Structural self-loops are not allowed; B must have a zero diagonal.")
        if np.any(self.noise_variances <= 0):
            raise ValueError("Every structural noise variance must be strictly positive.")
        if not isinstance(self.fit_metadata, dict):
            raise ValueError("fit_metadata must be an object.")
        object.__setattr__(self, "fit_metadata", copy.deepcopy(validate_json_tree(self.fit_metadata)))
        if not self.graph.is_dag():
            raise ValueError("A structural causal model must be an acyclic directed graph.")

    @property
    def graph(self):
        support=Graph(self.nodes, directed=[(self.nodes[p], self.nodes[c]) for c, p in zip(*np.nonzero(self.B))])
        if 'fitted_graph' in self.fit_metadata:
            graph=Graph.from_dict(self.fit_metadata['fitted_graph'])
            if (tuple(graph.nodes)!=self.nodes or not graph.is_dag() or
                not support.directed<=graph.directed):
                raise ValueError('Fitted graph must be a DAG containing every nonzero coefficient with matching IDs.')
            return graph
        return support

    def _values(self, values):
        if values is None:
            values = {}
        if not isinstance(values, Mapping):
            raise ValueError("Interventions and conditioning values must map variable IDs to numbers.")
        result = {}
        for node, value in values.items():
            if node not in self.nodes:
                raise ValueError(f"Unknown variable ID: {node!r}.")
            if isinstance(value, (bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)):
                raise ValueError("Intervention and conditioning values must be finite real numbers.")
            try:
                value = float(value)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("Intervention and conditioning values must be finite real numbers.") from exc
            if not np.isfinite(value):
                raise ValueError("Intervention and conditioning values must be finite real numbers.")
            result[node] = value
        return result

    def moments(self, interventions=None):
        """Return original-unit means/covariance after replacing clamped equations."""
        values = self._values(interventions)
        fixed = [i for i, node in enumerate(self.nodes) if node in values]
        free = [i for i, node in enumerate(self.nodes) if node not in values]
        mean = np.zeros(len(self.nodes))
        covariance = np.zeros((len(self.nodes), len(self.nodes)))
        mean[fixed] = [values[self.nodes[i]] for i in fixed]
        if free:
            system = np.eye(len(free)) - self.B[np.ix_(free, free)]
            rhs = self.intercept[free] + self.B[np.ix_(free, fixed)] @ mean[fixed]
            mean[free] = np.linalg.solve(system, rhs)
            # Solving against the noise square root directly preserves PSD.
            propagated = np.linalg.solve(system, np.diag(np.sqrt(self.noise_variances[free])))
            covariance[np.ix_(free, free)] = propagated @ propagated.T
        if not np.isfinite(mean).all() or not np.isfinite(covariance).all():
            raise ValueError("Model moments overflowed; reduce coefficient or noise magnitudes.")
        return mean, covariance

    def condition(self, values):
        """Gaussian observation conditioning, separate from causal intervention."""
        values = self._values(values)
        mean, covariance = self.moments()
        fixed = [i for i, node in enumerate(self.nodes) if node in values]
        free = [i for i, node in enumerate(self.nodes) if node not in values]
        if not fixed:
            return mean, covariance
        observed = np.array([values[self.nodes[i]] for i in fixed])
        new_mean, new_covariance = mean.copy(), np.zeros_like(covariance)
        new_mean[fixed] = observed
        if free:
            block = covariance[np.ix_(fixed, fixed)]
            if np.linalg.cond(block) > 1e12:
                raise ValueError("Conditioning covariance is ill-conditioned; rescale variables or revise the model.")
            cross = covariance[np.ix_(free, fixed)]
            new_mean[free] += cross @ np.linalg.solve(block, observed - mean[fixed])
            conditional = covariance[np.ix_(free, free)] - cross @ np.linalg.solve(block, cross.T)
            conditional = (conditional + conditional.T) / 2
            if np.min(np.linalg.eigvalsh(conditional)) < -1e-10 * max(1., np.max(np.diag(covariance))):
                raise ValueError("Numerically invalid conditional covariance.")
            # Only numerical roundoff on the diagonal is clamped; no regularization.
            conditional[np.diag_indices_from(conditional)] = np.maximum(np.diag(conditional), 0)
            new_covariance[np.ix_(free, free)] = conditional
        if not np.isfinite(new_mean).all() or not np.isfinite(new_covariance).all():
            raise ValueError('Conditional moments overflowed; revise variable scales or values.')
        return new_mean, new_covariance

    def simulate(self, n, seed, interventions=None):
        """Independent seeded draws using topological structural equations."""
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or not 1 <= n <= 1_000_000:
            raise ValueError("Sample count must be an integer between 1 and 1,000,000.")
        if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
            raise ValueError("Seed must be a nonnegative integer.")
        values = self._values(interventions)
        rng = np.random.default_rng(seed)
        noise = rng.normal(size=(n, len(self.nodes))) * np.sqrt(self.noise_variances)
        rows = np.zeros_like(noise)
        for node in self.graph.topological_order():
            i = self.nodes.index(node)
            rows[:, i] = values[node] if node in values else self.intercept[i] + rows @ self.B[i] + noise[:, i]
        if not np.isfinite(rows).all():
            raise ValueError("Simulation overflowed; reduce coefficient or noise magnitudes.")
        return rows

    def residuals(self, row):
        row = _array(row, (len(self.nodes),), "factual observation")
        result=row - self.intercept - self.B @ row
        if not np.isfinite(result).all():
            raise ValueError('Residual abduction overflowed; revise model or observation magnitudes.')
        return result

    def counterfactual(self, row, interventions):
        """Abduct residuals for this model, replace equations, reuse those residuals."""
        row = _array(row, (len(self.nodes),), "factual observation")
        values = self._values(interventions)
        residuals = self.residuals(row)
        result = np.zeros(len(self.nodes))
        for node in self.graph.topological_order():
            i = self.nodes.index(node)
            result[i] = values[node] if node in values else self.intercept[i] + self.B[i] @ result + residuals[i]
        if not np.isfinite(result).all():
            raise ValueError("Counterfactual overflowed; revise model magnitudes.")
        return result

    def total_effects(self):
        """Effect[child,treatment], including unit diagonal, summed over all paths."""
        effects = np.linalg.solve(np.eye(len(self.nodes)) - self.B, np.eye(len(self.nodes)))
        if not np.isfinite(effects).all():
            raise ValueError("Total effects overflowed.")
        return effects

    def to_original_units(self, center, scale):
        """Convert an SCM for z=(x-center)/scale into an SCM for x."""
        d = len(self.nodes)
        center, scale = _array(center, (d,), "center"), _array(scale, (d,), "scale")
        if np.any(scale <= 0):
            raise ValueError("Preprocessing scales must be strictly positive.")
        B = self.B * scale[:, None] / scale[None, :]
        intercept = center + scale * self.intercept - B @ center
        metadata = copy.deepcopy(self.fit_metadata)
        metadata["original_unit_transform"] = {"center": center.tolist(), "scale": scale.tolist()}
        return LinearSCM(self.nodes, B, intercept, self.noise_variances * scale**2, self.provenance, metadata)

    def to_dict(self):
        return {"nodes": list(self.nodes), "B": self.B.tolist(), "intercept": self.intercept.tolist(),
                "noise_variances": self.noise_variances.tolist(), "provenance": self.provenance,
                "fit_metadata": copy.deepcopy(self.fit_metadata), "matrix_convention": "B[child,parent]"}

    @classmethod
    def from_dict(cls, payload):
        if not isinstance(payload, dict) or not all(k in payload for k in ("nodes", "B", "intercept", "noise_variances")):
            raise ValueError("A serialized model requires nodes, B, intercept and noise_variances.")
        if payload.get("matrix_convention", "B[child,parent]") != "B[child,parent]":
            raise ValueError("Unsupported structural coefficient convention.")
        return cls(payload["nodes"], payload["B"], payload["intercept"], payload["noise_variances"],
                   payload.get("provenance", "user-specified"), payload.get("fit_metadata", {}))


def fit_scm(data, graph, *, condition_limit=1e10, variance_floor_relative=1e-12):
    """OLS with intercept, scaled rank diagnostics, ML residual variance RSS/n.

    A recorded floor of ``variance_floor_relative * marginal_variance`` is used
    only for tiny residual variances. It is never used to repair deficient rank.
    """
    if not isinstance(graph, Graph) or not graph.is_dag():
        raise ValueError("Select a valid directed acyclic graph before fitting an SCM.")
    if not np.isfinite(condition_limit) or condition_limit <= 1:
        raise ValueError("condition_limit must be finite and greater than 1.")
    if not np.isfinite(variance_floor_relative) or not 0 <= variance_floor_relative < 1:
        raise ValueError("variance_floor_relative must lie in [0,1).")
    nodes, d = tuple(graph.nodes), len(graph.nodes)
    X = _data(data, d, min_rows=3)
    n = len(X)
    marginal_variances = np.var(X, axis=0)
    if not np.isfinite(marginal_variances).all() or np.any(marginal_variances <= 0):
        raise ValueError("Constant or numerically overflowing columns cannot be fitted as positive-noise SCMs.")
    B, intercept, variances, diagnostics = np.zeros((d, d)), np.zeros(d), np.zeros(d), []
    for node in nodes:
        i = nodes.index(node)
        parents = sorted([nodes.index(parent) for parent in graph.parents(node)])
        if n <= len(parents) + 1:
            raise ValueError(f"Not enough observations to fit {node} with an intercept and its parents.")
        center = np.mean(X[:, parents], axis=0)
        scale = np.std(X[:, parents], axis=0)
        design = np.column_stack([np.ones(n), (X[:, parents] - center) / scale])
        coefficients, _, rank, singular = np.linalg.lstsq(design, X[:, i], rcond=None)
        condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else float("inf")
        if rank < design.shape[1] or condition > condition_limit:
            raise ValueError(f"Parent design for {node} is rank deficient or ill-conditioned (condition={condition:.3g}).")
        B[i, parents] = coefficients[1:] / scale
        intercept[i] = coefficients[0] - B[i, parents] @ center
        residual = X[:, i] - design @ coefficients
        raw_variance = float(residual @ residual / n)
        floor = float(variance_floor_relative * marginal_variances[i])
        variances[i] = max(raw_variance, floor)
        if variances[i] <= 0:
            raise ValueError(f"Residual variance for {node} is zero; revise the model or explicitly enable the variance floor.")
        diagnostics.append({"variable": node, "parents": [nodes[j] for j in parents], "rank": int(rank),
                            "condition": condition, "residual_variance_raw": raw_variance,
                            "variance_floor": floor, "variance_floored": bool(raw_variance < floor)})
    return LinearSCM(nodes, B, intercept, variances, "observational-OLS-fit",
                     {"estimator": "OLS with intercept; residual variance RSS/n (maximum likelihood)",
                      "fitted_graph": graph.to_dict(),
                      "n": n, "condition_limit": condition_limit, "variance_floor_relative": variance_floor_relative,
                      "parent_design_scaling": "centered and scaled for solving; coefficients returned in original units",
                      "diagnostics": diagnostics})


def check_backdoor(graph, treatment, outcome, adjustment):
    """Check Pearl's sufficient backdoor criterion for a supplied observed DAG."""
    if not isinstance(graph, Graph) or not graph.is_dag():
        raise ValueError("Backdoor checking requires a directed acyclic graph.")
    if treatment not in graph.nodes or outcome not in graph.nodes or treatment == outcome:
        raise ValueError("Treatment and outcome must be distinct graph variable IDs.")
    if isinstance(adjustment, str):
        raise ValueError("Adjustment must be a collection of variable IDs.")
    adjustment = list(adjustment)
    if len(set(adjustment)) != len(adjustment) or any(node not in graph.nodes for node in adjustment):
        raise ValueError("Adjustment variables must be unique known IDs.")
    if treatment in adjustment or outcome in adjustment:
        return False
    if set(adjustment) & set(graph.descendants(treatment)):
        return False
    mutilated = Graph(graph.nodes, directed=[(p, c) for p, c in graph.directed if p != treatment])
    return bool(d_separated(mutilated, treatment, outcome, adjustment))


def find_backdoor_sets(graph, treatment, outcome, *, max_sets=32, max_checks=1000, timeout=2.):
    """Bounded enumeration; complete=False never means no valid set exists."""
    if any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in (max_sets, max_checks)):
        raise ValueError("Backdoor search budgets must be positive integers.")
    if not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("Backdoor search timeout must be positive and finite.")
    check_backdoor(graph, treatment, outcome, [])  # validates identifiers and DAG
    available = sorted(set(graph.nodes) - {treatment, outcome} - set(graph.descendants(treatment)))
    sets, checks, start = [], 0, time.monotonic()
    for size in range(len(available) + 1):
        for adjustment in combinations(available, size):
            if checks >= max_checks or time.monotonic() - start >= timeout or len(sets) >= max_sets:
                return {"sets": sets, "complete": False, "checks": checks, "reason": "search budget exhausted"}
            checks += 1
            if check_backdoor(graph, treatment, outcome, adjustment):
                sets.append(list(adjustment))
    return {"sets": sets, "complete": True, "checks": checks, "reason": "all eligible sets checked"}
