Build **Meridian**, a complete Python causal-machine-learning laboratory with an interactive GitHub Pages application.

The central experience is: investigate a system from observations, discover which causal relationships remain possible, choose an experiment that distinguishes competing explanations, and explore interventions and counterfactuals under explicit models.

Implement the project, run it, test it, and deliver a working application. Do not stop at scaffolding, a design document, a mock dashboard, or interfaces backed by fabricated results.

## 1. Constraints and priorities

These constraints govern the entire project:

- Development machine: Apple M3 MacBook Air with 8 GB unified memory.
- All development, computation, experiments, and validation must run locally.
- No cloud GPUs, rented computers, paid APIs, API keys, or paid services.
- The deployed application must work entirely as a static GitHub Pages site.
- No Python server, inference service, database backend, or authentication requirement.
- Python must implement the actual graph algorithms, statistical tests, discovery methods, structural models, causal queries, and experiment selection.
- Run the same Python package natively and inside the browser through Pyodide.
- JavaScript/TypeScript should handle the interface, visualization, worker communication, and local persistence.
- Use small numerical problems. No deep neural networks or large training runs are required.
- Every advertised feature must work, and every reported result must come from actual computation.

Prioritize scientific correctness, clear distinctions between evidence and assumptions, reproducibility, usability, and visual quality.

Make reasonable implementation decisions and proceed through milestones without repeatedly requesting routine approval. Respect existing repository instructions and preserve unrelated work.

If an external limitation blocks verification, complete the independent work and report precisely what remains unverified.

## 2. Product experience

Meridian should support five connected activities:

1. **Observe:** inspect data from a simulated system or an uploaded CSV.
2. **Discover:** compare two causal-discovery approaches and inspect their evidence.
3. **Compare explanations:** explore alternative graphs compatible with the observations.
4. **Intervene:** choose an experiment, predict its outcomes, and compare predictions with new evidence.
5. **Ask “what if?”:** compute counterfactuals under an explicitly selected structural model.

The memorable demonstration must show:

- Several causal graphs explain the same observational distribution.
- Those graphs predict different consequences of an intervention.
- New experimental evidence changes their relative support.

This must be a real numerical workflow, not a scripted animation with predetermined conclusions.

## 3. Scientific scope and claim boundaries

Keep the required discovery scope deliberately precise:

- Continuous numerical variables.
- Complete observations.
- Acyclic structural models.
- Linear relationships.
- Gaussian additive noise.
- Modest graphs and datasets.

For PC-based causal interpretation, explicitly state assumptions including the causal Markov condition, faithfulness, causal sufficiency, and independent sampling.

Observational data generally do not identify a unique causal DAG. Preserve unresolved directions.

Separate these concepts throughout the code, documentation, exports, and interface:

- Statistical association.
- Conditional-independence evidence.
- Observational equivalence.
- A fitted candidate DAG.
- An assumed structural causal model.
- An intervention prediction under that model.
- A counterfactual conditional on that model.
- Ground truth known only in a simulated example.

Do not present:

- A NOTEARS-selected direction as observational proof of causation.
- A p-value as the probability that an edge exists.
- Bootstrap selection frequency as a posterior causal probability.
- A range across a sampled candidate list as a complete identified set.
- Agreement among candidate models as proof that all possible models agree.
- A simulator’s known hidden confounder as something the learner detected automatically.

Do not implement FCI, general latent-variable identification, nonlinear discovery, missing-data correction, time-series causality, or unrestricted do-calculus in the required release.

Include assumption-violation demonstrations that show the limits of the supported methods.

## 4. Architecture and dependency boundaries

Create an installable Python package, using an import name such as `meridian_causal`.

Suggested organization:

- `src/meridian_causal/graphs/`
- `src/meridian_causal/statistics/`
- `src/meridian_causal/discovery/`
- `src/meridian_causal/scm/`
- `src/meridian_causal/experiments/`
- `src/meridian_causal/evaluation/`
- `src/meridian_causal/serialization/`
- `src/meridian_causal/cli.py`
- `tests/`
- `examples/`
- `benchmarks/`
- `web/`
- `docs/`
- `.github/workflows/`

