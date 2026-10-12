"""Development-only references, with explicit optional-package skip reporting."""
import pytest

from checks import WORLDS, compare_fisher_z, compare_notears, compare_pc, vendor

pytestmark = pytest.mark.reference


def test_vendored_author_source_hashes():
    vendor()


def test_fisher_z_against_causal_learn():
    pytest.importorskip("causallearn")
    result = compare_fisher_z()
    assert len(result["comparisons"]) == 240
    assert result["max_absolute_error"] <= result["tolerance"]


@pytest.mark.parametrize("world", WORLDS)
def test_pc_against_causal_learn(world):
    pytest.importorskip("causallearn")
    result = compare_pc(world)
    assert result["meridian_status"] == "complete"
    assert result["graphs_equal"], result


@pytest.mark.parametrize("world", WORLDS[:3])
def test_notears_against_author_implementation(world):
    result = compare_notears(world)
    assert result["meridian_status"] == "complete"
    assert result["support_equal"], result
    assert result["max_absolute_weight_error"] < result["weight_atol"], result
