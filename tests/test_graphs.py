"""Independent small-graph oracles: no production conversion builds expectations."""
from collections import defaultdict
from itertools import combinations, product

import pytest

from meridian_causal.graphs import (Graph, apply_orientation_proposals,
    consistent_extension, dag_to_cpdag, d_separated, enumerate_extensions,
    meek_closure, meek_proposals, validate_pdag)


def independent_acyclic(nodes, edges):
    # Brute directed-path search is deliberately unlike production Kahn sort.
    for root in nodes:
        stack = [b for a, b in edges if a == root]
        visited = set()
        while stack:
            node = stack.pop()
            if node == root:
                return False
            if node not in visited:
                visited.add(node)
                stack.extend(b for a, b in edges if a == node)
    return True


def independent_signature(nodes, edges):
    skeleton = frozenset(tuple(sorted(e)) for e in edges)
    colliders = set()
    for a, b, c in product(nodes, repeat=3):
        if a < c and (a, b) in edges and (c, b) in edges and tuple(sorted((a, c))) not in skeleton:
            colliders.add((a, b, c))
    return skeleton, frozenset(colliders)


def all_dags(n):
    nodes = tuple("ABCD"[:n])
    pairs = list(combinations(nodes, 2))
    for state in product((0, 1, 2), repeat=len(pairs)):
        edges = frozenset(edge if orientation == 1 else edge[::-1]
                          for edge, orientation in zip(pairs, state) if orientation)
        if independent_acyclic(nodes, edges):
            yield nodes, edges


def independent_dsep(nodes, edges, x, y, conditioned):
    # Enumerate every simple undirected path and apply the active-trail rule.
    skeleton, _ = independent_signature(nodes, edges)
    conditioned = set(conditioned)
    ancestor_of_condition = set(conditioned)
    while True:
        expanded = ancestor_of_condition | {a for a, b in edges if b in ancestor_of_condition}
        if expanded == ancestor_of_condition:
            break
        ancestor_of_condition = expanded
    pending = [[x]]
    while pending:
        path = pending.pop()
        if path[-1] == y:
            active = True
            for a, b, c in zip(path, path[1:], path[2:]):
                collider = (a, b) in edges and (c, b) in edges
                if (collider and b not in ancestor_of_condition) or (not collider and b in conditioned):
                    active = False
                    break
            if active:
                return False
        else:
            pending.extend(path + [n] for n in nodes if n not in path and tuple(sorted((path[-1], n))) in skeleton)
    return True


@pytest.mark.parametrize("n,expected_count", [(1, 1), (2, 3), (3, 25), (4, 543)])
def test_exhaustive_equivalence_oracle_and_extensions(n, expected_count):
    classes = defaultdict(list)
    dags = list(all_dags(n))
    assert len(dags) == expected_count
    for nodes, edges in dags:
        classes[independent_signature(nodes, edges)].append(edges)
    for (skeleton, colliders), members in classes.items():
        # Every direction shared by every independently enumerated equivalent
        # DAG is compelled. This does not call the production converter.
        compelled = frozenset.intersection(*members)
        reversible = skeleton - {tuple(sorted(e)) for e in compelled}
        expected = Graph(nodes, compelled, reversible)
        for edges in members:
            assert dag_to_cpdag(Graph(nodes, edges)) == expected
        extension = consistent_extension(expected)
        assert extension.directed in members
        found = enumerate_extensions(expected, max_candidates=1000)
        assert found.complete
        assert {g.directed for g in found.graphs} == set(members)
        assert len(found.graphs) == len(members)
        assert validate_pdag(expected, require_cpdag=True)["valid"]


@pytest.mark.parametrize("n", [2, 3, 4])
def test_exhaustive_dsep_against_independent_path_oracle(n):
    for nodes, edges in all_dags(n):
        graph = Graph(nodes, edges)
        for x, y in combinations(nodes, 2):
            remaining = set(nodes) - {x, y}
            for size in range(len(remaining) + 1):
                for conditioned in combinations(sorted(remaining), size):
                    assert d_separated(graph, x, y, conditioned) == independent_dsep(nodes, edges, x, y, conditioned)


