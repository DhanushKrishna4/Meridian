# Verification record

This is the original local verification record. The subsequent public deployment
on 2026-10-13 is recorded separately in [DEPLOYMENT.md](DEPLOYMENT.md).

Verified locally on 2026-10-10 (Asia/Kolkata; browser report timestamps are UTC).
The production application runs at a repository subpath, `/Meridian/`, using
the same Python sources as the native package. No remote repository or site
was published. GitHub-hosted Actions execution is not verified.

## Measured checks

| Layer | Actual result |
|---|---|
| Native suite | 159 passed in 15.19 s, Python 3.14.3 / NumPy 2.4.2 / SciPy 1.17.1 |
| Installed wheel | 159 passed in 15.72 s from `/private/tmp`, isolated Python and checkout import path disabled |
| External references | 9 reference tests passed; Fisher-Z maximum error 2.89e-15 across 240 comparisons; four PC graphs agree exactly; three NOTEARS supports agree |
| Browser engine | 18 checks pass on the production subpath; raw timings, user agent and tolerance are in [browser.json](../benchmarks/results/browser.json) |
| Interface | Actual CSV chooser, validation failure, discovery, campaign, counterfactual, JSON download/restore, keyboard graph selection and trace navigation exercised |
| Production | TypeScript check and Vite build pass; worker, Python archive, NumPy and lazy SciPy load from local static assets |
| Package | Wheel and source archive built; fixture, demo and CSV discovery CLI commands work outside the checkout |
| Evaluation | 108 discovery runs, six paired selection campaigns, six hidden-confounder cases retained with their failures |

Native tests include exhaustive labeled DAG fixtures through four vertices,
independent equivalence and d-separation oracles, exact-oracle PC, Fisher-Z rank
and degrees-of-freedom checks, finite-difference NOTEARS gradients, graph-cycle
validation, analytic versus simulated SCM moments, residual counterfactuals,
campaign integrity and bounded import validation. External-reference versions,
settings, measurements and benchmark interpretation are in [EVALUATION.md](EVALUATION.md).

## Browser engine checks

Run against the built site using the in-app Chromium browser (reported Chrome
155 on macOS). The harness uses the production `Engine` and its actual Pyodide
worker, with fake workers only for injected protocol and watchdog failures.
The native/Pyodide comparison tolerance is
`abs(actual-reference) <= 1e-8 * max(1, abs(reference))`.

The saved report covers:

1. Rejection of injected stale worker generations and run IDs.
2. Watchdog termination and successful retry in a fresh worker.
3. Fresh-worker Python/NumPy initialization and exact fixture parity.
4. Native fitted-model import and cross-runtime query agreement.
5. Seeded PC discovery, trace production and three real DAG candidates.
6. Simultaneous interventions, zero clamped variance and factual invariance.
7. Covariance-sensitive recommendations and an actual oracle campaign.
8. Export/restore of fitted parameters and recorded experimental outcomes.
9. Rejection of tampered outcomes and invalid schemas without state loss.
10. Lazy SciPy loading, real NOTEARS optimization and model queries.
11. Sequential bootstrap progress and selected-graph effect intervals.
12. Cancellation during a real bootstrap and recovery of completed state.
13. Repeated real discoveries retaining the latest dataset state.
14. CSV analysis without an oracle; explicitly labeled model simulation.
15. Malformed/missing CSV rejection with useful errors and state preservation.
16. Imported experimental batches cannot count recorded evidence twice.
17. Separate user-specified models and rejection of a cyclic model.
18. Hidden-world truth reveal leaves discovery and support unchanged.

The fresh-worker startup check does **not** clear browser HTTP caches, so its
timing is not an uncached first-download measurement. The runtime assets occupy
about 35 MiB on disk; SciPy is fetched/loaded when NOTEARS first needs it.
The report's `externalResourceRequests` is the document performance list, not
a complete worker-network capture. Runtime URLs are local, pinned and bundled;
CSV processing and inference run inside the worker.

## Visible application checks

- At the default seed and 800 observations, the page computes three candidates
  with equal initial support. Ranking chooses `do(Y ≈ -1.11)`; a 100-row simulated
  batch changes displayed support to 100%, 0%, 0% (rounded for display).
- The what-if controls compute conditioning, intervention and factual-row
  counterfactual values. The displayed distribution changes with the outcome
  variable; fixed-variance results have a separate visual representation.
- A real browser download produced a 135,128-byte experiment JSON. Restoring
  that file through the chooser preserved the campaign and candidate weights.
  Native Python also validated the downloaded artifact, retained as
  [browser-campaign.json](../benchmarks/results/browser-campaign.json).
- The 200-row [sample CSV](../examples/observations.csv) loads through the file
  chooser and produces three candidates. Simulator-truth access is disabled;
  experiment controls offer imported measured batches or explicit model simulation.
- A CSV with 30 missing values is rejected. The prior three fitted candidates
  remain available. The alert explains that no rows were changed and asks the
  user to fix/deselect affected columns.
- Enter selects a graph variable and updates its histogram inspector. Keyboard
  navigation of the trace slider shows the initial three-edge graph, retains
  it during test events, and returns to the final two-edge graph.
- Desktop 1280×720 and 1440×1100 and narrow 390×844 layouts were inspected.
  The 390-pixel viewport has a 390-pixel document width. Data, graph and query
  panels are available through their respective narrow-screen tabs.

Screenshots: [desktop](screenshots/desktop.png), [narrow](screenshots/mobile.png).

## Reproduce

```sh
# Native and optional-reference setup: see README and EVALUATION.md.
.venv/bin/python -m pytest -q
PYTHONPATH=src .venv/bin/python scripts/generate_fixtures.py
cd web
npm ci
npm run build
cd ..
python3 scripts/serve_production.py --port 4173
```

Open `http://127.0.0.1:4173/Meridian/verification.html`, click **Run browser checks**,
and download the JSON report. Open `/Meridian/` for the visible workflow. The
server only serves static files; it does not execute analysis. Rebuild and
reload after source changes. The verification page is intentionally separate
from the product so it does not run tests on every user visit.

## Limits retained at handoff

- Safari, Firefox, physical phones, screen readers and comprehensive accessibility
  audits have not been verified. Responsive checks use a Chromium viewport.
- Repeated-run checks verify state cleanup and recovery. Browser heap growth
  and total browser resident memory are not instrumented; native peak RSS is
  not a browser-memory measurement.
- Benchmarks use three very sparse graph structures. Four standardized NOTEARS
  runs fail numerically and remain in the recorded results. They do not support
  universal recovery or broad method-ranking claims.
- GitHub Pages deployment configuration is prepared; remote CI and public
  hosting were deliberately not exercised. The verified deployment artifact is
  the local `web/dist` directory.
- Causal answers remain conditional on linear Gaussian SCM assumptions and the
  selected graph. Candidate support is plug-in predictive likelihood, not a
  calibrated causal posterior.
