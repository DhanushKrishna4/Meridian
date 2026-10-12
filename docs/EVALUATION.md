# Evaluation and reproducibility

Meridian separates mathematical correctness, agreement with external implementations, finite-sample recovery, and browser execution. Passing one does not establish the others. The numerical evaluation described here runs locally and serially; it uses no remote computation or hyperparameter search.

## Reproduce the native checks

From the repository root, install the tested native dependencies into a virtual environment. `requirements-dev.txt` pins NumPy 2.4.2, SciPy 1.17.1, pytest 8.4.2 and build tooling. The recorded run used Python 3.14.3 on arm64 macOS. The browser has its own smaller, separately pinned Pyodide environment.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q

# Optional native references; these dependencies are never sent to the browser.
.venv/bin/python -m pip install -r tests/reference/requirements.txt
MPLCONFIGDIR=/tmp/meridian-mpl XDG_CACHE_HOME=/tmp/meridian-cache \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python -m pytest tests/reference -q

# Preserve external-reference measurements and settings.
PYTHONPATH=src MPLCONFIGDIR=/tmp/meridian-mpl XDG_CACHE_HOME=/tmp/meridian-cache \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python tests/reference/checks.py

# Compact benchmark; runs sequentially and writes both JSON and Markdown.
PYTHONPATH=src OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  .venv/bin/python benchmarks/run.py
```

The normal test suite reports optional causal-learn tests as skipped if it is absent; a skipped comparison is not verification. The artifact generator requires the exact reference version and fails if it is absent or mismatched. `--pilot` selects a smaller benchmark and can be combined with `--output benchmarks/results/pilot.json`; its results are separate from the compact run.

## Correctness layers

- Graph and PC exact-oracle tests independently enumerate active paths, labeled DAGs, and equivalence classes for small graphs. They test d-separation, compelled edges, consistent extensions, collider/orientation conflicts, and budget exhaustion. An oracle supplies population independence, so these tests do not assess sampling error.
- Numerical tests cover Fisher-Z degrees of freedom, invalid/rank-deficient input, NOTEARS finite-difference gradients, analytic Gaussian moments versus seeded simulation, total effects, backdoor checks, and original-unit transformations.
- Exact equivalence fixtures verify the same observational covariance for the three chain/fork models, differing intervention means/covariances, and the abduct–act–predict counterfactual `(1,1,1) → (1,0,0.2)` under `do(Y=0)` in the forward model.
- Experiment tests cover likelihood updates with replaced mechanisms excluded, frozen plans, duplicate-batch rejection, fixed model parameters, and truth-free recommendation inputs. These are distinct from proving that a disagreement heuristic is optimal.
- Browser checks exercise actual Pyodide operations and interface behavior. See the project status and browser scripts for their separate results; native benchmark runtimes do not measure browser latency.

## External reference measurements

The checked-in [reference JSON](../benchmarks/results/reference.json) contains raw comparisons, data hashes, exact settings, library versions, and timings. The current run passed **9 reference tests** in **1.27 seconds**; the separate artifact-generation run took **1.73 seconds** including imports.

The development-only reference is [causal-learn 0.1.4.4](https://pypi.org/project/causal-learn/0.1.4.4/), pinned in `tests/reference/requirements.txt`. It is not an application dependency. The tests use its Fisher-Z implementation and PC with `stable=True`, `alpha=0.01`, `uc_rule=0` (separating-set collider orientation), and `uc_priority=2` (prioritize existing colliders). Missing-value processing and background knowledge are off.

For Gaussian Fisher-Z, all 240 combinations of tested pairs and conditioning subsets in one six-variable, 600-row seeded matrix agree to maximum absolute p-value error **2.89e-15** (test tolerance `2e-12`). For PC, four fixed fixtures—equivalence, collider, observed confounding, and a six-variable seeded sparse world—use 2,000 observations at seed 113. The returned directed and undirected graphs agree exactly after translating endpoint encodings. These are conflict-free fixtures. Meridian retains its own documented first-separating-set and conflict-proposal rules; the comparison does **not** claim general equivalence to causal-learn's handling of conflicting finite-sample evidence.

Linear NOTEARS is compared with the [author's implementation](https://github.com/xunzheng/notears/blob/4a9ab19fe502e392503da331773c5223d82d3666/notears/linear.py), vendored unchanged at commit `4a9ab19fe502e392503da331773c5223d82d3666`. `tests/reference/vendor/manifest.json` records its source URL and SHA-256; tests verify both code and retained license hashes before loading it. Author `W[parent,child]` is transposed to Meridian `B[child,parent]`.

Three 2,000-row fixtures at seed 113 use centered original units, squared loss, `lambda1=0.1`, edge threshold `0.2`, 30 outer steps and `h_tol=1e-8`. The unmodified author code uses SciPy's default inner-solver settings; Meridian uses its documented stricter tolerances and 1,000 inner iterations for these reference checks. All three selected supports agree, all Meridian runs complete, and maximum selected-coefficient differences are **0.00198**, **0.00130**, and **0.00335** (absolute comparison tolerance `0.03`). This is approximate numerical agreement, not bitwise optimizer parity or a claim of global optimality. Reference code exists only under tests.

## Compact benchmark design

The measured [compact JSON](../benchmarks/results/compact.json) and its [generated Markdown summary](../benchmarks/results/compact.md) preserve all **108 discovery runs**, **6 paired experiment campaigns**, and **6 hidden-confounding runs**. The earlier pilot remains available. No failed result was discarded, retried until success, or replaced in these artifacts.

The fixed design is three graph seeds `[7, 19, 41]`, sample sizes `[200, 800]`, five variables, edge probability `0.25`, and three exogenous-noise regimes. Equal-noise variances are one; unequal and wide regimes draw variances as `exp(Uniform(-1.2,1.2))` and `exp(Uniform(-2.5,2.5))`. Edge coefficients have random signs and magnitudes in `[0.35,0.95]`; topological order and labels are shuffled. Every dataset is also rescaled by `[0.2,0.5,1,2,5]`. PC and both NOTEARS preprocessing choices receive the same paired datasets.

PC uses `alpha=0.01`, conditioning depth at most 3, 10,000 tests, and a 10-second budget. NOTEARS uses `lambda1=0.1`, threshold `0.2`, 30 outer steps, 150 inner iterations per solve, `h_tol=1e-8`, and a 20-second budget. Its two modes are centered original units and standardized training data. Candidate SCMs use the same observational training rows and OLS fitting; NOTEARS penalized weights are never substituted for refitted coefficients. Prediction evaluation uses simulator moments only after fitting.

**This is a small implementation benchmark, not a representative ranking of discovery methods.** The three graph seeds produce only **1, 0, and 2 edges**, respectively. Noise/sample-size/rescaling combinations reuse those structures, and rescaling pairs are correlated copies. Thus 108 runs are not 108 independent graph draws. Sparse empty/easy graphs help explain perfect PC recovery here. There are no confidence intervals or claims of statistical superiority; broader graph families and many more independently generated graphs would be required.

### Metric definitions

Skeleton precision/recall/F1 compare unordered adjacencies. If a denominator is empty, the score is one only when the corresponding correct set is also empty; otherwise zero. A NOTEARS DAG is converted to its induced CPDAG before observational-equivalence comparison, so another member of the true equivalence class is not penalized solely for its arbitrary reversible arrows.

`cpdag_state_error` counts unordered pairs whose states differ among absent, undirected, forward, and reverse. A reversal counts once. This is an explicitly defined graph-state distance, not an unspecified structural Hamming-distance convention. Compelled precision/recall, reversed compelled edges, true compelled edges left unresolved, unresolved edges, and conflicts are recorded separately. Zero-denominator compelled precision/recall is `null`, not silently one. Raw DAG arrow recovery is additionally available but is not observational identification.

Intervention errors compare a uniform mixture of available fitted candidates against true analytic moments, over each variable clamped at its training mean and mean ± one training standard deviation. Clamped coordinates are excluded. Means are normalized by fixed training SD; covariance entries by the outer product of those SDs. Candidate mixture covariance includes between-model variation in means. The reported NRMSE is the square root of the mean squared normalized entries, then the summary averages per-run values. A uniform candidate list is not a posterior or a complete identified set when enumeration is truncated.

Graph metrics can describe valid, inspectable incomplete outputs. Prediction metrics require a complete discovery result and usable candidate fit, so their denominators can differ. A cyclic NOTEARS result is not replaced by an empty graph for scoring. All per-metric denominators, statuses and reasons are stored in JSON.

### Measured results and failure accounting

| Method | Complete / runs | Skeleton F1 | CPDAG state error | Mean NRMSE | Covariance NRMSE |
|---|---:|---:|---:|---:|---:|
| PC | 36 / 36 | 1.0000 | 0.0000 | 0.0566 | 0.0424 |
| NOTEARS, original units | 36 / 36 | 0.8251 | 1.2500 | 0.1077 | 0.0963 |
| NOTEARS, standardized | 32 / 36 | 0.6778 | 1.1667 | 0.1590 | 0.1588 |

The standardized NOTEARS failures occur for seed 7, n=200, equal/unequal noise, in both rescaling variants. All four report **nonfinite optimizer objective or gradient**; their retained inspectable graphs contribute to graph metrics, but they contribute no fitted intervention prediction. They remain failures despite finite last-completed iterates. These measurements do not establish universal reliable convergence.

The original-unit NOTEARS skeleton F1 changes from **0.9370** before rescaling to **0.7132** afterward; induced-CPDAG error changes from **0.7778** to **1.7222**. In this benchmark, standardized NOTEARS and PC summaries are unchanged under those positive rescalings. Standardization removes that specific input-units difference but does not make linear Gaussian direction selection causally identified. See [Beware of the Simulated DAG!](https://proceedings.neurips.cc/paper_files/paper/2021/hash/e987eff4a7c7b7e580d659feb6f60c1a-Abstract.html) for the motivation for reporting scale conditions.

The measured compact run used Python 3.14.3, NumPy 2.4.2, SciPy 1.17.1, arm64 macOS, and single-thread BLAS environment settings. Total wall time was **2.97 s** and process peak RSS **74.80 MiB**. RSS is a high-water mark including Python/imports, not the application browser's total memory. Individual method times sum discovery timing only; the total also includes fitting, metrics and campaigns. Hardware, library and load differences affect timings.

## Experiment comparison and limits

Each paired campaign discovers and fits candidates using only the equivalence world's observational training rows. It freezes the candidate set, parameters, two intervention choices, scores, and sample counts before consulting simulator truth. Both strategies receive two batches of 12 rows (24 experimental observations). The disagreement strategy repeats its best intervention because this release's unweighted candidate disagreement score does not change when predictive-support weights change. Random chooses uniformly with replacement from the same admissible proposals. This is a transparent fixed-candidate comparison, not an adaptive expected-information-gain experiment.

Weights are updated once per experimental batch using only the nonreplaced structural conditional densities. Evaluation then uses fresh, common held-out batches of 128 observations under every admissible intervention. Held-out rows are never given to selection or support updates. The metric is mean `log p_truth - log p_candidate_mixture` per nonintervened variable; lower is better and finite-sample estimates can be negative. The paired strategy experiments use common base-noise seeds, and held-out batches/data hashes are recorded.

The six campaigns use 3–6 fitted candidates. In the measured set disagreement has lower excess NLL by about 0.00092 and 0.04327 in two campaigns; two are exactly tied and two differ by less than 9e-9. Each strategy improves on its pre-experiment mixture. This is not evidence of broad superiority with only three seeds and one world. The n=200, seed-7 discovery contains six candidates rather than the population equivalence class's three; finite-sample candidate errors are retained rather than replaced with truth. Normalized plug-in likelihood weights are relative predictive support, not Bayesian posterior causal probabilities.

## Assumption violations

The hidden-common-cause world supplies only its two observed columns to discovery. The evaluator alone knows the hidden model. Both methods' output, completion status and interventional prediction errors are recorded separately. An observed-variable DAG is not the true generative structure here, so no DAG/CPDAG-recovery score is invented. A correct-looking intervention on one fixture cannot establish that a method detected a hidden confounder. The application labels the sufficiency violation as simulator knowledge.

## Interpretation boundary

These results establish tested behavior on the included fixtures and bounded experiments. They do not establish latent-variable identification, nonlinear validity, unique observational identification, calibrated causal probabilities, broad generalization, or optimal experiment selection. PC's causal interpretation still requires causal Markov, faithfulness, sufficiency, independent observations, and valid conditional-independence tests. NOTEARS supplies a score-selected candidate under explicit preprocessing and optimization settings. Interventions and counterfactuals remain conditional on the selected structural model.
