import copy

import numpy as np
import pytest

from meridian_causal.experiments import Campaign, intervention_log_likelihood, rank_interventions
from meridian_causal.scm import LinearSCM, fit_scm
from meridian_causal.scm.worlds import equivalence_models, make_world


def training_data():
    return equivalence_models()[0].simulate(1000, 91)


def test_covariance_disagreement_matters_when_interventional_means_coincide():
    ranking = rank_interventions(equivalence_models(), training_data(), {"Y": [0]})
    assert ranking[0]["mean_score"] == 0
    assert ranking[0]["covariance_score"] > .1
    assert ranking[0]["score"] == ranking[0]["covariance_score"]


def test_both_mean_and_covariance_disagreement_are_ranked():
    results = rank_interventions(equivalence_models(), training_data(), {"Y": [0, 1]})
    assert results[0]["value"] == 1
    assert results[0]["mean_score"] > 0
    assert results[0]["covariance_score"] > 0


def test_ranking_normalization_invariant_to_units():
    models, data = equivalence_models(), training_data()
    original = rank_interventions(models, data, {"Y": [0, 1]})
    center, scale = np.array([20, -40, 3]), np.array([.2, 100, 4])
    scaled_models = [model.to_original_units(center, scale) for model in models]
    transformed = rank_interventions(scaled_models, center + scale * data, {"Y": [-40, 60]})
    np.testing.assert_allclose([item["score"] for item in original], [item["score"] for item in transformed], atol=1e-12)


def test_values_are_bounded_in_original_units():
    with pytest.raises(ValueError, match="inside"):
        rank_interventions(equivalence_models(), training_data(), {"Y": [100]})
    with pytest.raises(ValueError, match="inside"):
        rank_interventions(equivalence_models(), training_data(), {"Y": [1]}, bounds={"Y": [-.5, .5]})
    for item in rank_interventions(equivalence_models(), training_data()):
        assert item["bounds"][0] <= item["value"] <= item["bounds"][1]


def test_truth_objects_are_rejected_by_learner_apis():
    for world in (make_world("equivalence"), make_world("hidden")):
        with pytest.raises(ValueError, match="truth|Truth|Simulator"):
            rank_interventions([world["truth"]], world["data"])
        with pytest.raises(ValueError):
            Campaign([world["truth"]])
    with pytest.raises(TypeError):
        rank_interventions(equivalence_models(), training_data(), truth=make_world("equivalence")["truth"])


def test_campaign_parameters_are_snapshotted_before_outcomes():
    models = equivalence_models()
    campaign = Campaign(models)
    plan = campaign.freeze({"Y": 1}, 50, .75)
    # Source-side mutation cannot influence the campaign snapshots.
    models[0].B.setflags(write=True)
    models[0].B[1, 0] = 7
    assert campaign.models[0].B[1, 0] == .8
    assert plan["candidate_count"] == 3 and plan["score"] == .75 and plan["n"] == 50
    altered = copy.deepcopy(plan)
    altered["intervention"]["Y"] = 0
    with pytest.raises(ValueError, match="unaltered"):
        campaign.update(altered, np.ones((50, 3)), "batch")
    with pytest.raises(ValueError, match="frozen"):
        campaign.update({"intervention": {"Y": 1}, "n": 50}, np.ones((50, 3)), "batch")


def test_likelihood_excludes_clamped_mechanism_and_retains_parent_value():
    nodes = ["X", "Y"]
    a = LinearSCM(nodes, [[0, 0], [2, 0]], [0, 0], [1, 1])
    b = LinearSCM(nodes, [[0, 0], [2, 0]], [999, 0], [10000, 1])
    rows = np.array([[3, 6.1], [3, 5.8]])
    score_a = intervention_log_likelihood(a, rows, {"X": 3})
    score_b = intervention_log_likelihood(b, rows, {"X": 3})
    expected = -.5 * (2 * np.log(2 * np.pi) + .1**2 + .2**2)
    assert score_a == pytest.approx(score_b)
    assert score_a == pytest.approx(expected)
    assert intervention_log_likelihood(a, [[3, 6]], {"X": 3, "Y": 6}) == 0


def test_no_duplicate_evidence_by_plan_id_batch_id_or_content():
    campaign = Campaign(equivalence_models())
    plan = campaign.freeze({"Y": 1}, 30)
    rows = equivalence_models()[0].simulate(30, 45, {"Y": 1})
    result = campaign.update(plan, rows, "batch1")
    before = campaign.weights.copy()
    with pytest.raises(ValueError, match="already used"):
        campaign.update(plan, rows, "batch2")
    second_plan = campaign.freeze({"Y": 1}, 30)
    with pytest.raises(ValueError, match="already used"):
        campaign.update(second_plan, rows, "batch1")
    with pytest.raises(ValueError, match="already been counted"):
        campaign.update(second_plan, rows, "batch2")
    np.testing.assert_array_equal(campaign.weights, before)
    assert "not Bayesian" in result["label"]


