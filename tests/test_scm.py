"""Exact SCM fixtures plus simulations generated independently of moments()."""

import numpy as np
import pytest

from meridian_causal.graphs import Graph
from meridian_causal.scm import LinearSCM, check_backdoor, find_backdoor_sets, fit_scm
from meridian_causal.scm.worlds import equivalence_models, make_world, seeded_model, simulate_world_experiment


def test_equivalent_observational_laws_and_different_intervention_predictions():
    expected_covariance = np.array([[1, .8, .64], [.8, 1, .8], [.64, .8, 1]])
    for model, expected in zip(equivalence_models(), [[0, .8], [.8, 0], [.8, .8]]):
        mean, covariance = model.moments()
        np.testing.assert_allclose(mean, 0, atol=1e-14)
        np.testing.assert_allclose(covariance, expected_covariance, atol=1e-14)
        intervention_mean, intervention_covariance = model.moments({"Y": 1})
        np.testing.assert_allclose(intervention_mean[[0, 2]], expected, atol=1e-14)
        assert np.all(intervention_covariance[1] == 0)
        np.testing.assert_allclose(model.moments({"Y": 0})[0], 0, atol=1e-14)
    covariances = [model.moments({"Y": 0})[1] for model in equivalence_models()]
    assert all(not np.allclose(covariances[i], covariances[j]) for i in range(3) for j in range(i))


def test_observation_is_distinct_from_intervention():
    model = equivalence_models()[0]
    conditioned_mean, conditioned_covariance = model.condition({"Y": 1})
    intervened_mean, intervened_covariance = model.moments({"Y": 1})
    np.testing.assert_allclose(conditioned_mean, [.8, 1, .8])
    np.testing.assert_allclose(intervened_mean, [0, 1, .8])
    assert conditioned_covariance[0, 0] == pytest.approx(.36)
    assert intervened_covariance[0, 0] == pytest.approx(1.)
    np.testing.assert_allclose(model.condition({})[1], model.moments()[1])


@pytest.mark.parametrize("intervention", [{}, {"X": 2}, {"Y": 1}, {"Z": -3}, {"X": 2, "Z": -3}, {"X": 2, "Y": 1, "Z": -3}])
def test_moments_against_independent_structural_simulation(intervention):
    model = equivalence_models()[0]
    # Independent literal equations, not production simulate or covariance code.
    rng = np.random.default_rng(777)
    u = rng.normal(size=(90000, 3)) * [1, .6, .6]
    x = np.full(len(u), intervention["X"]) if "X" in intervention else u[:, 0]
    y = np.full(len(u), intervention["Y"]) if "Y" in intervention else .8 * x + u[:, 1]
    z = np.full(len(u), intervention["Z"]) if "Z" in intervention else .8 * y + u[:, 2]
    data = np.column_stack([x, y, z])
    mean, covariance = model.moments(intervention)
    np.testing.assert_allclose(data.mean(axis=0), mean, atol=.012)
    np.testing.assert_allclose(np.cov(data, rowvar=False), covariance, atol=.02)


def test_simulation_reproducibility_and_seed_independence():
    model = equivalence_models()[0]
    np.testing.assert_array_equal(model.simulate(50, 13), model.simulate(50, 13))
    assert not np.array_equal(model.simulate(50, 13), model.simulate(50, 14))
    np.testing.assert_allclose(model.simulate(5, 1, {"X": 1, "Y": 2, "Z": 3}), np.tile([1, 2, 3], (5, 1)))


def test_chain_counterfactual_hand_calculation():
    model = equivalence_models()[0]
    np.testing.assert_allclose(model.residuals([1, 1, 1]), [1, .2, .2], atol=1e-15)
    np.testing.assert_allclose(model.counterfactual([1, 1, 1], {"Y": 0}), [1, 0, .2], atol=1e-15)


@pytest.mark.parametrize("model", equivalence_models())
def test_counterfactual_reconstruction_consistency_and_nondescendants(model):
    row = model.simulate(1, 55)[0]
    np.testing.assert_allclose(model.counterfactual(row, {}), row, atol=1e-13)
    for node in model.nodes:
        index = model.nodes.index(node)
        np.testing.assert_allclose(model.counterfactual(row, {node: row[index]}), row, atol=1e-13)
        counterfactual = model.counterfactual(row, {node: row[index] + 2})
        for unchanged in set(model.nodes) - {node} - set(model.graph.descendants(node)):
            assert counterfactual[model.nodes.index(unchanged)] == pytest.approx(row[model.nodes.index(unchanged)])


