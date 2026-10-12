"""A transparent disagreement heuristic, not expected information gain."""

from collections.abc import Mapping

import numpy as np

from meridian_causal.scm import LinearSCM


def validate_models(models):
    if not isinstance(models, (list, tuple)) or not 1 <= len(models) <= 128:
        raise ValueError("Supply between 1 and 128 fitted or user-specified candidate models.")
    if any(not isinstance(model, LinearSCM) for model in models):
        raise ValueError("Learner APIs accept explicit LinearSCM candidates, never world/truth descriptors.")
    if any("truth" in model.provenance.lower() or "oracle" in model.provenance.lower() for model in models):
        raise ValueError("Simulator truth cannot be a learner or experiment-selection input.")
    nodes = models[0].nodes
    if any(model.nodes != nodes for model in models):
        raise ValueError("Every candidate must have identical stable variable IDs in the same order.")
    return nodes


def rank_interventions(models, training_data, values=None, *, bounds=None, max_proposals=150, candidate_set_complete=None):
    """Rank one-variable interventions by pairwise mean AND covariance disagreement.

    Means are divided by fixed training standard deviations, and covariance
    entries by products of those scales. Pairwise squared differences are
    averaged over candidates and coordinates, with equal mean/covariance weight.
    Default values are mean ± SD and mean, inside mean ± 2 SD bounds.
    """
    nodes = validate_models(models)
    data = np.asarray(training_data, dtype=float)
    if data.ndim != 2 or data.shape[1] != len(nodes) or not 3 <= len(data) <= 1_000_000 or not np.isfinite(data).all():
        raise ValueError("Training data must have 3–1,000,000 finite rows aligned with model IDs.")
    centers, scales = data.mean(axis=0), data.std(axis=0, ddof=1)
    if not np.isfinite(centers).all() or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("Experiment ranking requires nonconstant training columns with finite scales.")
    if candidate_set_complete is not None and not isinstance(candidate_set_complete, bool):
        raise ValueError("candidate_set_complete must be boolean or None (unknown).")
    if isinstance(max_proposals, bool) or not isinstance(max_proposals, int) or not 1 <= max_proposals <= 1000:
        raise ValueError("max_proposals must be an integer between 1 and 1000.")
    if values is not None and (not isinstance(values, Mapping) or any(node not in nodes for node in values)):
        raise ValueError("Candidate values must map known variable IDs to lists of finite values.")
    if bounds is not None and (not isinstance(bounds, Mapping) or any(node not in nodes for node in bounds)):
        raise ValueError("Bounds must map known variable IDs to [lower,upper].")
    if values is None:
        values = {node: [centers[j] - scales[j], centers[j], centers[j] + scales[j]] for j, node in enumerate(nodes)}
    rankings, proposals = [], 0
    for j, node in enumerate(nodes):
        if node not in values:
            continue
        interval = (bounds or {}).get(node, [centers[j] - 2 * scales[j], centers[j] + 2 * scales[j]])
        if not isinstance(interval, (list, tuple, np.ndarray)) or len(interval) != 2:
            raise ValueError("Each intervention bound must contain a lower and upper value.")
        if any(isinstance(v,(bool,np.bool_)) or not isinstance(v,(int,float,np.integer,np.floating)) for v in interval):
            raise ValueError('Intervention bounds must contain real numbers, without booleans or strings.')
        low, high = np.asarray(interval, dtype=float)
        if not np.isfinite([low, high]).all() or low > high:
            raise ValueError("Intervention bounds must be finite and ordered.")
        node_values = values[node]
        if not isinstance(node_values, (list, tuple, np.ndarray)):
            raise ValueError("Each variable's candidate values must be a list.")
        proposals += len(node_values)
        if proposals > max_proposals:
            raise ValueError(f"Experiment proposal budget exceeded ({max_proposals}).")
        free = [k for k in range(len(nodes)) if k != j]
        norm_covariance = np.outer(scales[free], scales[free])
        validated_values = []
        for value in node_values:
            if isinstance(value, (bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)) or not np.isfinite(value) or not low <= value <= high:
                raise ValueError(f"Intervention on {node} must be finite and inside [{low:.6g}, {high:.6g}] original units.")
            validated_values.append(float(value))
        for value in sorted(set(validated_values)):
            predictions = [model.moments({node: float(value)}) for model in models]
            means = np.array([mean[free] / scales[free] for mean, _ in predictions])
            covariances = np.array([cov[np.ix_(free, free)] / norm_covariance for _, cov in predictions])
            count = len(models)
            if count < 2 or not free:
                mean_score = covariance_score = 0.
            else:
                # Pairwise identity avoids an O(K²) materialized tensor.
                mean_score = float(2 * count / (count - 1) * np.var(means, axis=0).mean())
                covariance_score = float(2 * count / (count - 1) * np.var(covariances, axis=0).mean())
            if not np.isfinite([mean_score,covariance_score,mean_score+covariance_score]).all():
                raise ValueError('Intervention disagreement overflowed; inspect training scales and candidate magnitudes.')
            rankings.append({"variable": node, "value": float(value), "score": mean_score + covariance_score,
                             "mean_score": mean_score, "covariance_score": covariance_score,
                             "bounds": [float(low), float(high)], "units": "original data units",
                             "candidate_count": count, "normalization": "fixed training standard deviations",
                             "candidate_set_complete": candidate_set_complete,
                             "candidate_scope": "provided candidate list; not a complete identified set",
                             "label": "candidate disagreement heuristic (mean + covariance)"})
    return sorted(rankings, key=lambda item: (-item["score"], item["variable"], item["value"]))
