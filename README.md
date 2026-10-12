# Meridian

[Open the live laboratory](https://dhanushkrishna4.github.io/Meridian/) ·
[Deployment verification](docs/DEPLOYMENT.md)

A local causal machine learning laboratory. Investigate observational data,
inspect compatible explanations, choose an experiment, and ask counterfactual
questions under an explicit structural model.

Meridian's Python engine runs natively and inside a Pyodide web worker. The React
interface is a fully static application: no Python server, analysis service,
API key or cloud compute. Runtime assets are bundled with the site. Uploaded
CSV data stays in the browser; persisting raw uploaded data is opt-in.

## Run locally

Tested native set: Python 3.14, NumPy 2.4.2, SciPy 1.17.1. The pinned browser set
is Pyodide 0.27.7 / Python 3.12.7 / NumPy 2.0.2 / SciPy 1.14.1. Node 22 or newer
and system `curl` are needed for the website build.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation .
cd web
npm ci
npm run dev
```

Open the printed HTTP address. First-time preparation downloads roughly 35 MiB
of pinned open-source browser runtime assets. Subsequent builds verify/reuse
those assets. All inference remains local. SciPy loads on demand for NOTEARS.

```sh
# From the project root
.venv/bin/python -m pytest -q
.venv/bin/meridian demo --output examples/campaign.json
.venv/bin/meridian fixture --output examples/exact-fixture.json
.venv/bin/meridian discover examples/observations.csv --columns X Y Z --output /tmp/meridian-csv.json
PYTHONPATH=src .venv/bin/python scripts/generate_fixtures.py
cd web
npm run build
npm run preview
```

The normal install makes `meridian` usable outside the checkout. After changing
Python source, repeat the package install command, or run directly from source
with `PYTHONPATH=src .venv/bin/python -m meridian_causal.cli fixture`. The tests
and browser asset preparation already use the checkout's source. The supplied
[examples](examples/README.md) contain computed exact fixtures, a replayable
campaign and a small observational CSV.

Build the native wheel and source archive with the pinned build tools:

```sh
.venv/bin/python -m build --no-isolation
.venv/bin/python -m pip install --force-reinstall --no-deps dist/meridian_causal-0.1.0-py3-none-any.whl
```

The wheel installs the Python engine and CLI; the source archive also contains
its tests, examples, benchmark scripts and documentation. Use this checkout
for the separate website build.

`web/dist` is the static production artifact. Serve it over HTTP, never `file://`.
For an exact repository-path preview from the root:

```sh
python3 scripts/serve_production.py --port 4173
```

Open `http://127.0.0.1:4173/Meridian/`. The verification page at
`/Meridian/verification.html` runs real browser-engine tests with a downloadable
report. See [verification](docs/VERIFICATION.md) for actual checks and limitations,
and [evaluation](docs/EVALUATION.md) for benchmark and reference commands.

## The investigation

1. **Observe:** choose a seeded world or select 2–15 complete numerical CSV
   columns (20–5,000 rows, at most 5 MiB). Inspect scales, rank diagnostics and
   the recorded training/validation/evaluation split.
2. **Discover:** PC-stable records Gaussian conditional-independence tests,
   separating sets and orientation premises. Replay the actual trace. Compare
   its unresolved directions with a separately optimized linear NOTEARS candidate.
3. **Compare:** enumerate up to 128 consistent DAG extensions, explicitly
   labeling truncation. Fit each using training observations and select a model.
4. **Intervene:** compare conditioning with replacing structural equations.
   Rank one-variable experiments using normalized mean **and covariance**
   disagreement. Run a simulated oracle experiment or import a measured batch.
   Update fixed-candidate plug-in likelihood support once per evidence batch.
5. **Ask what if:** choose an observed row and intervene while preserving the
   selected SCM's abducted residuals. Export and restore the full investigation.

The default three-variable puzzle has three equivalent DAGs. Their exact
observational covariances agree, while `do(Y=1)` predicts different `(X,Z)` means:
`(0,.8)`, `(.8,0)` and `(.8,.8)`. At `do(Y=0)`, covariance disagreement still
separates them. The live learner estimates candidate parameters from observations;
it is never given the exact fixture coefficients or the simulator truth.

Other worlds demonstrate collider selection, observed confounding with a sign
reversal, an explicit hidden-confounder assumption violation, and seeded sparse
systems. Revealing truth changes neither evidence nor discovery output.

## Scientific boundaries

The supported scope is small acyclic **linear Gaussian additive-noise** systems,
continuous numerical variables and complete independent observations. PC causal
interpretation additionally assumes causal Markov, faithfulness and causal
sufficiency. The hidden-confounder world violates sufficiency deliberately; its
latent variable is revealed simulator knowledge, not an automatic diagnosis.

Observational data generally do not identify a unique DAG. PC-stable uses a
first-separating-set orientation variant with stable variable-ID ordering,
conflict-checked Meek R1–R3, and structural CPDAG validation. It is not conservative
PC or FCI. Directions chosen by NOTEARS are model choices, not proof of causation.

A p-value is not an edge probability. Bootstrap frequencies measure stability.
Effect intervals condition on the selected graph. Plug-in likelihood weights
are not automatically Bayesian posterior probabilities. A bounded candidate
list is not a complete identified set. Model agreement is limited to the
models considered. No nonlinear, latent-variable identification, missing-data,
time-series or unrestricted do-calculus features are claimed.

## What is implemented here

Graph representation/validation, topology, d-separation, collider extraction,
DAG-to-CPDAG conversion, Meek closure, consistent extensions, bounded enumeration,
PC-stable logic and traces, partial correlations/Fisher Z, linear NOTEARS,
OLS structural fitting, analytic conditioning/interventions/total effects,
backdoor checking, residual counterfactuals, disagreement selection and fixed
likelihood campaigns are implemented in `src/meridian_causal`.

NumPy and SciPy provide numerical primitives, optimization and matrix
exponentials. Development-only reference comparisons are separated from runtime
dependencies. The frontend lays out and plots Python results.

Details: [PC and graphs](docs/PC.md), [NOTEARS](docs/NOTEARS.md),
[SCMs and experiments](docs/SCM.md), [architecture and recovery](docs/ARCHITECTURE.md).

## Deploy to GitHub Pages

The repository is configured for **GitHub Actions** as its Pages source.
`.github/workflows/pages.yml` runs
core tests, builds assets with relative URLs, and publishes `web/dist` after a
push to `main` or a manual workflow dispatch. It does not run the benchmark suite
on each site build.

- Repository: [DhanushKrishna4/Meridian](https://github.com/DhanushKrishna4/Meridian)
- Application: [Meridian laboratory](https://dhanushkrishna4.github.io/Meridian/)
- Browser checks: [verification page](https://dhanushkrishna4.github.io/Meridian/verification.html)

The local verification record in `docs/VERIFICATION.md` is dated separately from
deployment; it preserves the exact scope of the measured numerical checks.
The public deployment and its browser checks are recorded in
[DEPLOYMENT.md](docs/DEPLOYMENT.md).

MIT license. See [third-party notices](THIRD_PARTY_NOTICES.md).