def test_each_candidate_abducts_its_own_residuals():
    models = equivalence_models()
    results = [model.counterfactual([1, 1, 1], {"Y": 0}) for model in models]
    np.testing.assert_allclose(results, [[1, 0, .2], [.2, 0, 1], [.2, 0, .2]], atol=1e-14)


def test_total_effect_sums_parallel_paths():
    B = np.array([[0, 0, 0, 0], [2, 0, 0, 0], [3, 0, 0, 0], [.5, 4, -1, 0]])
    model = LinearSCM(["A", "B", "C", "D"], B, [0] * 4, [1] * 4)
    assert model.total_effects()[3, 0] == pytest.approx(.5 + 2 * 4 + 3 * -1)
    before = model.moments({"A": 0})[0]
    after = model.moments({"A": 1})[0]
    np.testing.assert_allclose(after - before, model.total_effects()[:, 0])


def test_original_units_transform_preserves_moments_interventions_and_counterfactuals():
    model = equivalence_models()[0]
    center, scale = np.array([10, -20, 5]), np.array([2, 3, .1])
    transformed = model.to_original_units(center, scale)
    for intervention in ({}, {"Y": 1}, {"X": -2, "Z": 0}):
        original_intervention = {node: center[model.nodes.index(node)] + scale[model.nodes.index(node)] * value for node, value in intervention.items()}
        mean, covariance = model.moments(intervention)
        new_mean, new_covariance = transformed.moments(original_intervention)
        np.testing.assert_allclose(new_mean, center + scale * mean, atol=1e-13)
        np.testing.assert_allclose(new_covariance, covariance * np.outer(scale, scale), atol=1e-13)
        row = np.array([1, 1, 1])
        np.testing.assert_allclose(transformed.counterfactual(center + scale * row, original_intervention), center + scale * model.counterfactual(row, intervention), atol=1e-13)


def test_fit_ols_original_units_and_recorded_estimator():
    true = equivalence_models()[0].to_original_units([20, -8, 2], [2, .5, 3])
    data = true.simulate(10000, 880)
    fitted = fit_scm(data, true.graph)
    np.testing.assert_allclose(fitted.B, true.B, atol=.12)
    np.testing.assert_allclose(fitted.intercept, true.intercept, atol=.5)
    np.testing.assert_allclose(fitted.noise_variances, true.noise_variances, rtol=.04)
    assert fitted.provenance == "observational-OLS-fit"
    assert fitted.fit_metadata["n"] == len(data)
    assert "RSS/n" in fitted.fit_metadata["estimator"]


def test_fit_rank_deficiency_rejected_instead_of_regularized():
    x = np.linspace(-2, 2, 50)
    graph = Graph(["A", "B", "C"], directed=[("A", "C"), ("B", "C")])
    with pytest.raises(ValueError, match="rank deficient|ill-conditioned"):
        fit_scm(np.column_stack([x, 2 * x, np.sin(x)]), graph)


def test_fit_records_variance_floor():
    x = np.linspace(-2, 2, 50)
    fitted = fit_scm(np.column_stack([x, 2 * x]), Graph(["A", "B"], directed=[("A", "B")]))
    diagnostic = fitted.fit_metadata["diagnostics"][1]
    assert diagnostic["variance_floored"]
    assert fitted.noise_variances[1] == diagnostic["variance_floor"]


def test_backdoor_observed_confounder_and_bounded_search():
    model = make_world("confounding")["truth"]
    assert not check_backdoor(model.graph, "X", "Y", [])
    assert check_backdoor(model.graph, "X", "Y", ["C"])
    assert not check_backdoor(model.graph, "X", "Y", ["Y"])
    result = find_backdoor_sets(model.graph, "X", "Y")
    assert result["complete"] and result["sets"] == [["C"]]
    result = find_backdoor_sets(model.graph, "X", "Y", max_checks=1)
    assert not result["complete"] and result["sets"] == []
    mean, covariance = model.moments()
    assert covariance[1, 2] / covariance[1, 1] > 0
    assert model.total_effects()[2, 1] < 0


def test_backdoor_descendants_are_ineligible_even_if_blocking():
    graph = Graph(["X", "M", "Y"], directed=[("X", "M"), ("M", "Y")])
    assert check_backdoor(graph, "X", "Y", [])
    assert not check_backdoor(graph, "X", "Y", ["M"])


