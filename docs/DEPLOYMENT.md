# Public deployment

Published on 2026-10-13 (Asia/Kolkata).

- Public repository: [DhanushKrishna4/Meridian](https://github.com/DhanushKrishna4/Meridian)
- Application: [Meridian](https://dhanushkrishna4.github.io/Meridian/)
- Browser checks: [verification page](https://dhanushkrishna4.github.io/Meridian/verification.html)
- Initial deployed source: [`80034c1`](https://github.com/DhanushKrishna4/Meridian/commit/80034c1f83cb2a92705e26030f56bfe4831a58fd)
- Successful build and deployment: [Actions run 38317358711](https://github.com/DhanushKrishna4/Meridian/actions/runs/38317358711)

GitHub Pages uses the repository's Actions workflow with HTTPS enforced. Pushes
to `main` build and deploy the static application. There is no analysis backend;
Python computation continues to run locally in the visitor's browser. Runtime
assets are bundled during the build and served from the Pages repository path.

## Checks performed on the public site

The initial GitHub-hosted build passed **154 tests**, with **5 optional
causal-learn reference checks skipped** because that development-only dependency
is not installed by the deployment workflow. The earlier native reference run
remains recorded in [EVALUATION.md](EVALUATION.md). TypeScript validation, the
Vite production build, artifact upload and Pages deployment all succeeded.

The live verification page passed **18 checks, 0 failures** using the deployed
worker and Python package, including native/Pyodide parity, lazy SciPy/NOTEARS,
interventions, counterfactuals, campaigns, export/restore, cancellation, watchdog
retry and rejection of stale responses. The unmodified browser report is saved
as [pages-browser.json](../benchmarks/results/pages-browser.json).

The visible application also loaded the default observations, discovered three
candidates, ranked an intervention and ran a 100-row simulated experiment.
Displayed relative support changed from 33.3% per candidate to 100%, 0%, 0%
(rounded display values). No warnings or errors appeared in the inspected
browser console. [Published application screenshot](screenshots/published.png).

These public-site checks used Chromium. The browser-family, memory and scientific
scope limitations in [VERIFICATION.md](VERIFICATION.md) continue to apply.

## Commit attribution

The initial commit's author and committer both resolve to `DhanushKrishna4`,
using the account's GitHub no-reply email. The repository's contributors API
listed only `DhanushKrishna4` after the initial push. The deployment workflow
uploads a Pages artifact and does not create additional source commits.
