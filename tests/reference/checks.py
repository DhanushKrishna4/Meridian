"""Small deterministic comparisons with pinned external implementations.

Run this file to preserve raw comparisons. It does not train or tune settings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
from itertools import combinations
import json
from pathlib import Path
import platform
import time

import numpy as np

from meridian_causal.discovery.notears import acyclicity, notears, reconstruction
from meridian_causal.discovery.pc import pc_stable
from meridian_causal.graphs import Graph
from meridian_causal.scm.worlds import make_world
from meridian_causal.statistics import fisher_z

ROOT = Path(__file__).resolve().parent
REFERENCE_VERSION = "0.1.4.4"
PC_CONFIG = {"alpha": .01, "indep_test": "fisherz", "stable": True, "uc_rule": 0,
             "uc_priority": 2, "show_progress": False}
NOTEARS_CONFIG = {"lambda1": .1, "threshold": .2, "standardize": False, "max_outer": 30,
                  "max_inner": 1000, "h_tol": 1e-8, "timeout": 20}
WORLDS = ("equivalence", "collider", "confounding", "random")


def check_reference_version():
    version = importlib.metadata.version("causal-learn")
    if version != REFERENCE_VERSION:
        raise RuntimeError(f"Reference comparisons require causal-learn=={REFERENCE_VERSION}; found {version}")
    return version


def vendor():
    manifest = json.loads((ROOT / "vendor/manifest.json").read_text())
    for name, source in manifest["files"].items():
        assert hashlib.sha256((ROOT / "vendor" / name).read_bytes()).hexdigest() == source["sha256"]
    spec = importlib.util.spec_from_file_location("notears_author_reference", ROOT / "vendor/notears_linear.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, manifest


def digest(data):
    return hashlib.sha256(np.ascontiguousarray(data).tobytes()).hexdigest()


def convert_reference_graph(matrix, nodes):
    """causal-learn tail=-1/head=+1; fail on unresolved endpoint encodings."""
    directed, undirected = [], []
    for i, j in combinations(range(len(nodes)), 2):
        endpoints = (matrix[i, j], matrix[j, i])
        if endpoints == (-1, 1):
            directed.append((nodes[i], nodes[j]))
        elif endpoints == (1, -1):
            directed.append((nodes[j], nodes[i]))
        elif endpoints == (-1, -1):
            undirected.append((nodes[i], nodes[j]))
        elif endpoints != (0, 0):
            raise ValueError(f"Unsupported/conflicting reference endpoints: {endpoints}")
    return Graph(nodes, directed, undirected)


def compare_fisher_z():
    check_reference_version()
    from causallearn.utils.cit import CIT
    rng = np.random.default_rng(113)
    data = rng.normal(size=(600, 6))
    data[:, 2] += .4 * data[:, 0] - .3 * data[:, 1]
    data[:, 4] += .5 * data[:, 2]
    reference = CIT(data, "fisherz")
    rows = []
    for a, b in combinations(range(6), 2):
        remaining = sorted(set(range(6)) - {a, b})
        for size in range(5):
            for conditioned in combinations(remaining, size):
                ours = fisher_z(data, a, b, conditioned)
                theirs = float(reference(a, b, list(conditioned)))
                assert ours.valid
                rows.append({"x": a, "y": b, "conditioned": list(conditioned),
                             "meridian": ours.p_value, "causal_learn": theirs,
                             "absolute_error": abs(ours.p_value - theirs)})
    return {"seed": 113, "n": 600, "d": 6, "data_digest": digest(data), "comparisons": rows,
            "max_absolute_error": max(row["absolute_error"] for row in rows), "tolerance": 2e-12}


def compare_pc(world):
    check_reference_version()
    from causallearn.search.ConstraintBased.PC import pc
    sample = make_world(world, seed=113, n=2000)
    data, nodes = sample["data"], sample["nodes"]
    ours = pc_stable(data, nodes, alpha=.01, max_depth=5, timeout=20)
    theirs = pc(data, node_names=nodes, **PC_CONFIG)
    expected = convert_reference_graph(theirs.G.graph, nodes)
    actual = Graph.from_dict(ours["graph"])
    return {"world": world, "seed": 113, "n": 2000, "data_digest": digest(data),
            "meridian_status": ours["status"], "meridian_graph": actual.to_dict(),
            "causal_learn_graph": expected.to_dict(), "graphs_equal": actual == expected,
            "meridian_settings": ours["settings"], "reference_settings": PC_CONFIG}


def compare_notears(world):
    module, manifest = vendor()
    sample = make_world(world, seed=113, n=2000)
    data = sample["data"]
    ours = notears(data, sample["nodes"], **NOTEARS_CONFIG)
    # Author W[parent, child] is Meridian B.T. No standardization in either run.
    reference = module.notears_linear(data, lambda1=.1, loss_type="l2", max_iter=30,
                                      h_tol=1e-8, rho_max=1e16, w_threshold=.2).T
    selected = np.array(ours["selected_weights"])
    z = data - data.mean(axis=0)
    reference_loss, _ = reconstruction(reference, z)
    our_loss, _ = reconstruction(selected, z)
    return {"world": world, "seed": 113, "n": 2000, "data_digest": digest(data),
            "meridian_status": ours["status"], "meridian_selected_B": selected.tolist(),
            "author_selected_B": reference.tolist(), "support_equal": bool(np.array_equal(selected != 0, reference != 0)),
            "max_absolute_weight_error": float(np.max(np.abs(selected - reference))),
            "weight_atol": .03, "meridian_selected_loss": our_loss, "author_selected_loss": reference_loss,
            "meridian_raw_h": ours["h"], "meridian_selected_h": acyclicity(selected)[0],
            "author_selected_h": acyclicity(reference)[0], "meridian_settings": NOTEARS_CONFIG,
            "reference_settings": {"loss_type": "l2", "lambda1": .1, "w_threshold": .2, "max_iter": 30,
                                   "h_tol": 1e-8, "rho_max": 1e16, "inner_solver": "unmodified SciPy L-BFGS-B defaults"},
            "reference_commit": manifest["commit"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/reference.json"))
    args = parser.parse_args()
    start = time.perf_counter()
    results = {"fisher_z": compare_fisher_z(), "pc": [compare_pc(w) for w in WORLDS],
               "notears": [compare_notears(w) for w in WORLDS[:3]]}
    results["environment"] = {"generated_utc": datetime.now(timezone.utc).isoformat(),
                              "python": platform.python_version(), "platform": platform.platform(),
                              "numpy": importlib.metadata.version("numpy"), "scipy": importlib.metadata.version("scipy"),
                              "causal_learn": check_reference_version(), "wall_seconds": time.perf_counter() - start}
    results["passed"] = (results["fisher_z"]["max_absolute_error"] <= results["fisher_z"]["tolerance"]
                         and all(r["graphs_equal"] and r["meridian_status"] == "complete" for r in results["pc"])
                         and all(r["support_equal"] and r["max_absolute_weight_error"] < r["weight_atol"]
                                 and r["meridian_status"] == "complete" for r in results["notears"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    print(f"Saved {args.output}; passed={results['passed']}; wall={results['environment']['wall_seconds']:.3f}s")
    if not results["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
