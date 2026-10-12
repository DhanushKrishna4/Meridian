"""Simulator-only worlds. Never pass their truth objects to discovery or selection."""

from __future__ import annotations

import numpy as np

from .linear import LinearSCM


_WORLD_METADATA = [
    {"id": "equivalence", "name": "Same observations, different causes", "description":
     "A three-variable Gaussian chain. Three DAGs share the same observational law but disagree about interventions. Candidate parameters are fitted from training observations."},
    {"id": "collider", "name": "Conditioning opens a path", "description":
     "Two independent causes share an outcome. Conditioning on the outcome induces association; intervening on it leaves the causes independent."},
    {"id": "confounding", "name": "A sign reversal", "description":
     "An observed common cause reverses the naive association between treatment and outcome. An explicit adjustment set separates association from the model's direct effect."},
    {"id": "hidden", "name": "When assumptions fail", "description":
     "A demonstration with an unobserved common cause. Causal sufficiency is deliberately violated; the learner does not diagnose that violation from observations alone."},
    {"id": "random", "name": "A seeded sparse system", "description":
     "A reproducible sparse DAG with randomized labels and unequal structural noise scales. Discovery receives observed rows only."},
]


def worlds():
    return [dict(world) for world in _WORLD_METADATA]


def equivalence_models():
    """Exact mathematical fixtures; live candidate fitting must use observations."""
    nodes = ("X", "Y", "Z")
    forward = np.array([[0, 0, 0], [.8, 0, 0], [0, .8, 0]])
    reverse = forward.T
    fork = np.array([[0, .8, 0], [0, 0, 0], [0, .8, 0]])
    return [LinearSCM(nodes, forward, [0, 0, 0], [1, .36, .36], "exact-mathematical-fixture"),
            LinearSCM(nodes, reverse, [0, 0, 0], [.36, .36, 1], "exact-mathematical-fixture"),
            LinearSCM(nodes, fork, [0, 0, 0], [.36, 1, .36], "exact-mathematical-fixture")]


def seeded_model(seed=7, d=6, noise="unequal", edge_probability=.25):
    """Sparse DAG in a random topological order, with labels separately shuffled."""
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)) or seed < 0:
        raise ValueError("World seed must be a nonnegative integer.")
    if isinstance(d, bool) or not isinstance(d, (int, np.integer)) or not 2 <= d <= 15:
        raise ValueError("Seeded worlds support 2–15 variables.")
    if noise not in ("equal", "unequal", "wide") or not np.isfinite(edge_probability) or not 0 <= edge_probability <= 1:
        raise ValueError("Choose equal, unequal or wide noise and an edge probability in [0,1].")
    rng = np.random.default_rng(seed)
    labels = [f"V{i + 1}" for i in rng.permutation(d)]
    order, B = rng.permutation(d), np.zeros((d, d))
    for position, parent in enumerate(order):
        for child in order[position + 1:]:
            if rng.random() < edge_probability:
                B[child, parent] = rng.uniform(.35, .95) * rng.choice([-1., 1.])
    noise_variances = np.ones(d) if noise == "equal" else np.exp(rng.uniform(-1.2 if noise == "unequal" else -2.5, 1.2 if noise == "unequal" else 2.5, d))
    return LinearSCM(labels, B, rng.uniform(-.3, .3, d), noise_variances, "simulator-truth")


def _truth(name, seed):
    if name == "equivalence":
        fixture = equivalence_models()[0]
        return LinearSCM(fixture.nodes, fixture.B, fixture.intercept, fixture.noise_variances, "simulator-truth")
    if name == "collider":
        return LinearSCM(("X", "Y", "Z"), [[0, 0, 0], [0, 0, 0], [.9, .9, 0]], [0, 0, 0], [1, 1, .25], "simulator-truth")
    if name == "confounding":
        return LinearSCM(("C", "X", "Y"), [[0, 0, 0], [1.1, 0, 0], [1.8, -.8, 0]], [0, 0, 0], [1, .3, .3], "simulator-truth")
    if name == "hidden":
        return LinearSCM(("H", "X", "Y"), [[0, 0, 0], [1, 0, 0], [1, 0, 0]], [0, 0, 0], [1, .3, .3], "simulator-truth")
    if name == "random":
        return seeded_model(seed)
    raise ValueError(f"Unknown world {name!r}; choose one of {[w['id'] for w in _WORLD_METADATA]}.")


def make_world(name, seed=7, n=800):
    model = _truth(name, seed)
    data = model.simulate(n, seed)
    metadata = next(world for world in _WORLD_METADATA if world["id"] == name)
    truth = model
    nodes = list(model.nodes)
    if name == "hidden":
        nodes, data = ["X", "Y"], data[:, [1, 2]]
        truth = {"kind": "hidden-confounder", "model": model.to_dict(), "observed_nodes": nodes,
                 "hidden_nodes": ["H"], "assumption_violation": "causal sufficiency",
                 "description": "The simulator contains H → X and H → Y, with no direct X–Y edge. This is simulator knowledge, not a discovery diagnosis."}
    return {"data": data, "nodes": nodes, "truth": truth, "description": metadata["description"],
            "world": name, "seed": int(seed)}


def simulate_world_experiment(name, seed, n, interventions, *, world_seed=7):
    """Separate experiment oracle; seed is a fresh batch seed, world_seed stays fixed.

    For the random world it is essential to preserve the original world_seed.
    The hidden world's latent noise is generated internally and never returned.
    """
    model = _truth(name, world_seed)
    if name == "hidden" and (not isinstance(interventions, dict) or any(node not in ("X", "Y") for node in interventions)):
        raise ValueError("Only observed variables X and Y may be intervened on in this world.")
    data = model.simulate(n, seed, interventions)
    return data[:, [1, 2]] if name == "hidden" else data