def test_wrong_batch_count_and_nonclamped_data_do_not_update_support():
    campaign = Campaign(equivalence_models())
    plan = campaign.freeze({"Y": 1}, 30)
    with pytest.raises(ValueError, match="dimensions"):
        campaign.update(plan, np.ones((29, 3)), "batch")
    with pytest.raises(ValueError, match="hard intervention"):
        campaign.update(plan, np.zeros((30, 3)), "batch")
    np.testing.assert_allclose(campaign.weights, [1 / 3] * 3)
    assert campaign.history == []


def test_support_stably_accumulates_fixed_parameter_likelihoods():
    campaign = Campaign(equivalence_models(), candidate_set_complete=False)
    for seed in range(4):
        plan = campaign.freeze({"Y": 1}, 100)
        rows = equivalence_models()[0].simulate(100, seed, {"Y": 1})
        result = campaign.update(plan, rows, str(seed))
        assert np.isfinite(result["weights"]).all()
        assert sum(result["weights"]) == pytest.approx(1)
        assert not result["candidate_set_complete"]
    assert campaign.weights[0] > .999
    assert len(campaign.history) == 4


def test_complete_real_fitted_observe_intervene_update_campaign():
    fixture = equivalence_models()[0]
    data = fixture.simulate(1200, 891)
    candidates = [fit_scm(data[:900], model.graph) for model in equivalence_models()]
    campaign = Campaign(candidates)
    ranking = rank_interventions(candidates, data[:900])
    selected = ranking[0]
    plan = campaign.freeze({selected["variable"]: selected["value"]}, 100, selected["score"])
    new_observations = fixture.simulate(plan["n"], 321, plan["intervention"])
    updated = campaign.update(plan, new_observations, "first-real-batch")
    assert updated["weights"][0] > .99


def test_campaign_export_restores_exact_support_and_consumed_evidence():
    campaign = Campaign(equivalence_models(), candidate_set_complete=False)
    plan = campaign.freeze({"Y": 0}, 100)
    rows = equivalence_models()[0].simulate(100, 921, {"Y": 0})
    campaign.update(plan, rows, "batch0")
    exported = campaign.to_dict()
    restored = Campaign.from_dict(exported)
    assert restored.to_dict() == exported
    with pytest.raises(ValueError, match="already used"):
        restored.update(plan, rows, "batch0")
    bad = copy.deepcopy(exported)
    bad["history"][0]["weights"] = [.1, .2, .7]
    with pytest.raises(ValueError, match="replay"):
        Campaign.from_dict(bad)
    bad = copy.deepcopy(exported)
    bad["models"][0]["B"][1][0] = .1
    with pytest.raises(ValueError, match="digest"):
        Campaign.from_dict(bad)


def test_single_candidate_reports_zero_disagreement():
    result = rank_interventions(equivalence_models()[:1], training_data())
    assert all(item["score"] == 0 for item in result)


def test_import_does_not_accept_invented_support_without_evidence():
    exported = Campaign(equivalence_models()).to_dict()
    exported["log_support"] = [0, -1, -2]
    with pytest.raises(ValueError, match="evidence history"):
        Campaign.from_dict(exported)


@pytest.mark.parametrize('weights',[1/3,[1/3],['0.3','0.3','0.4'],[True,False,False]])
def test_import_rejects_broadcast_or_coerced_weight_vectors(weights):
    campaign=Campaign(equivalence_models())
    plan=campaign.freeze({'Y':0},10)
    campaign.update(plan,equivalence_models()[0].simulate(10,201,{'Y':0}),'batch')
    snapshot=campaign.to_dict()
    snapshot['history'][0]['weights']=weights
    with pytest.raises(ValueError,match='numeric list'):
        Campaign.from_dict(snapshot)


def test_full_outcome_verification_is_read_only():
    campaign=Campaign(equivalence_models(),candidate_set_complete=False)
    plan=campaign.freeze({'Y':0},10)
    rows=equivalence_models()[0].simulate(10,201,{'Y':0})
    record=campaign.update(plan,rows,'batch')
    before=campaign.to_dict()
    campaign.verify_outcomes(record,rows.tolist())
    assert campaign.to_dict()==before
    record['log_likelihoods']=[value+1 for value in record['log_likelihoods']]
    with pytest.raises(ValueError,match='likelihoods.*replay'):
        campaign.verify_outcomes(record,rows.tolist())


def test_content_digests_use_portable_json_numeric_values():
    from meridian_causal.experiments.campaign import _digest
    assert _digest({'values':[1.0,-0.0,1e-8,1e21]})==_digest({'values':[1,0,1e-8,10**21]})
    assert _digest({'value':True})!=_digest({'value':1})


@pytest.mark.parametrize('bounds',[{'Y':['-2','2']},{'Y':[False,True]},{'Y':[0,None]}])
def test_intervention_bounds_require_real_numbers(bounds):
    with pytest.raises(ValueError,match='bounds.*real numbers'):
        rank_interventions(equivalence_models(),training_data(),values={'Y':[0]},bounds=bounds)
