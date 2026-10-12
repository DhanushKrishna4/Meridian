import numpy as np
import pytest

from meridian_causal.evaluation import graph_metrics, intervention_prediction_metrics, predictive_log_scores
from meridian_causal.experiments import intervention_log_likelihood
from meridian_causal.graphs import Graph, dag_to_cpdag
from meridian_causal.scm.worlds import equivalence_models, make_world


def test_markov_equivalent_dag_directions_have_zero_cpdag_error():
    forward, reverse, fork = equivalence_models()
    for model in (reverse, fork):
        metrics = graph_metrics(forward.graph, model.graph, estimate_is_dag=True)
        assert metrics["cpdag_state_error"] == 0
        assert metrics["skeleton_f1"] == 1
        assert metrics["dag_arrow_symmetric_difference"] > 0
        assert metrics["compelled_true"] == metrics["compelled_predicted"] == 0
        assert metrics["compelled_precision"] is None


def test_compelled_unresolved_reversal_and_missing_counts():
    truth = Graph("ABC", [("A", "B"), ("C", "B")])
    estimate = Graph("ABC", [("B", "A")], [("B", "C")])
    metrics = graph_metrics(truth, estimate, conflicts=1)
    assert metrics["cpdag_state_error"] == 2
    assert metrics["skeleton_f1"] == 1
    assert metrics["compelled_reversed"] == metrics["true_compelled_left_unresolved"] == 1
    assert metrics["compelled_correct"] == 0
    assert metrics["compelled_true"] == 2
    assert metrics["conflicting_directions"] == 1
    assert graph_metrics(truth, Graph("ABC"))["skeleton_recall"] == 0
    assert graph_metrics(Graph("ABC"), Graph("ABC"))["skeleton_f1"] == 1


def test_matching_truth_predictions_are_exact_and_rescaling_invariant():
    forward, reverse, _ = equivalence_models()
    interventions = [{"X": 1}, {"Y": 0}, {"Z": -1}]
    assert intervention_prediction_metrics([forward], forward, interventions, [1, 1, 1])["intervention_mean_nrmse"] == 0
    base = intervention_prediction_metrics([reverse], forward, interventions, [1, 1, 1])
    center, scale = np.array([2, 4, -3]), np.array([.2, 100, 3])
    transformed = [{node: center[forward.nodes.index(node)] + scale[forward.nodes.index(node)] * value for node, value in intervention.items()} for intervention in interventions]
    actual = intervention_prediction_metrics([reverse.to_original_units(center, scale)], forward.to_original_units(center, scale), transformed, scale)
    for metric in ("intervention_mean_nrmse", "intervention_covariance_nrmse"):
        assert actual[metric] == pytest.approx(base[metric])


def test_mixture_predictions_include_between_model_variation():
    models = equivalence_models()
    metric = intervention_prediction_metrics(models, models[0], [{"Y": 1}], [1, 1, 1])
    # X means [0,.8,.8], Z means [.8,0,.8]; uniform mixture errors [8/15,-4/15].
    expected = np.sqrt(((8 / 15) ** 2 + (4 / 15) ** 2) / 2)
    assert metric["intervention_mean_nrmse"] == pytest.approx(expected)
    assert metric["intervention_covariance_nrmse"] > 0


def test_predictive_density_matches_structural_likelihood_single_model():
    truth = equivalence_models()[0]
    rows = truth.simulate(20, 321, {"Y": 0})
    scores = predictive_log_scores([truth], [1], rows, {"Y": 0})
    assert sum(scores) == pytest.approx(intervention_log_likelihood(truth, rows, {"Y": 0}))
    with pytest.raises(ValueError, match="sum to one"):
        predictive_log_scores([truth], [0], rows, {"Y": 0})
    with pytest.raises(ValueError, match="hard intervention"):
        predictive_log_scores([truth], [1], rows, {"Y": 1})


def test_hidden_truth_can_only_be_projected_in_evaluation():
    from meridian_causal.scm import LinearSCM, fit_scm
    world = make_world("hidden", seed=7)
    truth = LinearSCM.from_dict(world["truth"]["model"])
    candidate = fit_scm(world["data"], Graph(["X", "Y"], [("X", "Y")]))
    metrics = intervention_prediction_metrics([candidate], truth, [{"X": 1}], [1, 1])
    assert metrics["intervention_mean_nrmse"] > .5


def test_node_mismatch_and_invalid_dag_fail_explicitly():
    with pytest.raises(ValueError, match="identical"):
        graph_metrics(Graph("AB"), Graph("AC"))
    with pytest.raises(ValueError, match="acyclic"):
        graph_metrics(Graph("ABC"), Graph("ABC", [("A", "B"), ("B", "C"), ("C", "A")]), estimate_is_dag=True)
