# Third-party notices

Meridian's original code is MIT licensed. Its scientific implementations are
informed by the papers cited in [PC](docs/PC.md), [NOTEARS](docs/NOTEARS.md), and
[SCM](docs/SCM.md); the supplied build brief provides the exact three-variable
demonstration.

The static distribution includes the following pinned open-source components.
Full license texts and the notices extracted from the actual numerical wheels
are checked into [web/public/licenses](web/public/licenses/index.html), which
Vite copies unchanged to `dist/licenses/`. This directory is available offline
alongside the self-hosted runtime; it does not depend on remote license links.

| Component | Version | License and local text |
|---|---|---|
| Pyodide | 0.27.7 | [MPL-2.0](web/public/licenses/pyodide-LICENSE.txt) |
| CPython in Pyodide | 3.12.7 | [PSF and incorporated historical licenses](web/public/licenses/cpython-LICENSE.txt) |
| Emscripten runtime | 3.1.58 | [MIT / NCSA and embedded Node.js notice](web/public/licenses/emscripten-LICENSE.txt), [musl notices](web/public/licenses/musl-COPYRIGHT.txt) |
| NumPy in Pyodide | 2.0.2 | [BSD-3-Clause](web/public/licenses/numpy-LICENSE.txt), [wheel notices](web/public/licenses/numpy-wheel-notices.txt), [bundled-component inventory](web/public/licenses/numpy-bundled-LICENSES.txt) |
| SciPy in Pyodide | 1.14.1 | [BSD-3-Clause](web/public/licenses/scipy-LICENSE.txt), [wheel notices](web/public/licenses/scipy-wheel-notices.txt), [bundled-component inventory](web/public/licenses/scipy-bundled-LICENSES.txt) |
| OpenBLAS | 0.3.26 | [BSD-3-Clause](web/public/licenses/openblas-LICENSE.txt), [included LAPACK license](web/public/licenses/lapack-LICENSE.txt) |
| React / React DOM | 19.1.1 | [MIT](web/public/licenses/react-LICENSE.txt), [React DOM copy](web/public/licenses/react-dom-LICENSE.txt) |
| React scheduler | 0.26.0 | [MIT](web/public/licenses/scheduler-LICENSE.txt) |

The license index additionally contains NumPy lapack-lite, libdivide and Dragon4
notices, and SciPy L-BFGS-B's notice. Wheel-embedded component notices are retained
in their original wheels as well as copied into the readable notice files.
The upstream bundled-component inventories describe source files beyond the
subset installed by each wheel; their referenced source trees are linked in
the index rather than claiming every listed source is executed by Meridian.

`web/public/licenses/manifest.json` records notice provenance and SHA-256 digests.
The Pyodide lock records the numerical package hashes. Core runtime hashes are
recorded in `scripts/runtime-manifest.json`; preparation verifies those assets
before reuse. Meridian redistributes the upstream runtime artifacts unchanged.
Corresponding source, build configuration and patches are available at the
[Pyodide 0.27.7 source release](https://github.com/pyodide/pyodide/tree/0.27.7)
and the component source versions linked in the license index.

No font files are bundled or fetched from font services. CSS lists DM Sans and
IBM Plex Mono as optional locally installed faces, followed by system fallbacks;
those names alone do not distribute the fonts.

Native NumPy 2.4.2 and SciPy 1.17.1 are separately installed packages, not
redistributed native binaries. Vite, TypeScript and build tooling are pinned in
the frontend lockfile. Development-only causal-learn 0.1.4.4 and its dependencies
are excluded from the deployed runtime. The unmodified reference NOTEARS source
is vendored only under `tests/reference/vendor`, together with its [Apache-2.0
license](tests/reference/vendor/NOTEARS_LICENSE) and pinned source manifest.
