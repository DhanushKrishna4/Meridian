"""Serial, bounded benchmark. Run from the checkout with PYTHONPATH=src.

The preset and seeds are fixed before observing results; there is no tuning.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import time

import numpy as np

from meridian_causal.discovery.notears import notears
from meridian_causal.discovery.pc import pc_stable
from meridian_causal.evaluation import graph_metrics, intervention_prediction_metrics, predictive_log_scores
from meridian_causal.experiments import Campaign, rank_interventions
from meridian_causal.graphs import Graph, enumerate_extensions
from meridian_causal.scm import LinearSCM, fit_scm
from meridian_causal.scm.worlds import make_world, seeded_model


PC = dict(alpha=.01, max_depth=3, max_tests=10000, timeout=10)
NOTEARS = dict(lambda1=.1, threshold=.2, max_outer=30, max_inner=150, h_tol=1e-8, timeout=20)
SCALES = np.array([.2, .5, 1., 2., 5.])


def digest(rows):
    return hashlib.sha256(np.ascontiguousarray(rows).tobytes()).hexdigest()


def fit_candidates(result, data, nodes, method):
    if result["status"] != "complete":
        return [], {"status": "not attempted: discovery incomplete"}
    graph = Graph.from_dict(result["graph"])
    if method == "pc":
        extension = enumerate_extensions(graph, max_candidates=128, max_expansions=10000, timeout=5)
        graphs, complete = extension.graphs, extension.complete
        metadata = {"status": extension.reason, "complete": complete, "count": len(graphs), "expansions": extension.expansions}
    else:
        graphs = [graph]
        metadata = {"status": "single score-selected DAG", "complete": False, "count": 1}
    return [fit_scm(data, graph) for graph in graphs], metadata


def run_discovery(truth, data, nodes, method, standardize=True):
    started = time.perf_counter()
    record = {"method": method, "standardize": standardize if method == "notears" else None}
    try:
        result = pc_stable(data, nodes, **PC) if method == "pc" else notears(data, nodes, standardize=standardize, **NOTEARS)
        record.update(status=result["status"], reason=result.get("reason", result.get("termination_reason")),
                      graph=result["graph"], runtime_seconds=result["elapsed_seconds"], settings=result["settings"])
        graph = Graph.from_dict(result["graph"])
        # Invalid NOTEARS output may contain an empty display graph plus conflicts;
        # do not score that empty surrogate as if it were the optimizer's estimate.
        if method == "pc" or result["graph_valid"]:
            if set(truth.nodes) == set(nodes):
                record["graph_metrics"] = graph_metrics(truth.graph, graph, estimate_is_dag=method != "pc",
                                                        conflicts=len(result.get("conflicts", [])))
        if method == "notears":
            record.update(h=result["h"], iterations=result["iterations"], converged=result["converged"],
                          preprocessing=result["preprocessing"], graph_valid=result["graph_valid"])
        else:
            record.update(tests=result["tests"], conflicts=result["conflicts"])
        models, candidate_info = fit_candidates(result, data, nodes, method)
        record["candidates"] = candidate_info
        if models:
            interventions = [{node: float(data[:, j].mean() + sign * data[:, j].std(ddof=1))}
                             for j, node in enumerate(nodes) for sign in (-1, 0, 1)]
            record["prediction_metrics"] = intervention_prediction_metrics(models, truth, interventions, data.std(axis=0, ddof=1))
    except (ValueError, RuntimeError, np.linalg.LinAlgError, FloatingPointError) as error:
        record.update(status="evaluation failure", reason=f"{type(error).__name__}: {error}")
    record["total_runtime_seconds"] = time.perf_counter() - started
    return record


def campaign(seed, n):
    """Plan using observational training only, then call experiment oracle.

    The candidate list and parameters stay fixed. This release's heuristic is
    unweighted candidate disagreement, so it repeats the highest ranked plan.
    Random chooses uniformly with replacement from the same admissible list.
    """
    world = make_world("equivalence", seed=seed, n=n)
    data, nodes = world["data"], world["nodes"]
    result = pc_stable(data, nodes, **PC)
    models, candidate_info = fit_candidates(result, data, nodes, "pc")
    out = {"seed": seed, "n": n, "discovery_status": result["status"], "candidates": candidate_info,
           "rounds": 2, "samples_per_round": 12, "sample_budget_per_strategy": 24,
           "training_digest": digest(data)}
    if not models:
        return dict(out, status="unavailable: no complete discovery candidates")
    ranked = rank_interventions(models, data, candidate_set_complete=candidate_info["complete"])
    rng = np.random.default_rng(seed + 20000)
    strategies, frozen = {}, {}
    for strategy in ("disagreement", "random"):
        c = Campaign(models, candidate_set_complete=candidate_info["complete"])
        chosen = [ranked[0]] * 2 if strategy == "disagreement" else [ranked[int(rng.integers(len(ranked)))] for _ in range(2)]
        plans = [c.freeze({choice["variable"]: choice["value"]}, 12, choice["score"]) for choice in chosen]
        strategies[strategy], frozen[strategy] = c, plans
    # All candidate snapshots, choices, scores and sample budgets now exist.
    # Only this subsequent evaluator/oracle block accesses simulator truth.
    truth = world["truth"]
    out["planned_before_oracle"] = True
    out["frozen_plans"] = frozen
    out["admissible_interventions"] = ranked
    out["candidate_graphs"] = [model.graph.to_dict() for model in models]
    out["true_graph_candidate_indices_evaluation_only"] = [i for i, model in enumerate(models) if model.graph == truth.graph]
    for strategy, c in strategies.items():
        for round_number, plan in enumerate(frozen[strategy]):
            # Common base noise across strategies reduces paired comparison noise.
            batch = truth.simulate(plan["n"], seed + 30000 + round_number, plan["intervention"])
            c.update(plan, batch, f"{strategy}-{seed}-{n}-{round_number}")
    # Fresh, common held-out outcomes under EVERY allowed intervention. None were
    # available to selection or weight updates. Predictive density is per row.
    scores = defaultdict(list)
    heldout = []
    for index, proposal in enumerate(ranked):
        intervention = {proposal["variable"]: proposal["value"]}
        rows = truth.simulate(128, seed + 40000 + index, intervention)
        heldout.append({"intervention": intervention, "seed": seed + 40000 + index, "n": 128, "data_digest": digest(rows)})
        truth_logs = predictive_log_scores([truth], [1.], rows, intervention)
        for strategy, c in strategies.items():
            logs = predictive_log_scores(models, c.weights, rows, intervention)
            scores[strategy].extend((truth_logs - logs) / (len(nodes) - 1))
        prior_logs = predictive_log_scores(models, np.ones(len(models)) / len(models), rows, intervention)
        scores["before_experiments"].extend((truth_logs - prior_logs) / (len(nodes) - 1))
    out["status"] = "complete"
    out["heldout_batches"] = heldout
    out["heldout_excess_nll_per_nonintervened_variable"] = {key: float(np.mean(values)) for key, values in scores.items()}
    out["campaigns"] = {strategy: {"weights": c.weights.tolist(), "history": c.history} for strategy, c in strategies.items()}
    return out


def summarize(results):
    groups = defaultdict(list)
    for row in results["discovery"]:
        key = f'{row["method"]}/' + ("standardized" if row["standardize"] else "original" if row["method"] == "notears" else "scale-invariant")
        groups[key].append(row)
    summary = {}
    for name, rows in sorted(groups.items()):
        entry = {"runs": len(rows), "statuses": dict(Counter(row["status"] for row in rows)),
                 "runtime_seconds_sum": sum(row["runtime_seconds"] for row in rows if "runtime_seconds" in row),
                 "failures_or_incomplete": sum(row["status"] != "complete" for row in rows)}
        for container, metrics in (("graph_metrics", ["skeleton_precision", "skeleton_recall", "skeleton_f1", "cpdag_state_error", "unresolved_directions", "conflicting_directions"]),
                                   ("prediction_metrics", ["intervention_mean_nrmse", "intervention_covariance_nrmse"])):
            for metric in metrics:
                vals = [row[container][metric] for row in rows if container in row]
                entry[metric + "_mean"] = float(np.mean(vals)) if vals else None
                entry[metric + "_evaluated_runs"] = len(vals)
        for metric in ("compelled_correct", "compelled_predicted", "compelled_true", "compelled_reversed"):
            entry[metric + "_sum"] = sum(row["graph_metrics"][metric] for row in rows if "graph_metrics" in row)
        summary[name] = entry
    return summary


def markdown(results):
    lines = ["# Measured Meridian benchmark", "", f'Generated UTC: {results["environment"]["generated_utc"]}', "",
             "Serial local execution; no hyperparameter search. See `docs/EVALUATION.md` for definitions and limits.", "",
             "| Method | Runs | Complete | Skeleton F1 | CPDAG state error | do-mean NRMSE | do-cov NRMSE | Runtime (s) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for method, row in results["summary"].items():
        vals = [row[key] for key in ("skeleton_f1_mean", "cpdag_state_error_mean", "intervention_mean_nrmse_mean", "intervention_covariance_nrmse_mean", "runtime_seconds_sum")]
        text = [f"{value:.4f}" if value is not None else "unavailable" for value in vals]
        lines.append(f'| {method} | {row["runs"]} | {row["statuses"].get("complete", 0)} | ' + " | ".join(text) + " |")
    lines += ["", "Graph metrics include inspectable incomplete outputs; intervention metrics only include complete usable fits. Every metric denominator and failure reason is in the JSON.", "", "## Experiment campaigns", "",
              "Two rounds × 12 observations = 24 experimental observations per strategy. Fixed observationally fitted candidates; common held-out batches across strategies. Lower held-out excess negative log likelihood is better; finite-sample estimates may be negative.", "",
              "| Seed | Training n | Candidates | Prior excess NLL | Disagreement | Random |", "|---|---:|---:|---:|---:|---:|"]
    for row in results["campaigns"]:
        if row["status"] == "complete":
            scores = row["heldout_excess_nll_per_nonintervened_variable"]
            lines.append(f'| {row["seed"]} | {row["n"]} | {row["candidates"]["count"]} | {scores["before_experiments"]:.5f} | {scores["disagreement"]:.5f} | {scores["random"]:.5f} |')
        else:
            lines.append(f'| {row["seed"]} | {row["n"]} | unavailable | {row["status"]} | — | — |')
    lines += ["", "## Failure accounting", ""]
    for method, row in results["summary"].items():
        lines.append(f'- {method}: {json.dumps(row["statuses"], sort_keys=True)}.')
    lines += ["", "The hidden-confounder demonstration is recorded separately. There is no observed-variable DAG ground truth, so observational CPDAG recovery metrics are intentionally omitted for that violation case.", "",
              f'Total wall time: {results["environment"]["wall_seconds"]:.2f} s. Peak process resident memory: {results["environment"]["peak_rss_mib"]:.2f} MiB (high-water mark, includes imports).', ""]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("benchmarks/results/compact.json"))
    args = parser.parse_args()
    started = time.perf_counter()
    seeds, samples, noises = ([7], [200], ["equal"]) if args.pilot else ([7, 19, 41], [200, 800], ["equal", "unequal", "wide"])
    results = {"schema_version": 1, "preset": "pilot" if args.pilot else "compact-v1", "discovery": [], "campaigns": [], "hidden_violation": [],
               "configuration": {"seeds": seeds, "sample_sizes": samples, "noise": noises, "d": 5, "edge_probability": .25,
                                 "rescaling": SCALES.tolist(), "pc": PC, "notears": NOTEARS,
                                 "threads": {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")}}}
    for seed in seeds:
        for n in samples:
            for noise in noises:
                truth = seeded_model(seed=seed, d=5, noise=noise, edge_probability=.25)
                base = truth.simulate(n, seed + 10000)
                for rescaled in (False, True):
                    scales = SCALES if rescaled else np.ones(5)
                    model = truth.to_original_units(np.zeros(5), scales)
                    data = base * scales
                    for method, standardize in (("pc", True), ("notears", True), ("notears", False)):
                        row = run_discovery(model, data, model.nodes, method, standardize)
                        row.update(seed=seed, n=n, noise=noise, rescaled=rescaled, data_digest=digest(data), true_graph=model.graph.to_dict())
                        results["discovery"].append(row)
                        print(f'{seed=} {n=} {noise=} {rescaled=} {method=} {standardize=} status={row["status"]}', flush=True)
            results["campaigns"].append(campaign(seed, n))
    for seed in seeds:
        world = make_world("hidden", seed=seed, n=800)
        truth = LinearSCM.from_dict(world["truth"]["model"])
        for method in ("pc", "notears"):
            row = run_discovery(truth, world["data"], world["nodes"], method)
            row.update(seed=seed, n=800, violated_assumption="causal sufficiency", truth_has_no_direct_observed_edge=True,
                       warning="This is simulator knowledge, not a learner diagnosis.")
            results["hidden_violation"].append(row)
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    results["environment"] = {"python": platform.python_version(), "platform": platform.platform(), "machine": platform.machine(),
                              "numpy": importlib.metadata.version("numpy"), "scipy": importlib.metadata.version("scipy"),
                              "generated_utc": datetime.now(timezone.utc).isoformat(), "wall_seconds": time.perf_counter() - started,
                              "peak_rss_mib": usage / (1024 ** 2 if platform.system() == "Darwin" else 1024)}
    results["summary"] = summarize(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    args.output.with_suffix(".md").write_text(markdown(results))
    print(f'Wrote {args.output}; wall={results["environment"]["wall_seconds"]:.2f}s peak_rss={results["environment"]["peak_rss_mib"]:.2f}MiB')


if __name__ == "__main__":
    main()
