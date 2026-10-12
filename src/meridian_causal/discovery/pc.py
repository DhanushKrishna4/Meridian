"""PC-stable skeleton with deterministic first-sepset collider orientation.

This is not conservative PC: no second search of all separating sets occurs.
Stable variable IDs determine first-sepset order; changing those IDs may change
finite-sample orientations. Conflicting proposals are surfaced explicitly.
"""
from __future__ import annotations

from itertools import combinations
from time import monotonic

import numpy as np

from ..graphs import (Graph, apply_orientation_proposals, meek_closure, pair,
                      validate_pdag)
from ..statistics import CITestCache


def pc_stable(data, nodes, alpha=.01, max_depth=3, max_tests=10000, timeout=10, oracle=None, progress=None):
    """Discover a bounded equivalence graph, preserving all failure statuses.

    ``oracle(x, y, S)`` returns an exact independence boolean using stable IDs.
    ``progress`` receives real completed-depth/test counters. Computation is
    synchronous; browser cancellation terminates the worker when needed.
    """
    nodes = tuple(nodes)
    if not np.isfinite(alpha) or not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between zero and one")
    if not isinstance(max_depth, int) or max_depth < 0 or not isinstance(max_tests, int) or max_tests < 1 or not np.isfinite(timeout) or timeout <= 0:
        raise ValueError("Invalid PC search budget")
    graph = Graph(nodes, undirected=combinations(sorted(nodes), 2))
    if len(nodes) < 2 or len(nodes) > 15:
        raise ValueError("PC supports 2–15 variables")
    cache = None if oracle is not None else CITestCache(data, nodes, max_entries=max_tests)
    started, tests = monotonic(), 0
    oracle_cache, sepsets, invalid_tests = {}, {}, []
    trace = [{"type": "start", "graph": graph.to_dict()}]
    status, reason, depth_completed = "complete", "adjacency search exhausted", -1
    if progress:
        progress({"stage": "pc", "completed": 0, "message": "Starting conditional-independence search"})

    def run_test(a, b, conditioning):
        nonlocal tests
        key = (pair(a, b), conditioning)
        if monotonic() - started >= timeout:
            return None, "timeout"
        if key not in oracle_cache:
            if tests >= max_tests:
                return None, "test_limit"
            tests += 1
            if oracle is not None:
                independent = oracle(a, b, conditioning)
                if not isinstance(independent, (bool, np.bool_)):
                    raise ValueError("Exact independence oracle must return a boolean")
                evidence = {"valid": True, "independent": bool(independent), "p_value": None, "oracle": True}
            else:
                result = cache.test(a, b, conditioning)
                evidence = result.to_dict()
                evidence["independent"] = bool(result.p_value > alpha) if result.valid else None
                evidence["oracle"] = False
            oracle_cache[key] = evidence
            trace.append({"type": "test", "x": a, "y": b, "conditioning": list(conditioning), **evidence})
        return oracle_cache[key], None

    for depth in range(min(max_depth, len(nodes) - 2) + 1):
        # The frozen sets are the defining PC-stable modification. Edges may
        # disappear within this stage; conditioning sets must not change.
        frozen = {node: graph.adjacency(node) for node in nodes}
        eligible = [edge for edge in sorted(graph.undirected)
                    if any(len(frozen[a] - {b}) >= depth for a, b in (edge, edge[::-1]))]
        if not eligible:
            break
        trace.append({"type": "depth_start", "depth": depth,
                      "adjacency": {n: sorted(frozen[n]) for n in sorted(nodes)}, "graph": graph.to_dict()})
        for a, b in eligible:
            # Union both endpoints' eligible sets and use stable lexical order.
            sets = set()
            for first, second in ((a, b), (b, a)):
                sets.update(combinations(sorted(frozen[first] - {second}), depth))
            for conditioning in sorted(sets):
                result, stop = run_test(a, b, conditioning)
                if stop:
                    status, reason = "budget_exhausted", stop
                    break
                if not result["valid"]:
                    invalid_tests.append({"x": a, "y": b, "conditioning": list(conditioning), **result})
                    status, reason = "numerical_failure", "invalid conditional-independence test"
                    break
                if result["independent"]:
                    sepsets[pair(a, b)] = conditioning
                    graph = Graph(nodes, undirected=graph.undirected - {pair(a, b)})
                    trace.append({"type": "remove_edge", "edge": [a, b], "depth": depth,
                                  "conditioning": list(conditioning), "evidence": result, "graph": graph.to_dict()})
                    break
            if status != "complete":
                break
        if status != "complete":
            break
        depth_completed = depth
        trace.append({"type": "depth_complete", "depth": depth, "tests": tests, "graph": graph.to_dict()})
        if progress:
            progress({"stage": "pc", "completed": depth + 1, "tests": tests,
                      "message": f"Completed conditioning depth {depth}; {tests} tests"})
        next_depth = depth + 1
        if not any(len(graph.adjacency(a) - {b}) >= next_depth
                   for edge in graph.undirected for a, b in (edge, edge[::-1])):
            break
        if depth == max_depth:
            status, reason = "budget_exhausted", "depth_limit"

    conflicts, ambiguous = [], []
    validation = {"valid": False, "is_cpdag": False, "reason": "Search incomplete; orientations not attempted"}
    if status == "complete":
        proposals = []
        for middle in sorted(nodes):
            for a, c in combinations(sorted(graph.adjacency(middle)), 2):
                if graph.adjacent(a, c):
                    continue
                separator = sepsets.get(pair(a, c))
                if separator is None:
                    # An empty recorded tuple differs from an absent key.
                    ambiguous.append({"triple": [a, middle, c], "reason": "no recorded separating set"})
                    continue
                collider = middle not in separator
                trace.append({"type": "triple", "triple": [a, middle, c],
                              "conditioning": list(separator), "decision": "collider" if collider else "noncollider"})
                if collider:
                    proposals.extend({"edge": [endpoint, middle], "rule": "collider",
                                      "premises": [a, middle, c], "conditioning": list(separator)} for endpoint in (a, c))
        graph, accepted, conflicts = apply_orientation_proposals(graph, proposals)
        trace.append({"type": "orientation_batch", "stage": "colliders", "proposals": proposals,
                      "accepted": accepted, "conflicts": conflicts, "graph": graph.to_dict()})
        # A conflicting collider batch is not a valid premise for more arrows.
        if not conflicts:
            graph, accepted, more_conflicts = meek_closure(graph)
            conflicts.extend(more_conflicts)
            trace.append({"type": "orientation_batch", "stage": "meek", "accepted": accepted,
                          "conflicts": more_conflicts, "graph": graph.to_dict()})
        validation = validate_pdag(graph, require_cpdag=True)
        if conflicts or ambiguous or not validation["valid"]:
            status, reason = "inconsistent_graph", "orientation conflicts or non-CPDAG output"
    elapsed = monotonic() - started
    graph_type = "CPDAG" if status == "complete" and validation["is_cpdag"] else "partial graph (not a verified CPDAG)"
    trace.append({"type": "finish", "status": status, "reason": reason, "graph": graph.to_dict()})
    return {"graph": graph.to_dict(), "graph_type": graph_type, "status": status, "reason": reason,
            "trace": trace, "tests": tests, "depth_completed": depth_completed, "elapsed_seconds": elapsed,
            "ambiguous_triples": ambiguous, "conflicts": conflicts, "invalid_tests": invalid_tests,
            "separating_sets": [{"edge": list(edge), "conditioning": list(s)} for edge, s in sorted(sepsets.items())],
            "validation": validation,
            "settings": {"alpha": alpha, "max_depth": max_depth, "max_tests": max_tests, "timeout": timeout,
                         "collider_variant": "first-separating-set (stable-ID order); not conservative PC",
                         "orientation": "simultaneous conflict-checked Meek R1–R3; no background knowledge",
                         "oracle": oracle is not None, "dataset_id": cache.dataset_id if cache else None}}