def test_collider_conditioning_induces_association_but_do_does_not():
    model = make_world("collider")["truth"]
    assert model.moments()[1][0, 1] == 0
    assert model.condition({"Z": 0})[1][0, 1] < -.4
    assert model.moments({"Z": 0})[1][0, 1] == 0


def test_hidden_world_keeps_latent_data_outside_observations():
    world = make_world("hidden", seed=12, n=10000)
    assert world["nodes"] == ["X", "Y"] and world["data"].shape == (10000, 2)
    assert world["truth"]["hidden_nodes"] == ["H"]
    assert np.corrcoef(world["data"].T)[0, 1] > .7
    left = simulate_world_experiment("hidden", 14, 100, {"X": -4}, world_seed=12)
    right = simulate_world_experiment("hidden", 14, 100, {"X": 4}, world_seed=12)
    np.testing.assert_array_equal(left[:, 1], right[:, 1])
    with pytest.raises(ValueError, match="observed"):
        simulate_world_experiment("hidden", 14, 100, {"H": 4})


def test_seeded_world_preserves_graph_in_experiment_oracle():
    world = make_world("random", seed=33, n=20)
    node = world["nodes"][0]
    expected = world["truth"].simulate(50, 999, {node: 2})
    actual = simulate_world_experiment("random", 999, 50, {node: 2}, world_seed=33)
    np.testing.assert_array_equal(actual, expected)
    assert seeded_model(33).graph.is_dag()
    assert seeded_model(33).nodes != seeded_model(34).nodes


@pytest.mark.parametrize("payload", [
    {"nodes": ["X", "X"], "B": [[0, 0], [0, 0]], "intercept": [0, 0], "noise_variances": [1, 1]},
    {"nodes": ["X", "Y"], "B": [[0, 1], [1, 0]], "intercept": [0, 0], "noise_variances": [1, 1]},
    {"nodes": ["X", "Y"], "B": [[0, 0], [0, 0]], "intercept": [0, 0], "noise_variances": [1, 0]},
    {"nodes": ["X", "Y"], "B": [[0, 0], [0, 0]], "intercept": [0, float("nan")], "noise_variances": [1, 1]},
])
def test_invalid_models_rejected(payload):
    with pytest.raises(ValueError):
        LinearSCM.from_dict(payload)


def test_model_json_roundtrip_and_invalid_query_values():
    model = equivalence_models()[0]
    restored = LinearSCM.from_dict(model.to_dict())
    np.testing.assert_array_equal(restored.B, model.B)
    for values in ({"missing": 1}, {"X": float("nan")}, {"Y": [1]}, {"Z": "1"}):
        with pytest.raises(ValueError):
            model.moments(values)
    with pytest.raises(ValueError):
        model.counterfactual([1, 2], {"Y": 0})
    with pytest.raises(ValueError):
        model.simulate(1.2, 1)


@pytest.mark.parametrize('value',[True,'0',1+2j,np.complex128(1+2j)])
def test_model_and_query_numeric_types_are_not_silently_coerced(value):
    model=equivalence_models()[0]
    payload=model.to_dict()
    payload['intercept'][0]=value
    with pytest.raises(ValueError):
        LinearSCM.from_dict(payload)
    with pytest.raises(ValueError):
        model.moments({'X':value})


def test_zero_fitted_coefficient_preserves_the_selected_parent_graph(monkeypatch):
    graph=Graph(['X','Y'],directed=[('X','Y')])
    rng=np.random.default_rng(17)
    rows=rng.normal(size=(100,2))
    original=np.linalg.lstsq
    def exact_zero(design,y,rcond=None):
        values,residuals,rank,singular=original(design,y,rcond=rcond)
        if len(values)>1: values[1:]=0
        return values,residuals,rank,singular
    monkeypatch.setattr(np.linalg,'lstsq',exact_zero)
    model=fit_scm(rows,graph)
    assert model.B[1,0]==0
    assert model.graph==graph
    assert LinearSCM.from_dict(model.to_dict()).graph==graph
    assert model.total_effects()[1,0]==0
    invalid=model.to_dict()
    invalid['B'][0][1]=1
    with pytest.raises(ValueError,match='Fitted graph'):
        LinearSCM.from_dict(invalid)
