# Structural models and experiments

Meridian keeps a discovery result separate from a selected DAG and from its
fitted structural causal model (SCM). A model is an explicit assumption. Each
coefficient uses `B[child, parent]`; observations occupy rows. All public
predictions, intervention values and fitted coefficients use original units.

## Fitting and units

`fit_scm` requires a valid DAG. Each equation includes an intercept and is fitted
by NumPy's stable least-squares solver. Parent columns are centered and scaled
for numerical solving and rank/conditioning diagnostics, then coefficients and
intercepts are transformed back to the original units. Rank-deficient systems
and scaled design condition numbers above `1e10` are rejected; there is no ridge
repair. Residual variance is the maximum-likelihood estimate `RSS/n`. The
default floor is `1e-12` times that child's marginal training variance. The raw
variance, floor and whether flooring occurred are recorded per equation.
Constant columns are rejected. Noise variances must be finite and positive.
The fitted model retains the selected parent graph in its metadata even when
an estimated coefficient is exactly zero. Such an edge remains a structural
assumption; its fitted numerical effect is zero.

This fit uses the authorized observational training split. It is separate from
NOTEARS' penalized weights. Interventional batches never become observational
training rows, and campaign parameters remain fixed. `to_original_units`
supports an explicit transformation from `z=(x-center)/scale`: coefficients are
`diag(scale) B diag(1/scale)`, the intercept is
`center + scale*intercept - B_original@center`, and noise variances scale by
`scale**2`.

## Observation, action and counterfactuals

`condition` applies the ordinary conditional Gaussian formulas. `moments`
instead replaces every clamped equation with a constant, solves only the
remaining system, and sets clamped variances and covariances to zero. Multiple
simultaneous interventions, root interventions, leaf interventions and fully
clamped systems are supported. Covariance propagation solves against the noise
square root, avoiding explicit inverses and singular full-density calculations.

`total_effects()[child,treatment]` sums products along every directed path;
the diagonal equals one. A supplied backdoor set is checked by excluding
treatment descendants and testing d-separation after deleting treatment's
outgoing edges. This is the backdoor criterion, not unrestricted identification.
The optional bounded search returns a completion flag; an empty incomplete
search is not evidence that no valid set exists.

For a complete factual row, residual abduction computes `u=x-b-B@x` separately
for each selected model. The action replaces equations, then prediction
propagates the same residuals in topological order. No new noise is sampled.
The result is conditional on that selected SCM, not a general hidden-confounder
counterfactual. This follows [Pearl's structural definition of counterfactuals](https://causality.cs.ucla.edu/blog/index.php/2014/11/),
which replaces equations while preserving the individual exogenous context.

## Worlds and truth boundary

The exact equivalence fixtures share covariance
`[[1,.8,.64],[.8,1,.8],[.64,.8,1]]`. Under `do(Y=1)` their `(X,Z)` means are
`(0,.8)`, `(.8,0)`, and `(.8,.8)`. Under `do(Y=0)` all means vanish but their
covariances differ. These are mathematical fixtures. Live alternative models
are fitted from observations rather than receiving their exact coefficients.

The worlds module is simulator infrastructure. A hidden-confounder world's
observations contain only X and Y; its separate truth descriptor contains H and
the complete simulator. `simulate_world_experiment` is the oracle boundary.
Its `seed` controls the new experimental batch and `world_seed` preserves the
world created at load time. Revealing truth has no effect on learner results.
The recommendation and Campaign APIs reject truth-tagged models and world
descriptors. This separation prevents ordinary workflow leakage, not malicious
inspection of a static site's embedded simulator code.

## Recommendation and support

The recommender accepts only candidate SCMs and their observational training
data. It uses no true graph, true coefficients, hidden residuals, evaluation
rows or future outcomes. For each one-variable intervention it compares
nonintervened predicted means and covariances. Means are normalized by fixed
training standard deviations; covariance entries by products of those scales.
The score is average pairwise squared mean disagreement per variable plus
average pairwise squared covariance disagreement per matrix entry, with equal
weight on those two terms. Thus a zero-mean intervention can still score well.

Default proposals use training mean minus one SD, the mean, and mean plus one
SD. Default admissible bounds are mean ± two SD; custom finite bounds can be
supplied. Values outside bounds are rejected. The returned ranking is a
**disagreement heuristic**, not expected information gain. A finite candidate
list need not cover the full equivalence class. Campaign records preserve
whether enumeration was complete.

Before an oracle runs, `Campaign.freeze` records immutable copies of candidate
parameters, the intervention, batch size, score, and content digest. It returns
a frozen plan. `update` accepts only an unchanged registered plan and verifies
the batch size and clamped values. Each plan and batch ID is consumable once;
content hashing also catches identical observations relabeled as new evidence.
The digest detects accidental mutation; it is not a cryptographic guarantee
that a caller really collected observations only after planning.

The experimental log likelihood is the sum of structural Gaussian conditional
log densities over **nonintervened** equations. Clamped values still appear as
parents in other equations. The replaced mechanism contributes no density.
Log weights accumulate with a subtracted common offset to prevent underflow.
Displayed values are **normalized plug-in likelihood support**, not automatic
Bayesian model posterior probabilities. Parameters are not refitted, so these
weights do not integrate parameter uncertainty and depend on the candidate
set, assumptions and fixed fits. Uploaded CSV workflows need a measured batch
or an explicit model simulation; this module never fabricates observations.

Campaign JSON records plans, evidence IDs/digests, fixed models, per-batch
likelihoods and weights. Restore validates dimensions, graph states, finite
values and schema version, then replays the recorded log-likelihood updates.
Full laboratory exports additionally retain each batch's observations; restore
checks the outcome digest and recomputes the nonreplaced structural likelihoods
under the fixed models, without calling the simulator. Digests canonicalize
integral numbers and signed zero to survive JavaScript JSON serialization.
The enclosing experiment export is responsible for retaining actual batches
when full outcome replay is requested; summary campaign records alone cannot
recompute log likelihoods from missing observations.

Raw imports are checked for the 5,000-row and 15-variable bounds and exact row
widths before deep copying or allocating numerical arrays. Exported sessions
are detached snapshots; a failed restore leaves the existing laboratory intact.
Cancelling an operation before its final result rolls back its intermediate
state. For built-in worlds, stored raw data defines the dataset identity and
regenerated provenance is compared at `rtol=atol=1e-12` to allow native versus
WebAssembly rounding. If an export omits raw data, its regenerated identity must
match exactly; otherwise a data-inclusive export is required.

## Validation

Run `.venv/bin/python -m pytest tests/test_scm.py tests/test_experiments.py`.
Tests include the exact mathematical fixtures, independent literal-equation
simulations, conditioning versus action, roots/leaves/multiple/full clamps,
path-summed total effects, adjustment sets, per-model residual counterfactuals,
unit conversion, OLS/rank diagnostics, hidden-world oracle isolation,
covariance-sensitive ranking, truth-input rejection, frozen plans, exclusion
of replaced likelihood mechanisms, duplicate evidence and export replay.