Use NumPy and SciPy for numerical primitives, optimization, matrix exponentials, and probability calculations.

Implement Meridian’s graph algorithms and discovery logic yourself. Do not make the application a wrapper around a causal-discovery package.

Established packages such as causal-learn may be used as development-only references. Record their versions and configuration when comparing results.

Keep the browser’s Python dependencies small. Do not require pandas, PyTorch, R, or Graphviz in the deployed runtime.

Use a modest frontend stack such as TypeScript, Vite, React, and a suitable graph-rendering library.

The graph renderer must display results supplied by Python. It must not contain a second implementation of causal reasoning.

Pin a tested dependency set and include reproducible installation instructions.

## 5. Define graph and structural-model semantics first

Use stable variable IDs independent of display order.

Represent directed and undirected edges explicitly. Do not encode every intermediate graph as an ordinary DAG.

Choose and document one matrix convention everywhere. Use:

`B[child, parent] = structural coefficient`

For a column-vector observation:

`x = b + Bx + u`

For ordinary supported models:

`u ~ Normal(0, diag(noise_variances))`

Keep this convention consistent in simulation, fitting, plotting, serialization, and reference comparisons.

Required graph utilities:

- Parents, children, ancestors, and descendants.
- Cycle detection and topological ordering.
- Skeleton extraction.
- Unshielded-collider extraction.
- d-separation.
- DAG-to-CPDAG conversion.
- Validation of partially directed results.
- Consistent DAG extension.
- Bounded enumeration of consistent extensions.

Reject self-loops, duplicate IDs, invalid endpoints, and invalid graph states.

A finite-sample discovery result may be inconsistent. Represent that explicitly.

An orientation conflict must not be drawn as if it proved latent confounding.

## 6. Observational data and preprocessing

Support:

- Built-in synthetic datasets.
- Locally uploaded CSV files containing selected numerical columns.

Suggested interactive bounds:

- 2–15 observed variables.
- Up to 5,000 rows.
- Sparse 5–8-variable examples by default.
- A configurable upload limit, initially around 5 MiB.

Before discovery, report:

- Row and column counts.
- Missing and nonfinite values.
- Constant columns.
- Duplicate or nearly dependent columns.
- Basic scale and conditioning diagnostics.

Do not silently impute missing values, drop rows, or add numerical regularization that changes the statistical procedure.

Unsupported input should produce an actionable explanation.

Split data before fitting preprocessing or selecting settings. Preserve separate discovery/training, validation, and evaluation roles where relevant.

Store preprocessing parameters and transform predictions and interventions back to original units.

Expose whether NOTEARS uses centered original units or standardized data. Changing scales can change its result; do not hide that behavior.

CSV data must remain in the browser. No uploads to an external analysis service.

## 7. Discovery method A: PC-stable

Implement a documented PC-stable pipeline using Gaussian partial correlations and Fisher’s Z tests.

