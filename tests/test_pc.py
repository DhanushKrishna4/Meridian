from collections import defaultdict
from itertools import combinations, permutations

import numpy as np
import pytest

from meridian_causal.discovery.pc import pc_stable
from meridian_causal.graphs import Graph
from test_graphs import all_dags, independent_dsep, independent_signature


@pytest.mark.parametrize("n", [2, 3, 4])
def test_exact_oracle_pc_all_labeled_dags(n):
    # Exact independence comes from independent active-path enumeration.
    dags = list(all_dags(n))
    classes = defaultdict(list)
    for nodes, edges in dags:
        classes[independent_signature(nodes, edges)].append(edges)
    for nodes, edges in dags:
        signature = independent_signature(nodes, edges)
        compelled = frozenset.intersection(*classes[signature])
        unresolved = signature[0] - {tuple(sorted(e)) for e in compelled}
        expected = Graph(nodes, compelled, unresolved)
        oracle = lambda a, b, s: independent_dsep(nodes, edges, a, b, s)
        for order in [nodes, tuple(reversed(nodes))]:
            result = pc_stable(None, order, max_depth=n-2, oracle=oracle)
            assert result["status"] == "complete", (nodes, edges, result)
            assert Graph.from_dict(result["graph"]) == expected
            assert result["graph_type"] == "CPDAG"


def test_all_column_permutations_stable_ids_real_data():
    rng = np.random.default_rng(193)
    data = rng.normal(size=(600, 4))
    data[:, 2] += data[:, 0] * .9 + data[:, 1] * .7
    data[:, 3] += data[:, 2] * .8
    nodes = ("A", "B", "C", "D")
    baseline = pc_stable(data, nodes, max_depth=2)
    for order in permutations(range(4)):
        result = pc_stable(data[:, order], [nodes[i] for i in order], max_depth=2)
        assert result["status"] == baseline["status"]
        assert Graph.from_dict(result["graph"]) == Graph.from_dict(baseline["graph"])
        assert result["separating_sets"] == baseline["separating_sets"]


def test_empty_separator_orients_collider_and_trace_is_replayable():
    nodes, edges = tuple("ABC"), {("A", "B"), ("C", "B")}
    result = pc_stable(None, nodes, oracle=lambda a, b, s: independent_dsep(nodes, edges, a, b, s))
    assert result["separating_sets"] == [{"edge": ["A", "C"], "conditioning": []}]
    assert result["graph"]["directed"] == [["A", "B"], ["C", "B"]]
    assert result["trace"][0]["graph"]["undirected"] == [["A", "B"], ["A", "C"], ["B", "C"]]
    assert any(event["type"] == "remove_edge" and event["evidence"]["independent"] for event in result["trace"])
    assert any(event["type"] == "orientation_batch" and event["accepted"] for event in result["trace"])


def test_budget_exhaustion_and_invalid_test_statuses():
    for budgets, reason in [({"max_tests": 1}, "test_limit"), ({"max_depth": 0}, "depth_limit"), ({"timeout": 1e-20}, "timeout")]:
        result = pc_stable(None, tuple("ABCD"), oracle=lambda *args: False, **budgets)
        assert result["status"] == "budget_exhausted" and result["reason"] == reason
        assert result["graph_type"] != "CPDAG"
    result = pc_stable(np.ones((50, 3)), tuple("ABC"))
    assert result["status"] == "numerical_failure"
    assert result["invalid_tests"][0]["p_value"] is None
    assert not result["separating_sets"]


def test_frozen_adjacency_from_both_endpoints():
    seen = set()
    def oracle(a, b, s):
        seen.add((a, b, tuple(s)))
        # A-C is removed at depth zero, so A cannot supply C at depth one;
        # testing A-B | C must still use B's adjacency set.
        return (a, b) == ("A", "C") and not s or (a, b) == ("A", "B") and s == ("C",)
    result = pc_stable(None, tuple("ABC"), oracle=oracle)
    assert ("A", "B", ("C",)) in seen
    assert {tuple(s["edge"]) for s in result["separating_sets"]} == {("A", "B"), ("A", "C")}


def test_skeleton_uses_frozen_sets_within_depth():
    seen = set()
    def oracle(a, b, s):
        seen.add((a, b, tuple(s)))
        return bool(s) and ((a, b, s) == ("A", "B", ("C",)) or (a, b, s) == ("A", "C", ("B",)))
    result = pc_stable(None, tuple("ABC"), oracle=oracle)
    assert ("A", "C", ("B",)) in seen
    assert len(result["separating_sets"]) == 2


def test_incompatible_collider_evidence_reported_as_conflict():
    # Marginal separation of A-C and B-D yields A->B<-C and B->C<-D:
    # opposite arrow proposals on B-C. This CI oracle is inconsistent.
    keep = {("A", "B"), ("B", "C"), ("C", "D")}
    result = pc_stable(None, tuple("ABCD"), oracle=lambda a, b, s: (a, b) not in keep)
    assert result["status"] == "inconsistent_graph"
    assert any(conflict.get("edge") == ["B", "C"] for conflict in result["conflicts"])
    assert ["B", "C"] in result["graph"]["undirected"]


@pytest.mark.parametrize("seed", [3, 8, 14, 37, 68])
def test_statistical_chain_recovery_across_seeds(seed):
    rng = np.random.default_rng(seed)
    data = rng.normal(size=(1600, 3))
    data[:, 1] = .8 * data[:, 0] + .6 * data[:, 1]
    data[:, 2] = .8 * data[:, 1] + .6 * data[:, 2]
    result = pc_stable(data, ["X", "Y", "Z"], alpha=.005)
    assert result["status"] == "complete"
    graph = Graph.from_dict(result["graph"])
    # Strong links should survive; a weak finite-sample extra edge is allowed.
    assert {("X", "Y"), ("Y", "Z")} <= graph.skeleton()
    assert not graph.directed


def test_progress_records_real_stage_counters():
    progress = []
    result = pc_stable(None, tuple("ABC"), oracle=lambda *args: False, progress=progress.append)
    assert len(progress) == 3
    assert progress[-1]["tests"] == result["tests"]
