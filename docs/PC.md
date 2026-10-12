# Graphs and PC-stable

`Graph` stores stable string IDs, explicit `(parent, child)` arrows, and
lexically ordered undirected endpoint pairs. Display order does not affect
algorithm order. Construction rejects duplicate IDs, duplicate/contradictory
edges, unknown endpoints and self-loops. Cyclic directed results remain
representable for diagnostics; causal operations reject them.

## Statistical evidence

PC uses Gaussian partial correlation, calculated by centered least-squares
residualization. Unit-norm scaling improves numerical conditioning without
changing the statistic. Every selected joint design receives an SVD rank and
condition check (condition limit `1e12`); there is no ridge penalty or silent
pseudoinverse fallback. Constant, singular, nearly dependent, nonfinite and
insufficient-sample tests are invalid and stop discovery as numerical failure.

The two-sided test uses `sqrt(n - |S| - 3) * abs(atanh(r))` and a normal-tail
probability. Degrees of freedom must be positive. Correlation is clipped only
at machine roundoff after rank checks. The cache owns an immutable data copy;
its identity hashes bytes, dimensions, IDs, preprocessing and test settings.
Cache entries and the recorded tests are bounded by the search budget.

A large p-value fails to reject the null of zero partial correlation. It is
not proof of independence. A p-value is not the probability an edge exists,
and per-test alpha is not a family-wise discovery error guarantee.

## Exact orientation variant

The adjacency search implements PC-stable: freeze adjacency sets at the start
of each depth and consider candidate conditioning sets from **both** endpoints.
The first accepted separating set is retained in stable-ID lexical order.
An empty separating tuple is a recorded marginal independence; it is distinct
from a missing separating-set record.

This is **first-separating-set PC-stable, not conservative PC**. There is no
second search to collect every possible separating set. Reordering columns
while retaining their IDs is deterministic. Renaming IDs can change a finite
sample's first separating set and its collider orientations. PC-stable alone
does not make every orientation choice independent of variable ordering.

An unshielded triple is oriented as a collider when its middle vertex is
absent from the recorded separating set. Subsequent batches apply R1–R3:
avoid new unshielded colliders, avoid directed three-cycles, and orient the
two-parent nonadjacency configuration. This is the no-background-knowledge
formulation in [Colombo and Maathuis (2014), §3.1 and §4.1](https://www.jmlr.org/papers/volume15/colombo14a/colombo14a.pdf),
following [Meek (1995)](https://arxiv.org/abs/1302.4972). Background-knowledge
rules and latent-variable discovery are outside the implementation.

Each batch collects all arrow proposals before updating the graph. Opposing
proposals preserve an unresolved edge and produce explicit conflict evidence.
A batch introducing a directed cycle is rejected in its entirety. There is
no iteration-order tie breaker and no bidirected confounder notation. Rule
premises, tested sets, edge removals and graph snapshots are recorded for
replay. These diagnostics do not imply the existence of a latent variable.

## Structural validation and bounded search

DAG-to-CPDAG conversion starts from the skeleton, orients the DAG's unshielded
colliders, and applies Meek closure. Consistent extension uses sink elimination:
a sink has no children, and every undirected neighbor must be adjacent to all
its other neighbors and parents. The final DAG preserves arrows, skeleton and
unshielded colliders. Failure to find a sink is an inconsistent PDAG.

Only a completed search with no orientation conflicts, a consistent extension,
and equality between its output and that extension's converted CPDAG receives
the `CPDAG` label. Budget exhaustion and invalid tests preserve their explicit
status and are never silently promoted to complete discovery. The causal
interpretation additionally assumes independent sampling, causal Markovness,
faithfulness and causal sufficiency; validation cannot establish those facts.

Enumeration branches on unresolved edges and rejects cycles or new colliders.
Candidate count, visited states and elapsed time are bounded. A truncated list
is nonexhaustive; its size is not an estimated equivalence-class size. A single
extra valid leaf distinguishes an exactly reached candidate cap from truncation.

## Verification

`tests/test_graphs.py` independently enumerates every labeled DAG through four
vertices (1, 3, 25, 543). Grouping by independently calculated skeletons and
unshielded colliders gives equivalence classes; their invariant arrows are the
expected CPDAG. Every production conversion and every enumerated extension is
checked against that oracle. D-separation is compared against independent
enumeration of active simple paths for every pair and conditioning subset.

`tests/test_pc.py` feeds those independent d-separation answers to PC for all
2–4-variable DAGs in both forward and reversed display orders. Additional
checks cover all column permutations, each Meek rule, conflicts, numerical
failure, both-endpoint eligibility, frozen depth sets and resource limits.
Statistical fixtures use exact covariance matrices and independent OLS
residuals with SciPy's Pearson correlation and normal-tail calculations.

Run `.venv/bin/python -m pytest tests/test_graphs.py tests/test_statistics.py tests/test_pc.py`.
