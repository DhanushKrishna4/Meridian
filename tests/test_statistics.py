import math

import numpy as np
import pytest
from scipy.stats import norm, pearsonr

from meridian_causal.statistics import (CITestCache, InvalidTest, data_diagnostics,
                                       fisher_z, partial_correlation)


def exact_covariance_rows(covariance, n=200):
    rng = np.random.default_rng(9)
    x = rng.normal(size=(n, len(covariance)))
    x -= x.mean(axis=0)
    q, _ = np.linalg.qr(x)
    return q @ np.linalg.cholesky(covariance).T * np.sqrt(n - 1)


def test_known_covariance_partial_correlation_and_fisher_z():
    covariance = np.array([[1, .8, .64], [.8, 1, .8], [.64, .8, 1]])
    x = exact_covariance_rows(covariance)
    assert partial_correlation(x, 0, 1) == pytest.approx(.8, abs=1e-14)
    assert partial_correlation(x, 0, 2, [1]) == pytest.approx(0, abs=1e-14)
    precision = np.linalg.solve(covariance, np.eye(3))
    expected = -precision[0, 1] / np.sqrt(precision[0, 0] * precision[1, 1])
    assert partial_correlation(x, 0, 1, [2]) == pytest.approx(expected)
    result = fisher_z(x, 0, 1, [2])
    z = math.sqrt(len(x) - 1 - 3) * math.atanh(expected)
    assert result.valid and result.degrees_of_freedom == 196
    assert result.statistic == pytest.approx(z)
    assert result.p_value == pytest.approx(2 * norm.sf(abs(z)))


@pytest.mark.parametrize("seed", [1, 7, 21, 109])
def test_partial_correlation_reference_residuals_and_rescaling(seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(180, 4))
    x[:, 0] += x[:, 2] * 2
    x[:, 1] -= x[:, 2] * .7
    design = np.column_stack([np.ones(len(x)), x[:, 2:]])
    # Independent explicit regression + SciPy Pearson reference.
    residuals = x[:, :2] - design @ np.linalg.lstsq(design, x[:, :2], rcond=None)[0]
    reference = pearsonr(residuals[:, 0], residuals[:, 1]).statistic
    assert partial_correlation(x, 0, 1, [2, 3]) == pytest.approx(reference, abs=1e-13)
    scaled = x * [1e-8, -1e7, 5e4, -1e-5] + [3, 5, 10, 0]
    assert partial_correlation(scaled, 0, 1, [2, 3]) == pytest.approx(-reference, abs=1e-8)
    assert fisher_z(x, 0, 1, [2, 3]).p_value == pytest.approx(fisher_z(scaled, 0, 1, [2, 3]).p_value, abs=1e-8)


def test_invalid_tests_do_not_report_independence():
    rng = np.random.default_rng(5)
    x = rng.normal(size=(20, 4))
    variants = [np.ones((20, 4)), x[:4], x.copy(), x.copy(), x.copy()]
    variants[2][:, 1] = variants[2][:, 0]
    variants[3][2, 0] = np.nan
    variants[4][:, 1] = variants[4][:, 0] + rng.normal(size=20) * 1e-14
    for value in variants:
        result = fisher_z(value, 0, 1, [2])
        assert not result.valid and result.p_value is None and result.reason
    assert not fisher_z(x, 0, 1, [1]).valid
    with pytest.raises(InvalidTest):
        partial_correlation(x, 0, 0)


def test_cache_identity_and_snapshot_invalidation():
    data = np.random.default_rng(9).normal(size=(100, 3))
    first = CITestCache(data, ["A", "B", "C"])
    result = first.test("A", "B", ["C"])
    assert first.test("B", "A", ["C"]) is result and first.hits == 1
    data[:, 1] += data[:, 0] * 4
    second = CITestCache(data, ["A", "B", "C"])
    assert first.dataset_id != second.dataset_id
    assert first.test("A", "B", ["C"]) is result
    assert second.test("A", "B", ["C"]).p_value != result.p_value
    assert second.dataset_id != CITestCache(data, ["A", "B", "C"], preprocessing={"center": True}).dataset_id
    assert second.dataset_id != CITestCache(data, ["B", "A", "C"]).dataset_id
    assert second.dataset_id != CITestCache(data, ["A", "B", "C"], condition_limit=1e10).dataset_id
    bounded = CITestCache(data, ["A", "B", "C"], max_entries=1)
    bounded.test("A", "B")
    bounded.test("A", "C")
    assert len(bounded._cache) == 1


def test_data_diagnostics_explain_invalid_data():
    assert data_diagnostics(np.ones((10, 2)), ["X", "Y"])["constant_columns"] == ["X", "Y"]
    x = np.column_stack([np.arange(10), np.arange(10)])
    assert data_diagnostics(x)["near_dependent"]
    x = x.astype(float)
    x[0, 0] = np.inf
    assert data_diagnostics(x)["nonfinite"] == 1
