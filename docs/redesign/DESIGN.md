# Meridian redesign record

Work began on 2026-10-16. The implementation and verification record below was
updated on 2026-10-18. Completed checks and remaining limitations are recorded
separately; build success is not a substitute for visual verification.

## Product and baseline

Meridian is a local causal-inference laboratory, not a general dashboard. Its
strongest working story is that several causal graphs can explain the same
observations yet disagree about an intervention. A user can inspect that
ambiguity, choose an experiment, collect a simulated or measured batch, and see
the support for the candidate explanations change. The selected structural
model also supports conditioning, intervention and individual counterfactual
queries.

The baseline is the equivalence world, seed **7**, **800 observations**,
PC-stable with alpha **0.01** and maximum conditioning depth **3**. The completed
baseline discovery contains three candidate DAGs. Matching after captures
must use this same state rather than a different dataset or cherry-picked
result. Baseline screenshots are in [before/](before/): initial views at 1440,
1280, 768 and 390 pixels, plus the query state and expanded field guide at
1440 pixels. The initial baseline view already contains a real discovery;
it is not an empty or mocked landing screen.

The old desktop composition allocated a persistent left data sidebar, central
graph/results column and right inspector. A journey strip, graph tabs and
inspector tabs divided the workflow across several navigation systems. The
graph's available width was reduced by two permanent sidebars, while controls
and explanatory labels frequently used very small type. This made the central
scientific comparison less prominent than its surrounding chrome. Narrow
layouts switched between the physical panels rather than the user's tasks.

Capabilities that remain part of the redesign include built-in worlds, local
CSV selection and validation, seeded loading, PC and NOTEARS controls, alternate
DAG selection, graph/edge inspection, discovery trace replay, simulator-truth
reveal, intervention recommendations, experiment histories and support,
measured outcome import, explicitly labeled model simulation, simultaneous
interventions, conditioning, counterfactuals, backdoor checks, bootstrap
diagnostics, explicit model editing, experiment export/import and optional local
session persistence. Loading, cancellation, failures and unavailable actions
are part of the interface, not exceptional screens to omit.

## Existing identity retained

The existing palette was read from `web/src/styles.css` before replacement.

| Role | Existing value | Intended role after redesign |
|---|---|---|
| Background | `#0c141d` | Deep navy workspace ground |
| Panel | `#101b26` | Quiet secondary working surfaces |
| Surface | `#14222e` | Selected or elevated controls |
| Rule | `#263642` | Editorial separators and plot scaffolding |
| Main text | `#dce6ee` | Primary text and results |
| Muted text | `#95a9b8` | Explanations and secondary labels |
| Faint text | `#758c9d` | Low-priority annotation, subject to contrast review |
| Teal | `#6ee4cf` | Primary actions, active state and selected model |
| Amber | `#e4bc83` | Assumptions, simulator truth and caveats |
| Coral | `#f09c90` | Conflicting graph evidence/error emphasis |

DM Sans remains appropriate for interface and explanatory text; IBM Plex Mono
remains appropriate for numerical readouts, equations and compact scientific
labels. The typography hierarchy can change substantially without discarding
these families. Status and graph semantics must also be conveyed by wording,
stroke patterns, geometry and selection markers rather than color alone.

## Quality benchmark inspected

