"""Small explicit graphs; IDs are strings and arrow tuples are (parent, child).

Graph construction checks the simple-graph representation, but permits directed
cycles so invalid discovery output can be inspected. Causal routines reject them.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import isfinite
from time import monotonic


def pair(a, b):
    return tuple(sorted((a, b)))


class Graph:
    def __init__(self, nodes, directed=(), undirected=()):
        self.nodes = tuple(nodes)
        if any(not isinstance(n, str) or not n for n in self.nodes):
            raise ValueError("Variable IDs must be nonempty strings")
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("Duplicate variable IDs")
        occupied = set()
        edges = []
        for kind, source in (("directed", directed), ("undirected", undirected)):
            current = set()
            for edge in source:
                if len(edge) != 2:
                    raise ValueError("An edge must have two endpoints")
                a, b = edge
                if a not in self.nodes or b not in self.nodes:
                    raise ValueError("Unknown edge endpoint")
                if a == b:
                    raise ValueError("Self-loops are invalid")
                key = pair(a, b)
                if key in occupied:
                    raise ValueError("Duplicate or contradictory edge")
                occupied.add(key)
                current.add((a, b) if kind == "directed" else key)
            edges.append(frozenset(current))
        self.directed, self.undirected = edges

    def __eq__(self, other):
        return (isinstance(other, Graph) and set(self.nodes) == set(other.nodes)
                and self.directed == other.directed and self.undirected == other.undirected)

    def __repr__(self):
        return f"Graph({self.nodes!r}, directed={sorted(self.directed)!r}, undirected={sorted(self.undirected)!r})"

    def to_dict(self):
        return {"nodes": list(self.nodes), "directed": [list(e) for e in sorted(self.directed)],
                "undirected": [list(e) for e in sorted(self.undirected)]}

    @classmethod
    def from_dict(cls, obj):
        if not isinstance(obj, dict) or "nodes" not in obj:
            raise ValueError("Expected graph object with nodes")
        return cls(obj["nodes"], obj.get("directed", ()), obj.get("undirected", ()))

    def _node(self, node):
        if node not in self.nodes:
            raise ValueError(f"Unknown variable: {node}")

    def parents(self, node):
        self._node(node)
        return frozenset(a for a, b in self.directed if b == node)

    def children(self, node):
        self._node(node)
        return frozenset(b for a, b in self.directed if a == node)

    def neighbors(self, node):
        self._node(node)
        return frozenset(b if a == node else a for a, b in self.undirected if node in (a, b))

    def adjacent(self, a, b):
        return pair(a, b) in self.skeleton()

    def adjacency(self, node):
        return self.parents(node) | self.children(node) | self.neighbors(node)

    def _reach(self, node, reverse=False):
        self._node(node)
        result, stack = set(), [node]
        while stack:
            here = stack.pop()
            for nxt in self.parents(here) if reverse else self.children(here):
                if nxt != node and nxt not in result:
                    result.add(nxt)
                    stack.append(nxt)
        return frozenset(result)

    def ancestors(self, node):
        return self._reach(node, True)

    def descendants(self, node):
        return self._reach(node)

    def topological_order(self):
        """Order the directed portion; undirected edges impose no ordering."""
        parents = {n: set(self.parents(n)) for n in self.nodes}
        order = []
        while parents:
            roots = sorted(n for n, p in parents.items() if not p)
            if not roots:
                raise ValueError("Directed graph contains a cycle")
            for node in roots:
                order.append(node)
                del parents[node]
            for remaining in parents.values():
                remaining.difference_update(roots)
        return tuple(order)

    def is_dag(self):
        if self.undirected:
            return False
        try:
            self.topological_order()
            return True
        except ValueError:
            return False

    def skeleton(self):
        return self.undirected | frozenset(pair(a, b) for a, b in self.directed)

    def colliders(self):
        return frozenset((a, b, c) for b in self.nodes
                         for a, c in combinations(sorted(self.parents(b)), 2)
                         if not self.adjacent(a, c))


def _as_set(value):
    return {value} if isinstance(value, str) else set(value)


def d_separated(graph, x, y, conditioned=()):
    """Exact d-separation by ancestral moralization, for disjoint node sets."""
    if not graph.is_dag():
        raise ValueError("d-separation requires a DAG")
    x, y, z = _as_set(x), _as_set(y), _as_set(conditioned)
    if not (x | y | z) <= set(graph.nodes):
        raise ValueError("Unknown variable in d-separation query")
    if (x & y) or (x & z) or (y & z):
        raise ValueError("d-separation query sets must be disjoint")
    ancestral = x | y | z
    for node in tuple(ancestral):
        ancestral |= set(graph.ancestors(node))
    moral = {n: set() for n in ancestral - z}
    edges = set(graph.skeleton())
    for node in ancestral:
        edges.update(combinations(sorted(graph.parents(node)), 2))
    for a, b in edges:
        if a in moral and b in moral:
            moral[a].add(b)
            moral[b].add(a)
    reached, stack = set(x), list(x)
    while stack:
        here = stack.pop()
        if here in y:
            return False
        for nxt in moral[here] - reached:
            reached.add(nxt)
            stack.append(nxt)
    return True


def apply_orientation_proposals(graph, proposals):
    """Apply a simultaneous batch; opposing proposals leave an unresolved edge.

    An entire batch producing a directed cycle is rejected, rather than using
    iteration order to choose a preferred subset. Conflicts are diagnostic data,
    never bidirected edges or a claim of hidden confounding.
    """
    grouped = {}
    for proposal in proposals:
        a, b = proposal["edge"]
        if not graph.adjacent(a, b):
            raise ValueError("Orientation proposal targets absent edge")
        grouped.setdefault(pair(a, b), []).append(proposal)
    directed, undirected = set(graph.directed), set(graph.undirected)
    accepted, conflicts = [], []
    for edge, evidence in sorted(grouped.items()):
        directions = {tuple(item["edge"]) for item in evidence}
        existing = {e for e in graph.directed if pair(*e) == edge}
        if len(directions | existing) > 1:
            conflicts.append({"edge": list(edge), "reason": "opposing orientations", "proposals": evidence})
            continue
        direction = next(iter(directions))
        if edge in undirected:
            undirected.remove(edge)
            directed.add(direction)
            accepted.extend(evidence)
    result = Graph(graph.nodes, directed, undirected)
    try:
        result.topological_order()
    except ValueError:
        conflicts.append({"reason": "orientation batch creates directed cycle", "proposals": accepted})
        return graph, [], conflicts
    return result, accepted, conflicts


def meek_proposals(graph):
    """R1–R3, Colombo & Maathuis (2014), section 3.1, after Meek (1995)."""
    proposals = []
    for left, right in sorted(graph.undirected):
        for a, b in ((left, right), (right, left)):
            for c in sorted(graph.parents(a)):
                if not graph.adjacent(c, b):
                    proposals.append({"edge": [a, b], "rule": "R1", "premises": [[c, a], [a, b]],
                                      "nonadjacent": [c, b]})
            for c in sorted(graph.children(a) & graph.parents(b)):
                proposals.append({"edge": [a, b], "rule": "R2", "premises": [[a, c], [c, b], [a, b]]})
            for c, d in combinations(sorted(graph.neighbors(a) & graph.parents(b)), 2):
                if not graph.adjacent(c, d):
                    proposals.append({"edge": [a, b], "rule": "R3",
                                      "premises": [[a, c], [c, b], [a, d], [d, b], [a, b]],
                                      "nonadjacent": [c, d]})
    return proposals


def meek_closure(graph):
    trace, conflicts, blocked = [], [], set()
    while True:
        proposals = [p for p in meek_proposals(graph) if pair(*p["edge"]) not in blocked]
        updated, accepted, rejected = apply_orientation_proposals(graph, proposals)
        trace.extend(accepted)
        conflicts.extend(rejected)
        blocked.update(pair(*c["edge"]) for c in rejected if "edge" in c)
        if updated == graph:
            return graph, trace, conflicts
        graph = updated


def dag_to_cpdag(graph):
    """Orient unshielded colliders then close under Meek R1–R3."""
    if not graph.is_dag():
        raise ValueError("DAG-to-CPDAG requires a DAG")
    pattern = Graph(graph.nodes, undirected=graph.skeleton())
    proposals = []
    for a, b, c in sorted(graph.colliders()):
        proposals.extend({"edge": [p, b], "rule": "collider", "premises": [a, b, c]} for p in (a, c))
    pattern, _, conflicts = apply_orientation_proposals(pattern, proposals)
    result, _, more_conflicts = meek_closure(pattern)
    if conflicts or more_conflicts:
        raise RuntimeError("A DAG generated contradictory orientation proposals")
    return result


def consistent_extension(graph):
    """Dor–Tarsi sink elimination; preserve skeleton, arrows and colliders.

    A removable sink has no children, and each undirected neighbor is adjacent
    to every other neighbor and every parent. Existing parents need not form a
    clique: their unshielded collider is already part of the input.
    """
    graph.topological_order()
    remaining = set(graph.nodes)
    directed, undirected = set(graph.directed), set(graph.undirected)
    while remaining:
        chosen = None
        for node in sorted(remaining):
            if any(a == node and b in remaining for a, b in directed):
                continue
            neighbors = {b if a == node else a for a, b in undirected if node in (a, b)} & remaining
            parents = {a for a, b in directed if b == node and a in remaining}
            if all(graph.adjacent(a, b) for a in neighbors for b in (neighbors | parents) - {a}):
                chosen = node
                for neighbor in neighbors:
                    undirected.remove(pair(neighbor, node))
                    directed.add((neighbor, node))
                break
        if chosen is None:
            raise ValueError("Partially directed graph has no consistent DAG extension")
        remaining.remove(chosen)
    result = Graph(graph.nodes, directed)
    if not result.is_dag() or result.colliders() != graph.colliders():
        raise ValueError("Partially directed graph has no consistent DAG extension")
    return result


def validate_pdag(graph, require_cpdag=False):
    """Return explicit structural diagnostics; full CPDAG check is optional."""
    try:
        extension = consistent_extension(graph)
    except ValueError as error:
        return {"valid": False, "is_cpdag": False, "reason": str(error)}
    cpdag = dag_to_cpdag(extension)
    is_cpdag = cpdag == graph
    return {"valid": is_cpdag if require_cpdag else True, "is_cpdag": is_cpdag,
            "reason": "complete equivalence graph" if is_cpdag else "extendible PDAG is not a completed equivalence graph"}


@dataclass
class ExtensionResult:
    graphs: list
    complete: bool
    reason: str
    expansions: int

    def to_dict(self):
        return {"graphs": [g.to_dict() for g in self.graphs], "complete": self.complete,
                "reason": self.reason, "expansions": self.expansions}


def enumerate_extensions(graph, max_candidates=128, max_expansions=100000, timeout=5):
    """Bounded DFS, forbidding new colliders and cycles at every branch.

    Only this finite list is returned when truncated; no total class size is
    estimated. One extra valid leaf distinguishes exactly-at-cap completion.
    """
    if not isinstance(max_candidates, int) or max_candidates < 1 or not isinstance(max_expansions, int) or max_expansions < 1 or not isfinite(timeout) or timeout <= 0:
        raise ValueError("Enumeration budgets must be positive")
    consistent_extension(graph)
    started, expansions, candidates = monotonic(), 0, []
    pending = [graph]
    allowed_colliders = graph.colliders()
    while pending:
        if monotonic() - started >= timeout:
            return ExtensionResult(candidates, False, "timeout", expansions)
        if expansions >= max_expansions:
            return ExtensionResult(candidates, False, "expansion_limit", expansions)
        current = pending.pop()
        expansions += 1
        try:
            current.topological_order()
        except ValueError:
            continue
        if not current.colliders() <= allowed_colliders:
            continue
        if not current.undirected:
            if len(candidates) >= max_candidates:
                return ExtensionResult(candidates, False, "candidate_limit", expansions)
            candidates.append(current)
            continue
        a, b = min(current.undirected)
        remaining = current.undirected - {(a, b)}
        for arrow in ((b, a), (a, b)):
            pending.append(Graph(current.nodes, current.directed | {arrow}, remaining))
    return ExtensionResult(candidates, True, "exhausted", expansions)
