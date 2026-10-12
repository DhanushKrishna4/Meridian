# Boundaries and reproducibility

The installable `meridian_causal` Python package owns graph algorithms, Gaussian
conditional tests, discovery, linear structural equations, experiment selection,
likelihood updates and JSON validation. The exact same sources are zipped for
Pyodide by `scripts/prepare_web.py`. No frontend module implements causal inference.
React renders returned graph edges, traces and numerical results; plotting a
histogram or laying out a graph is display work, not a second learner.

`B[child,parent]` is universal. Observations are rows. Variable IDs are stable
strings, independent of drawing positions. `Graph` distinguishes directed and
undirected edges. A discovery result is evidence; an explicitly selected DAG
and fitted `LinearSCM` are the assumption-bearing objects used for queries.

## Browser lifecycle

A dedicated worker lazily boots bundled Pyodide 0.27.7 and NumPy 2.0.2. SciPy
1.14.1 loads only for NOTEARS. Runtime wheels are downloaded during preparation,
verified against the Pyodide lock's SHA256 hashes, and served with the app. There
is no inference API, Python backend, authentication, CDN fetch at runtime,
SharedArrayBuffer, cross-origin isolation requirement or browser flag.

PC is bounded by depth, tests and elapsed time; it reports actual depth counters.
Enumeration is bounded by candidate count, expansions and time. NOTEARS yields
between bounded optimizer calls; bootstrap yields after individual replicates.
Synchronous graph stages have a watchdog and immediate main-thread cancellation
via worker termination. Cancellation does not wait for a Python event-loop yield.

Every command/reply has a run ID and worker-generation ID. Stale replies are
ignored. The main thread preserves the latest full, completed snapshot in memory;
a fresh worker restores it before the next dependent operation. Pending promises
are rejected on cancellation and watchdog failure. UI state records configuration
and completed results separately from active computation. Python operates
transactionally: errors do not commit an unfinished action.

JSON strings cross the boundary rather than retained PyProxy arrays. Temporary
generators/globals are released after actions. Statistical caches are scoped to
a discovery call; arrays, trace sizes, data size, candidates and bootstrap counts
are bounded. Repeated full snapshots intentionally trade a modest memory copy
for recovery; default datasets have 800 rows and three variables.

## Data and model roles

Observations are split 60/20/20 by seeded permutation before fitting any
preprocessing. Discovery, regression fitting and experiment selection use the
training split only. Validation and evaluation roles are stored separately;
the app does not tune its settings against evaluation rows. Experimental batches
are stored separately and never appended to the PC/NOTEARS training matrix.

The selector receives fitted candidates and training scales. The experiment
oracle is a separate function called only after the plan, candidate snapshot,
value, sample count and disagreement score are frozen. A static app's simulator
truth is inspectable source, but it is not passed to learner or selector APIs.
Truth reveal does not rerun or amend discovery.

Versioned JSON exports contain observations (when explicitly included), IDs,
units, seed/split, settings, traces/statuses, candidates, fits, selected model,
campaign plans and measured/simulated outcomes. Restore validates data and graph
structure; no code evaluation or pickle is involved. Built-in observation data
can be regenerated from identity only, verified by hash. CSV exports without
raw observations are records that cannot resume computation without the data.
Simulator-truth exports are explicitly opt-in and separated from learner state.

Model edits are a separate user-specified SCM and never amend PC's graph.
Queries name their selected model; switching models or data clears affected UI
results. PC rediscovery starts a fresh candidate campaign, so old experiments
cannot silently reweight new parameters.