def test_graph_semantics_and_invalid_representations():
    graph = Graph(["D", "C", "B", "A"], [("A", "B"), ("B", "C")])
    assert graph.parents("B") == {"A"}
    assert graph.children("B") == {"C"}
    assert graph.ancestors("C") == {"A", "B"}
    assert graph.descendants("A") == {"B", "C"}
    assert graph.topological_order() == ("A", "D", "B", "C")
    assert Graph.from_dict(graph.to_dict()) == graph
    for args in [(["A", "A"],), (["A"], [("A", "A")]), (["A"], [("A", "B")]),
                 (["A", "B"], [("A", "B"), ("B", "A")]), (["A", "B"], [("A", "B")], [("A", "B")])]:
        with pytest.raises(ValueError):
            Graph(*args)
    cyclic = Graph("ABC", [("A", "B"), ("B", "C"), ("C", "A")])
    assert not cyclic.is_dag()
    with pytest.raises(ValueError):
        cyclic.topological_order()
    assert not validate_pdag(cyclic)["valid"]


def test_meek_rules_have_recorded_premises():
    fixtures = [
        (Graph("ABC", [("A", "B")], [("B", "C")]), "R1", ["B", "C"]),
        (Graph("ABC", [("A", "B"), ("B", "C")], [("A", "C")]), "R2", ["A", "C"]),
        (Graph("ABCD", [("C", "B"), ("D", "B")], [("A", "B"), ("A", "C"), ("A", "D")]), "R3", ["A", "B"]),
    ]
    for graph, rule, edge in fixtures:
        assert any(p["rule"] == rule and p["edge"] == edge and p["premises"] for p in meek_proposals(graph))
        oriented, trace, conflicts = meek_closure(graph)
        assert tuple(edge) in oriented.directed
        assert any(p["rule"] == rule for p in trace)
        assert not conflicts


def test_orientation_conflicts_are_explicit_and_not_bidirected():
    graph = Graph("AB", undirected=[("A", "B")])
    proposals = [{"edge": ["A", "B"], "rule": "test"}, {"edge": ["B", "A"], "rule": "test"}]
    for order in (proposals, list(reversed(proposals))):
        result, accepted, conflicts = apply_orientation_proposals(graph, order)
        assert result == graph and not accepted and len(conflicts) == 1
    graph = Graph("ABC", undirected=[("A", "B"), ("B", "C"), ("A", "C")])
    cyclic = [{"edge": edge, "rule": "test"} for edge in [["A", "B"], ["B", "C"], ["C", "A"]]]
    result, _, conflicts = apply_orientation_proposals(graph, cyclic)
    assert result == graph and "cycle" in conflicts[0]["reason"]


def test_nonchordal_graph_has_no_consistent_extension():
    square = Graph("ABCD", undirected=[("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")])
    with pytest.raises(ValueError, match="no consistent"):
        consistent_extension(square)


def test_extension_budgets_and_exact_cap():
    graph = Graph("ABC", undirected=[("A", "B"), ("B", "C")])
    assert not enumerate_extensions(graph, max_candidates=2).complete
    assert enumerate_extensions(graph, max_candidates=3).complete
    short = enumerate_extensions(graph, max_expansions=1)
    assert short.reason == "expansion_limit" and not short.complete
    short = enumerate_extensions(graph, timeout=1e-20)
    assert short.reason == "timeout" and not short.complete


def test_larger_collider_descendant_and_multiple_query_sets():
    graph = Graph("ABCDE", [("A", "C"), ("B", "C"), ("C", "D")])
    assert d_separated(graph, "A", "B")
    assert not d_separated(graph, "A", "B", ["D"])
    assert d_separated(graph, {"A", "B"}, {"E"})
    assert dag_to_cpdag(graph).directed == graph.directed