The public portfolio source was inspected through the GitHub API at commit
[`d9b70c3364c5c7399bedf3e86c46f43d027a8887`](https://github.com/DhanushKrishna4/DhanushKrishna4.github.io/tree/d9b70c3364c5c7399bedf3e86c46f43d027a8887).
The source inspection covered:

- `src/App.tsx`, `src/components/Hero.tsx`, `Core.tsx`, `Menu.tsx` and `Work.tsx`.
- `src/lib/motion.ts` and `src/lib/scroll.ts`.
- `src/styles/index.css` and `src/styles/sculpture.css`.
- `scripts/check-sculpture-geometry.mjs`.

The transferable standards are careful proportions, responsive recomposition,
shared values for related motion, useful content at first paint, visual
fallbacks, cleanup of event listeners/rendering work, focus management, and
preservation of touch and pinch zoom. The source makes the fallback visible
until the rendered object is ready, reacts to reduced-motion changes, restores
focus after overlays and prevents skipped reveal animations from leaving
content invisible. Its graphical checks validate geometry rather than merely
asserting that a page builds. These observations are source findings; no test
execution is claimed for the portfolio repository.

The benchmark is an execution standard only. Meridian does not borrow its
sculpture, contour fields, aperture loader, alternating grounds, signature,
hero shrink, scattered project grid, assets, palette, section order or motion
choreography. The browser inspection and resulting screenshots are recorded
separately by the redesign verification work.

## Structural directions considered

1. **Sequential research notebook.** Observations, discovery, intervention and
   interpretation become stacked chapters. It tells the scientific story well,
   but makes repeated comparisons cumbersome and places current controls far
   from earlier results.
2. **Three-pane instrument console.** A dense persistent control/graph/inspector
   arrangement supports expert access. It remains too close to the existing
   structure and spends the first viewport on peripheral controls.
3. **Broad causal comparison folio — chosen.** A wide graph and comparison field
   establishes the competing explanations as the focal point. Task navigation
   selects **Structure**, **Experiments**, **What if**, or **Data**. Each task has
   an intentional working composition while the dataset/model context remains
   visible and consistent.

The chosen direction follows the product's central question: what changes when
we act rather than merely observe? It creates enough room for causal structure,
alternative explanations and outcome comparisons to read together. Data setup
is still immediate, but no longer permanently consumes a third of the desktop
canvas. Advanced parameters and diagnostics are grouped next to their relevant
task and remain available through explicit disclosure.

The graph is an actual instrument: node and edge selection expose evidence,
candidate selection changes the model used for queries, and interventions
change the computed outcomes under that explicit structural assumption.
Selection highlights the variable being inspected; it does not imply that
the graph has been re-estimated. The design
must not imply that an observational arrow is uniquely identified or that
candidate support is a calibrated posterior. Labels distinguish unresolved
structure, selected assumptions, simulator truth and user-specified models.

On narrow screens, task navigation stays recognizable while the graph, result
and controls are ordered for use. Dense controls move into readable groups;
plots retain useful space. Motion should explain changes of task, selection and
computed state without delaying frequent actions. Reduced motion must preserve
all content and interactions.

## Scientific and deployment boundaries

Python remains authoritative for graph discovery, fitting, experimental design,
likelihood updates and causal queries. The redesign does not change
`B[child,parent]`, datasets, fitted artifacts, worker contracts, numerical
semantics or the distinction between measured and simulated outcomes.

The application continues to use React/TypeScript and the bundled Pyodide
worker. It must remain a static application that works at `/Meridian/` on
GitHub Pages, with no credentials, paid API, inference service or new server
dependency. No background effect should compete with numerical work on an
8 GB M3 MacBook Air.

## Verification plan and current status

The original check list below is retained for scope. Dated results establish
which checks were completed; earlier release records do not verify the new
presentation.

### Native verification — 2026-10-18

`.venv/bin/python -m pytest` completed with **159 passed in 34.54 seconds**
using Python 3.14.3 and pytest 8.4.2. The full command output is preserved in
[native-tests.txt](native-tests.txt). This includes the optional reference
checks and confirms the native causal-engine suite; it does not establish
browser interaction or visual correctness.

### Frontend contract audit — 2026-10-17

A source comparison against the published frontend confirms that the task
navigation keeps a single `App` instance and persistent `Engine` reference.
Switching workspaces does not initialize another Python worker or trigger a
new computation. The frontend still sends the existing `load`, `discover`,
`select`, `query`, `rank`, `experiment`, `truth`, `bootstrap`, `model`, `export`
and `restore` actions through that engine; the numerical payloads and Python
implementation are unchanged.

The four workspaces expose the previous workflows: Structure contains graph
selection, candidate selection, truth reveal, trace playback, method reports,
bootstrap and assumed-model editing; Experiments contains rankings, batch
controls, measured import, labeled simulation, support and history; What if
contains simultaneous interventions, distributions, individual counterfactuals
and backdoor checks; Data contains built-in systems, seeded loading, CSV column
selection, optional raw-data persistence, previews and method parameters.
Header utilities retain the field guide, JSON restore and export.

The orchestration also clears old queries after selecting a factual row,
resets selected/intervention variable IDs when a different dataset is restored,
and preserves completed derived results when a new load fails validation.
Dialogs make background content inert and restore focus when dismissed. These
are source-level findings; the visible-browser checks below must still verify
their actual behavior and accessibility.

- Run the native suite and TypeScript/production build.
- Run the existing 18-check `verification.html` harness against the built
  `/Meridian/` path and save the actual JSON result.
- Exercise visible workflows: seeded parameter changes and rediscovery,
  candidate selection, graph node/edge inspection, trace replay, NOTEARS,
  experiment ranking/run/history, what-if queries and factual row selection.
- Exercise CSV selection/validation and imported experimental outcomes through
  the visible controls, plus model editing, export/download/restore and local
  persistence. Engine-level tests alone do not exercise file choosers or
  frontend state wiring.
- Verify cancellation/recovery through the product controls; inspect loading,
  error, disabled, selected and success states.
- Inspect keyboard navigation, focus visibility and restoration, dialogs,
  disclosure controls, touch target sizing and reduced-motion behavior.
- Inspect initial, completed workspace and secondary states at approximately
  1440, 1280, 768 and 390 pixels, after fonts and computation settle. Compare
  matching baseline and redesign screenshots and make a substantive correction
  pass after the first full implementation.
- Check browser console errors, static asset loading, overflow and project
  subpath behavior. If the redesign is published, verify the actual deployed
  revision and repeat the relevant live checks.

### Existing browser harness coverage

`web/src/verification.ts` uses the production Engine and worker for numerical
tests; only injected stale-message and watchdog tests use fake workers. Its
18 checks cover worker protocol/retry, native/Pyodide parity, seeded PC and
candidate enumeration, single/simultaneous interventions, factual invariance,
covariance-sensitive recommendations, a real simulated campaign, deterministic
export/restore, malformed/tampered imports, lazy SciPy and NOTEARS, bootstrap,
cancel/recovery, repeated-run state, CSV provenance and validation, duplicate
experimental evidence, explicit model validation, and truth-reveal invariance.

It does **not** establish that the redesigned task navigation, component
callbacks, controls, file choosers, downloads, persistence toggle, dialogs,
keyboard/focus behavior, plots, legends, responsive layout or explanatory copy
work correctly. It does not instrument browser heap memory, clear HTTP caches,
test physical touch devices or establish Safari/Firefox compatibility. Those
limits remain explicit even when all 18 engine checks pass.

### Browser and visual results — 2026-10-18

The production-path browser harness passed **18 checks, 0 failures**, in
7,434.5 ms. The actual report is [browser-checks.json](browser-checks.json).
It recorded Chromium 155, `/Meridian/verification.html`, no external resource
requests, and native/Pyodide agreement at the stated `1e-8` tolerance. This run
preceded the final frontend-only cancellation and export-default fixes; the
worker, engine bridge and Python package were unchanged by those fixes.

Visible UI checks completed before browser access was interrupted:

- The default equivalence world loaded 800 observations with seed 7 and
  completed PC-stable: six CI tests, 16 trace events and three candidates.
- Keyboard Enter selected graph variable X. The field guide moved focus to its
  close control, made the background inert, trapped Shift+Tab, closed with Escape
  and returned focus to its trigger.
- A real `do(Y=1)` query for outcome X showed conditional mean 0.857 and variance
  0.345 versus interventional mean -0.065 and variance 1.043. The individual
  counterfactual retained X and changed Y and Z under the selected model.
- Changing the intervention to `Y=2` and adding simultaneous `X=-1` cleared the
  old result and computed the new values. The table showed interventional means
  X=-1, Y=2 and Z=1.58; the row-specific counterfactual Z was 1.406.
- The empty adjustment set passed the X-to-Z backdoor check for candidate 1.
- Ranking returned `do(Y=-1.11)` with score 0.581, including mean and covariance
  components. Changing the proposed batch from 100 to 80 and running the
  simulated experiment produced one history round and displayed support of
  100%, 0%, 0%, from 33.3% each. These are rounded fitted-candidate weights.
- The export dialog displayed its raw-data and simulator-truth options. The
  subsequent download/cancellation interaction was interrupted and is not
  recorded as passed.

The initial layout was inspected at 1440×900, 1280×800, 768×540 and 390×844,
with settled fonts and real discovery results. DOM measurements showed no
horizontal overflow at those sizes. The narrow layout also completed a real
query. Screenshots are stored as JPEG files, matching their actual encoding.

| State | Before | After |
|---|---|---|
| Initial, 1440 | [before](before/initial-1440.jpg) | [after](after/initial-1440.jpg) |
| Initial, 1280 | [before](before/initial-1280.jpg) | [after](after/initial-1280.jpg) |
| Initial, 768 | [before](before/initial-768.jpg) | [after](after/initial-768.jpg) |
| Initial, 390 | [before](before/initial-390.jpg) | [after](after/initial-390.jpg) |
| Query, 1440 | [before](before/query-1440.jpg) | [after](after/query-1440.jpg) |
| Field guide, 1440 | [before](before/guide-1440.jpg) | [after](after/guide-1440.jpg) |
| Completed experiment | — | [after](after/experiment-1440.jpg) |

The substantive correction pass increased useful graph space, removed duplicate
inspector readouts, refined density overlays, and made labels and axes readable.
A later pass compressed the mobile introduction and graph, made narrow-screen
navigation sticky, added explicit icon-button names, and offset the sticky
experiment controls below the header. The 1280/768/390 and experiment screenshots
predate these final spacing adjustments; refreshed captures remain pending.

### Final source review and build — 2026-10-18

The production build, including TypeScript checking, passed after the final
changes; output is saved in [build.txt](build.txt). The added font packages are
pinned to 5.3.0, served locally, and accompanied by their SIL Open Font License
texts in the existing license index and hash manifest.

Independent source review identified a cancellation race: a session could commit
before the persistence export finished, while its dependent results were cleared
only after that export. Cancelling in that interval could pair an old prediction
with the new selected model. Session commits now synchronously invalidate query,
backdoor and bootstrap results before awaiting persistence. Discovery and restore
also reset trace/ranking state. Every committed load or restore resets dataset
controls and export defaults, even when identical data retain the same ID. CSV
sessions therefore cannot inherit an enabled raw-data export from a built-in
world. These fixes were source-reviewed and type-checked; their precise timing
and dialog behavior have not yet been re-exercised in the browser.

### Remaining verification limits

After the interrupted browser connection, the browser tool rejected the local
preview with a URL-security-policy error. The user confirmed that browsing was
allowed; a retry still returned the same error. Browser checks were stopped,
and no alternate browser or automation path was used to bypass that restriction.

The following remain unverified in the redesigned visible UI: final-spacing
recaptures; cancellation/recovery through its controls; dataset reload and NOTEARS
controls; trace replay and bootstrap controls; candidate/custom-model selection;
factual-row preview selection; CSV file choosers and measured-batch import;
export download/JSON restore and persistence; final console inspection; and a
browser run against the published redesign. Several corresponding engine paths
passed the 18-check harness, but that does not establish their UI wiring.
Safari, Firefox, physical touch hardware, heap usage and runtime reduced-motion
behavior were not tested. The existing scientific limitations remain unchanged.
