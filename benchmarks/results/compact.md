# Measured Meridian benchmark

Generated UTC: 2026-10-09T08:01:14.927032+00:00

Serial local execution; no hyperparameter search. See `docs/EVALUATION.md` for definitions and limits.

| Method | Runs | Complete | Skeleton F1 | CPDAG state error | do-mean NRMSE | do-cov NRMSE | Runtime (s) |
|---|---:|---:|---:|---:|---:|---:|---:|
| notears/original | 36 | 36 | 0.8251 | 1.2500 | 0.1077 | 0.0963 | 1.5622 |
| notears/standardized | 36 | 32 | 0.6778 | 1.1667 | 0.1590 | 0.1588 | 0.8908 |
| pc/scale-invariant | 36 | 36 | 1.0000 | 0.0000 | 0.0566 | 0.0424 | 0.0227 |

Graph metrics include inspectable incomplete outputs; intervention metrics only include complete usable fits. Every metric denominator and failure reason is in the JSON.

## Experiment campaigns

Two rounds × 12 observations = 24 experimental observations per strategy. Fixed observationally fitted candidates; common held-out batches across strategies. Lower held-out excess negative log likelihood is better; finite-sample estimates may be negative.

| Seed | Training n | Candidates | Prior excess NLL | Disagreement | Random |
|---|---:|---:|---:|---:|---:|
| 7 | 200 | 6 | 0.13912 | 0.03627 | 0.03719 |
| 7 | 800 | 3 | 0.08868 | 0.00059 | 0.04386 |
| 19 | 200 | 3 | 0.07413 | 0.00387 | 0.00387 |
| 19 | 800 | 3 | 0.07854 | -0.00114 | -0.00114 |
| 41 | 200 | 3 | 0.10036 | 0.01074 | 0.01074 |
| 41 | 800 | 3 | 0.08868 | 0.00504 | 0.00504 |

## Failure accounting

- notears/original: {"complete": 36}.
- notears/standardized: {"complete": 32, "numerical failure": 4}.
- pc/scale-invariant: {"complete": 36}.

The hidden-confounder demonstration is recorded separately. There is no observed-variable DAG ground truth, so observational CPDAG recovery metrics are intentionally omitted for that violation case.

Total wall time: 2.97 s. Peak process resident memory: 74.80 MiB (high-water mark, includes imports).