Follow the [PC-stable research](https://www.jmlr.org/beta/papers/v15/colombo14a.html) and clearly identify the exact collider-orientation variant implemented.

Required behavior:

- Freeze adjacency sets at each conditioning depth.
- Consider eligible conditioning sets from both endpoints.
- Cache conditional-independence calculations.
- Distinguish an empty separating set from the absence of a recorded separating set.
- Use deterministic ordering based on stable variable IDs.
- Record the evidence responsible for every removed edge.
- Record the premises of collider and subsequent orientation decisions.

Implement the applicable Meek orientation rules and closure using a cited, tested formulation. Consult [Meek’s paper](https://arxiv.org/abs/1302.4972).

Collect and resolve orientation proposals explicitly. Do not let incidental iteration order silently resolve opposing proposals.

PC-stable stabilizes skeleton discovery; do not claim that every orientation choice is automatically order-independent. If implementing a conservative extension, name it accurately and handle ambiguous triples according to that algorithm.

For Fisher’s Z:

- Use the correct conditioning-set-dependent degrees of freedom.
- Validate sample size and conditioning-matrix rank.
- Handle numerical roundoff deliberately.
- Treat singular or otherwise invalid tests as invalid, not as independence.
- Explain that failing to reject dependence is not proof of independence.

Use bounded conditioning depth, test count, and execution time.

If a budget prevents completion, report an incomplete search. Do not present it as a fully searched CPDAG.

Validate orientation consistency, acyclicity of directed portions, and existence of a consistent extension. Only label a result a CPDAG when its structural requirements are satisfied.

The interface must allow replaying the actual discovery trace.

## 8. Discovery method B: linear NOTEARS

Implement linear NOTEARS with squared reconstruction loss and an L1 sparsity penalty.

With observations stored in rows and the chosen coefficient convention:

`loss(B) = ||X - X @ B.T||² / (2n)`

Use:

`h(B) = trace(expm(B ∘ B)) - d`

Enforce a zero diagonal. Implement the augmented-Lagrangian procedure and the smooth optimization needed for L1 splitting.

Finite-difference-check the reconstruction and acyclicity gradients.

Use the [original paper](https://arxiv.org/abs/1803.01422) and [author implementation](https://github.com/xunzheng/notears/blob/master/notears/linear.py) as references, accounting explicitly for the transposed matrix convention.

Expose optimization progress and record:

- Loss and penalty.
- Constraint residual.
- Iteration counts.
- Convergence status.
- Termination reason.
- Preprocessing.
- Edge threshold.

A small acyclicity residual is not sufficient to prove that thresholded support is a DAG. Always perform an explicit graph check.

If thresholding leaves a cycle, report an invalid candidate. Optional cycle-removal postprocessing must be separately labeled and disclose every removed edge.

Keep raw optimization output distinct from the selected graph and any subsequently refitted structural equations.

Explain scale sensitivity and benchmark it. Consult the findings in [“Beware of the Simulated DAG!”](https://proceedings.neurips.cc/paper_files/paper/2021/hash/e987eff4a7c7b7e580d659feb6f60c1a-Abstract.html).

## 9. Fit explicit structural causal models

Discovery outputs and usable structural models must be separate objects.

For a selected valid DAG, fit each variable on its parents using training observations, with:

- An intercept.
- Stable least-squares computation.
- Explicit residual-variance estimation.
- Rank and conditioning checks.
- Positive, validated noise variances.

Document the estimator and any numerical variance floor.

Do not silently fit a cyclic graph.

Keep fitted coefficients separate from NOTEARS’ penalized weights. If refitting occurs, make that visible.

For partially directed graphs, require selection of a valid consistent extension before computing a single-model causal answer.

Allow users to edit an assumed DAG and its coefficients in a separate model-building mode. Label such models as user-specified.

Do not quietly incorporate manually edited directions into the discovery result.

If the selected graph or data changes, invalidate affected fits, query results, and experiment rankings.

## 10. Observation versus intervention

Implement analytic mean and covariance calculations for supported linear Gaussian models, plus seeded simulation for validation.

Provide distinct operations for:

- Observational conditioning: `P(Y | X = x)`.
- Intervention: `P(Y | do(X = x))`.

An intervention replaces the selected structural equation with a fixed value. It does not merely filter observations or condition a Gaussian.

For interventions on variables `I`, solve the remaining system over variables `N`:

`M = Identity - B[N, N]`

`mean_N = solve(M, b_N + B[N, I] @ intervention_values)`

Compute covariance using linear solves and the nonintervened noise covariance. Avoid explicit matrix inversion.

Clamped variables have zero variance. Handle this without passing a singular full covariance into calculations that require a positive-definite matrix.

Support one or several simultaneous hard interventions in the query engine. The experiment recommender may be limited to one-variable interventions.

Display:

- Observational and interventional distributions.
- Changes in means and variances.
- Affected descendants.
- Model equations replaced by the intervention.
- Original units.

Implement total linear effects and verify them against sums of path coefficients on small DAGs.

Also implement checking a supplied backdoor adjustment set for a selected DAG. If searching for valid sets, bound the search and distinguish “none found within the budget” from “none exist.”

Any causal interpretation must identify the selected model and its assumptions.

## 11. Counterfactuals

Implement abduction, action, and prediction for complete observations in supported additive models, following the [structural definition of counterfactuals](https://causality.cs.ucla.edu/blog/index.php/2014/11/).

For an observed row `x` and a selected fitted model:

1. Abduct its residuals: `u = x - b - B @ x`.
2. Replace the intervened equations.
3. Propagate the remaining equations using those same residuals.

Do not resample noise. That would generate a new individual rather than a counterfactual for the observed one.

Display the factual and counterfactual values side by side, with changes highlighted.

Required checks:

- Reconstructing the factual world returns the original observation.
- Intervening at an already observed value preserves the original row.
- Non-descendants remain unchanged.
- Simple chain calculations match hand-derived answers.

Each candidate model must perform its own abduction. Do not reuse numerical residuals across differently parameterized models.

Label the result as conditional on the selected fitted SCM.

Do not apply this exact-residual procedure to incomplete rows or present it as a general solution for hidden confounding.

## 12. Alternative models and experiment selection

Implement bounded enumeration of consistent DAG extensions for small valid CPDAGs.

Each candidate must:

- Preserve compelled directions.
- Be acyclic.
- Preserve the skeleton.
- Introduce no incompatible unshielded colliders.
- Be deduplicated.

Bound search expansions, elapsed time, and returned candidates. Start with a candidate cap such as 128 and use smaller default graphs.

If enumeration is truncated, label the set nonexhaustive. Do not invent a total candidate count.

Fit each candidate using the same authorized observational training data.

Implement a transparent experiment-selection heuristic:

- Enumerate allowed one-variable interventions.
- Use bounded intervention values in original units.
- Predict nonintervened means and covariances under each candidate.
- Rank experiments by normalized disagreement among those predictions.
- Include both mean and covariance disagreement so zero-mean experiments are not automatically treated as uninformative.
- Use fixed training-data scales for normalization.

Call this a disagreement heuristic. Do not call it expected information gain unless that quantity is actually implemented.

The recommender must not access:

- The true generating graph.
- True structural coefficients.
- Hidden noise values.
- Future experiment outcomes.
- Evaluation-only data.

Freeze the candidate set, intervention, sample count, and score before calling the simulated experiment oracle.

For the first release, keep candidate parameters fixed during a campaign. Update relative predictive support using each new experimental batch once.

Under `do(X_j=x)`, score the nonintervened structural conditional densities. Exclude the replaced mechanism for `X_j`, while retaining its fixed value wherever it is a parent.

Use numerically stable likelihood aggregation.

Normalized plug-in likelihood weights are not automatically Bayesian model posterior probabilities. Label them accurately.

Do not concatenate intervention data into the observational PC or NOTEARS input.

For uploaded observational CSVs, recommendations are proposals for real experiments. Do not fabricate outcomes. Allow clearly labeled model simulations and separately imported measured intervention batches.

## 13. Built-in worlds

Include a small set of carefully designed worlds with explanatory walkthroughs.

### A. Same observations, different causes

Use a three-variable linear Gaussian example with:

- `X = U_X`
- `Y = 0.8 X + U_Y`
- `Z = 0.8 Y + U_Z`

Noise variances:

- `Var(U_X) = 1`
- `Var(U_Y) = 0.36`
- `Var(U_Z) = 0.36`

Its observational equivalence class includes:

- `X → Y → Z`
- `X ← Y ← Z`
- `X ← Y → Z`

Construct equivalent parameterizations and verify their observational covariance matrices agree.

With those exact parameterizations, `do(Y=1)` produces means for `(X,Z)` of:

- `(0, 0.8)`
- `(0.8, 0)`
- `(0.8, 0.8)`

At `do(Y=0)`, their means coincide, but their nonintervened covariance matrices differ. This must exercise covariance-sensitive experiment selection.

For the forward-chain observation `(1,1,1)`, the residuals are `(1,0.2,0.2)`. Its counterfactual under `do(Y=0)` is `(1,0,0.2)`.

Use exact parameters for mathematical fixtures. In the live discovery workflow, fit candidates from observations rather than giving the learner the hidden true coefficients.

### B. Collider and selection effects

Create independent causes of a shared outcome.

Show how conditioning on the outcome can induce an association between its causes, while intervening on that outcome does not have the same effect.

### C. Observed confounding

Include an observed common cause and a direct effect whose sign differs from the naive observational regression.

Show observational prediction, a valid adjustment, and the selected model’s intervention effect.

### D. Hidden-confounder failure

Use a hidden common cause of two observed variables, without a direct edge between them.

The observations are associated, but intervening on one does not change the other’s true distribution.

Reveal that the causal-sufficiency assumption was violated. Do not claim the learner diagnosed the hidden variable from observational data alone.

### E. Seeded systems

Provide a generator for sparse linear Gaussian DAGs, with randomized variable labels and several noise-scale settings.

Use these for experiments and benchmarks rather than relying exclusively on hand-picked examples.

Keep simulator truth outside learner inputs. This is an architectural boundary for honest inference, not a claim that truth embedded in a static website is cryptographically secret.

Revealing truth must not change or retroactively improve discovery results.

## 14. Uncertainty and evaluation

Keep these sources of uncertainty separate:

- Unresolved causal directions.
- Finite-sample uncertainty in fitted parameters.
- Discovery instability.
- Omitted candidates from bounded enumeration.
- Model-assumption violations.

Support bounded bootstrap runs for graph stability and selected-model effect estimates.

Label graph frequencies as bootstrap stability.

Effect intervals conditional on a chosen graph must not be described as accounting for graph uncertainty.

Run bootstrap replicates sequentially with progress and cancellation. Keep defaults modest.

For simulated benchmarks, report:

- Skeleton precision, recall, and F1.
- A clearly defined CPDAG-aware structural error.
- Correctness of compelled orientations.
- Unresolved and conflicting directions.
- DAG-level recovery separately where useful.
- Intervention prediction error.
- Runtime and failure or timeout counts.

Do not penalize every reversible direction as if observational data should determine it.

Compare intervention selection against a random admissible-intervention baseline at the same sample budget.

Use held-out experiment outcomes for evaluation. Do not choose experiments using those outcomes.

Publish a compact reproducible benchmark suite covering multiple seeds, sample sizes, unequal noise variances, and variable rescaling. Include failures and assumption-violation cases.

Do not tune against the final benchmark or claim universal causal recovery.

## 15. Interface and interaction design

Build a polished scientific workspace with the application immediately usable.

Suggested visual direction:

- Deep navy or neutral background.
- Teal accents for evidence and interventions.
- A contrasting restrained accent for model assumptions.
- Clear typography.
- Spacious graph layouts.
- Consistent visual language for directed, unresolved, selected, and conflicting edges.

Avoid a generic marketing dashboard.

A useful desktop layout:

- Dataset and question controls on the left.
- Main causal graph in the center.
- Distributions, model comparisons, and explanations on the right.
- An expandable evidence timeline below.

Provide usable narrow-screen layouts with tabs.

Required interactions:

- Select a variable to inspect its distribution.
- Select an edge to see the evidence or rule behind it.
- Replay the actual discovery process.
- Compare PC and NOTEARS results.
- Select an alternative DAG.
- Apply an intervention and inspect changed predictions.
- Run a recommended simulated experiment.
- Inspect how new observations change candidate support.
- Select a factual row and ask a counterfactual.
- Reveal simulator truth and compare results.
- Export and restore an experiment.

Place assumptions beside the results they affect. Keep detailed optimizer and statistical diagnostics in expandable inspectors.

Do not use color alone to convey edge types or status.

Support keyboard operation, accessible labels, readable contrast, reduced motion, and clear loading, empty, and error states.

## 16. Browser execution and resource limits

Run the Python package in a Pyodide worker. NumPy and SciPy are available through the [Pyodide package distribution](https://pyodide.org/en/stable/usage/packages-in-pyodide.html); pin and verify the actual versions used.

Load SciPy only when needed.

Do not require cross-origin isolation, SharedArrayBuffer, WebGPU, browser flags, or external compute.

Use bounded units of work:

- PC conditioning-depth stages or test batches.
- Bounded optimization calls.
- Individual bootstrap replicates.
- Candidate-enumeration batches.
- Individual experimental rounds.

Yield between units so the worker can process commands.

For computations that cannot cooperate promptly, provide a main-thread watchdog that can terminate and recreate the worker.

Preserve user configuration and completed results outside the worker.

Tag messages with run and worker-generation IDs. Reject stale results after cancellation or reset.

Destroy Pyodide proxies and release temporary arrays. Bound caches and trace storage.

Expose progress using real counters, not fabricated percentages.

Provide explicit statuses such as:

- Complete.
- Cancelled.
- Budget exhausted.
- Numerical failure.
- Inconsistent graph.
- Optimizer did not converge.

Do not convert any of these into a successful complete result.

Before larger local experiments, run a short pilot and measure time and memory where available. Keep default working datasets and matrices small; do not launch extensive hyperparameter searches.

## 17. Reproducibility and import/export

Export a versioned experiment containing:

- Dataset or dataset identity.
- Variable IDs and units.
- Data split and preprocessing metadata.
- Algorithm settings.
- Random seeds.
- Discovery results and completion status.
- Relevant evidence traces.
- Selected candidate graphs.
- Fitted structural models.
- Intervention history.
- Experiment-selection settings.
- Results and evaluation metadata.

Make inclusion of uploaded raw data explicit.

Use validated JSON and safe numerical array formats. Do not execute imported code or deserialize pickle.

Validate dimensions, finiteness, graph structure, array sizes, variances, IDs, and schema versions before allocation.

Cache statistical tests using dataset identity, variable IDs, conditioning sets, preprocessing, and test configuration.

Keep truth-containing simulator exports distinct from learner-only inputs.

Support deterministic replay of recorded experiment choices and outcomes. Do not regenerate a different world when replaying an existing run.

## 18. Correctness and reference tests

The project must have substantial verification beyond screenshots.

### Graph and exact-oracle tests

Exhaustively test all labeled DAGs through four vertices, plus targeted larger fixtures.

Build an independent expected-equivalence oracle by grouping DAGs with the same skeleton and unshielded colliders and identifying invariant directions.

Use exact d-separation answers to test discovery independently of statistical sampling.

Check:

- Chains, forks, colliders, and disconnected graphs.
- Meek-rule fixtures.
- Consistent extensions.
- Cycle and orientation-conflict detection.
- Variable permutations.
- Extension enumeration and truncation.
- d-separation against an independent implementation.

Do not use the same production routine to manufacture its own expected answers.

### Statistical tests

Validate partial correlations and Fisher’s Z against known covariance examples and a pinned reference implementation.

Test:

- Empty conditioning sets.
- Insufficient samples.
- Constant columns.
- Singular systems.
- Near-collinearity.
- Variable rescaling.
- Cache invalidation.

Statistical recovery tests should use multiple fixed seeds and appropriate expectations. Do not demand perfect recovery from every noisy sample.

### NOTEARS tests

Check analytical gradients with finite differences.

Compare objective and constraint values with the original implementation after accounting for matrix convention.

Test diagonal constraints, optimization failure, thresholding, and genuine cycle checks.

Include a regression case where a small acyclicity residual coexists with cyclic thresholded support.

### Structural-model tests

Compare analytic observational and intervention moments with independent seeded simulations.

Validate:

- Conditioning versus intervention.
- Direct and total effects.
- Multi-variable interventions.
- Interventions on roots and leaves.
- Fully clamped systems.
- Backdoor-set checking.
- Counterfactual reconstruction and invariance.
- Original-unit transformations.

### Experiment-selection tests

Use observationally equivalent models with analytically different intervention predictions.

Verify:

- Mean and covariance disagreement both matter.
- Intervention values respect configured bounds.
- Selection occurs before oracle outcomes exist.
- Truth objects are not accepted by learner or selector APIs.
- Experimental scoring excludes intervened mechanisms.
- Evidence is not counted twice.
- Truncated candidate sets are labeled.
- Uploaded CSV workflows do not fabricate observations.

### Browser tests

Verify native Python and browser Python agree on fixed fixtures within documented tolerances.

Test:

- Cold loading.
- CSV import.
- Discovery and cancellation.
- Stale-result rejection.
- Model fitting and queries.
- Intervention campaigns.
- Counterfactuals.
- Export/import.
- Invalid files.
- Worker recovery.
- Repeated-run resource cleanup.
- Responsive layouts.
- Production operation under a GitHub Pages repository subpath.

Serve the application over HTTP for testing.

Clearly report any unavailable browser verification. A skipped check is not a pass.

## 19. Packaging, documentation, and deployment

Deliver a fully static production build and a GitHub Pages deployment workflow.

Use repository-relative asset handling so the application works under a path such as `/Meridian/`.

Verify worker imports, Python package loading, SciPy loading, and static dataset assets.

Do not run the full benchmark suite during every website build.

Include:

- Python package metadata.
- Dependency pins and frontend lockfile.
- Development and production-preview commands.
- Core-test and reference-test commands.
- Benchmark and fixture-generation commands.
- Browser-test commands.
- A license and third-party notices.
- Reproducible, actual benchmark results.

The README should explain:

- What Meridian does.
- What is implemented from scratch.
- The exact supported scientific scope.
- Assumptions and limitations.
- How observations, interventions, and counterfactuals differ.
- How to run the application locally.
- How to reproduce results.
- How to deploy to GitHub Pages.

Additional documentation should explain graph representations, PC orientation behavior, NOTEARS diagnostics, structural-model fitting, experiment selection, and evaluation methodology.

Prepare deployment configuration and verify the local production build. Do not create a remote repository, push, or publish without my instruction.

## 20. Implementation sequence and completion criteria

Proceed in runnable milestones:

1. Graph representations, structural models, simulation, and exact mathematical fixtures.
2. Partial-correlation tests and PC-stable discovery.
3. NOTEARS with gradient checks and explicit graph validation.
4. Structural-model fitting, intervention queries, and counterfactuals.
5. Candidate enumeration and experiment selection.
6. Browser Python integration and the core interactive workflow.
7. Discovery traces, graph comparisons, uncertainty views, and persistence.
8. Benchmarks, browser verification, documentation, and static deployment preparation.

Maintain concise status and design notes so interrupted work can resume accurately.

Meridian is complete only when:

- Both discovery methods perform real computations.
- Ambiguous and invalid results are represented honestly.
- The observational-equivalence demonstration works numerically.
- Interventions replace structural equations correctly.
- Counterfactuals preserve the appropriate abducted residuals.
- Experiment selection cannot use simulator truth.
- At least one complete observe–discover–intervene–update campaign works in the browser.
- Uploaded CSV analysis remains local.
- Exact-oracle, numerical, reference, and browser checks have been performed.
- Published benchmark summaries are generated from actual results.
- Resource budgets, cancellation, and recovery work.
- The static production build operates under a repository subpath.
- No fake metrics, hardcoded discoveries, placeholder computations, or advertised-but-unimplemented features remain.

At handoff, summarize what was built, how to run it, the checks actually performed, measured results, and any remaining limitations or environment-dependent verification gaps.

Start by inspecting the workspace, then implement Meridian.