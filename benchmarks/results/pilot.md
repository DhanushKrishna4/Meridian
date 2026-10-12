# Measured Meridian benchmark

Generated UTC: 2026-10-09T08:00:44.350124+00:00

Serial local execution; no hyperparameter search. See `docs/EVALUATION.md` for definitions and limits.

| Method | Runs | Complete | Skeleton F1 | CPDAG state error | do-mean NRMSE | do-cov NRMSE | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| notears/original | 2 | 2 | 0.8333 | 0.5000 | 0.0555 | 0.0487 | 0.1142 |
| notears/standardized | 2 | 0 | 0.0000 | 1.0000 | unavailable | unavailable | 0.0208 |
| pc/scale-invariant | 2 | 2 | 1.0000 | 0.0000 | 0.1010 | 0.0567 | 0.0029 |

Graph metrics include inspectable incomplete outputs; intervention metrics only include complete usable fits. Every metric denominator and failure reason is in the JSON.

## Experiment campaigns

Two rounds × 12 observations = 24 experimental observations per strategy. Fixed observationally fitted candidates; common held-out batches across strategies. Lower held-out excess negative log likelihood is better; finite-sample estimates may be negative.

| Seed | Training n | Candidates | Prior excess NLL | Disagreement | Random |
|---|---:|---:|---:|---:|---:|
| 7 | 200 | 6 | 0.13912 | 0.03627 | 0.03719 |

## Failure accounting

- notears/original: {"complete": 2}.
- notears/standardized: {"numerical failure": 2}.
- pc/scale-invariant: {"complete": 2}.

The hidden-confounder demonstration is recorded separately. There is no observed-variable DAG ground truth, so observational CPDAG recovery metrics are intentionally omitted for that violation case.

Total wall time: 0.40 s. Peak process resident memory: 72.88 MiB (high-water mark, includes imports).
