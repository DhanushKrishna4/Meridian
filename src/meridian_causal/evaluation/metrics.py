"""Explicit graph-state and original-unit-normalized prediction measurements."""

from itertools import combinations

import numpy as np
from scipy.special import logsumexp

from meridian_causal.graphs import dag_to_cpdag


def _state(graph, a, b):
    if (a, b) in graph.directed:
        return "forward"
    if (b, a) in graph.directed:
        return "reverse"
    if tuple(sorted((a, b))) in graph.undirected:
        return "unresolved"
    return "absent"


def graph_metrics(truth_dag, estimate, *, estimate_is_dag=False, conflicts=0):
    """Compare {absent, undirected, forward, reverse} once per node pair.

    ``cpdag_state_error`` counts one differing state per unordered pair, including
    a reversal as one error. DAG estimates are first converted to their CPDAG,
    avoiding penalties for choosing another member of the true equivalence class.
    DAG arrow recovery is separately reported and is not observational recovery.
    Empty precision/recall denominators return 1 only for an empty correct set.
    """
    if set(truth_dag.nodes) != set(estimate.nodes):
        raise ValueError("Truth and estimate must have identical variable IDs.")
    truth = dag_to_cpdag(truth_dag)
    if estimate_is_dag and not estimate.is_dag():
        raise ValueError("A DAG estimate must be acyclic and fully directed.")
    compared = dag_to_cpdag(estimate) if estimate_is_dag else estimate
    actual, predicted = truth.skeleton(), compared.skeleton()
    tp = len(actual & predicted)
    precision = tp / len(predicted) if predicted else float(not actual)
    recall = tp / len(actual) if actual else float(not predicted)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.
    correct = len(truth.directed & compared.directed)
    result = {
        "skeleton_precision": precision, "skeleton_recall": recall, "skeleton_f1": f1,
        "skeleton_true_positive": tp, "skeleton_false_positive": len(predicted - actual),
        "skeleton_false_negative": len(actual - predicted),
        "cpdag_state_error": sum(_state(truth, a, b) != _state(compared, a, b)
                                 for a, b in combinations(sorted(truth.nodes), 2)),
        "compelled_correct": correct, "compelled_predicted": len(compared.directed),
        "compelled_true": len(truth.directed),
        "compelled_precision": correct / len(compared.directed) if compared.directed else None,
        "compelled_recall": correct / len(truth.directed) if truth.directed else None,
        "compelled_reversed": sum((b, a) in compared.directed for a, b in truth.directed),
        "true_compelled_left_unresolved": sum(tuple(sorted(edge)) in compared.undirected for edge in truth.directed),
        "unresolved_directions": len(compared.undirected),
        "output_unresolved_directions": len(estimate.undirected),
        "conflicting_directions": int(conflicts),
        "comparison": "induced CPDAG" if estimate_is_dag else "returned partially directed graph",
    }
    if estimate_is_dag:
        result["dag_arrow_symmetric_difference"] = len(truth_dag.directed ^ estimate.directed)
        result["dag_exact_recovery"] = truth_dag == estimate
    return result


def _validate_models(models, scales):
    if not models:
        raise ValueError("At least one explicit model is required.")
    nodes = models[0].nodes
    if any(model.nodes != nodes for model in models):
        raise ValueError("Model variable IDs and order must match.")
    scales = np.asarray(scales, dtype=float)
    if scales.shape != (len(nodes),) or not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("Scales must be finite positive training scales.")
    return nodes, scales


def intervention_prediction_metrics(models, truth, interventions, training_scales):
    """Average errors over interventions and nonclamped coordinates.

    Equal-weight candidate mixture moments include between-model mean variation.
    Mean errors use training SD; covariance errors use its outer product. Truth
    may contain hidden nodes; evaluation projects it onto observed candidate IDs.
    This function is an evaluator, not an experiment-selection API.
    """
    nodes, scales = _validate_models(models, training_scales)
    truth_indices = [truth.nodes.index(node) for node in nodes]
    mean_errors, covariance_errors = [], []
    for intervention in interventions:
        free = [i for i, node in enumerate(nodes) if node not in intervention]
        if not free:
            continue
        predictions = [model.moments(intervention) for model in models]
        means = np.array([mean for mean, _ in predictions])
        mean = means.mean(axis=0)
        delta = means - mean
        covariance = np.mean([cov for _, cov in predictions], axis=0) + delta.T @ delta / len(models)
        true_mean, true_cov = truth.moments(intervention)
        true_mean = true_mean[truth_indices]
        true_cov = true_cov[np.ix_(truth_indices, truth_indices)]
        mean_errors.extend(((mean[free] - true_mean[free]) / scales[free]) ** 2)
        norm = np.outer(scales[free], scales[free])
        covariance_errors.extend((((covariance - true_cov)[np.ix_(free, free)] / norm) ** 2).ravel())
    if not mean_errors:
        raise ValueError("At least one nonclamped evaluation coordinate is required.")
    return {"intervention_mean_nrmse": float(np.sqrt(np.mean(mean_errors))),
            "intervention_covariance_nrmse": float(np.sqrt(np.mean(covariance_errors))),
            "prediction_candidate_count": len(models), "prediction_pooling": "uniform candidate mixture",
            "normalization": "training SD for mean; training SD outer product for covariance"}


def predictive_log_scores(models, weights, data, intervention):
    """Per-row log density under fixed-weight mixture; omit clamped equations."""
    nodes, _ = _validate_models(models, np.ones(len(models[0].nodes)))
    rows = np.asarray(data, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if rows.ndim != 2 or rows.shape[1] != len(nodes) or not np.isfinite(rows).all():
        raise ValueError("Evaluation rows must be finite and aligned with model IDs.")
    if weights.shape != (len(models),) or np.any(weights < 0) or not np.isfinite(weights).all() or not np.isclose(weights.sum(), 1):
        raise ValueError("Mixture weights must be nonnegative and sum to one.")
    values = models[0]._values(intervention)
    for node, value in values.items():
        if not np.allclose(rows[:, nodes.index(node)], value, rtol=1e-10, atol=1e-10):
            raise ValueError("Evaluation rows do not match the hard intervention.")
    free = [i for i, node in enumerate(nodes) if node not in values]
    logs = []
    for model in models:
        residuals = rows[:, free] - model.intercept[free] - rows @ model.B[free].T
        variance = model.noise_variances[free]
        logs.append(-.5 * (np.log(2 * np.pi * variance).sum() + (residuals ** 2 / variance).sum(axis=1)))
    with np.errstate(divide="ignore"):
        return logsumexp(np.array(logs) + np.log(weights)[:, None], axis=0)
