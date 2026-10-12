# Meridian implementation notes

Build brief: `BUILD_BRIEF.md`. Development and numerical validation were local.
Public GitHub and Pages publication was authorized on 2026-10-12.

## Shared boundaries

- All Python numerical APIs accept arrays with observations in rows. Coefficients are `B[child,parent]`.
- Graph JSON: `{nodes: [stable string IDs], directed: [[parent,child]], undirected: [[a,b]]}`.
- Graph class: `Graph(nodes, directed=(), undirected=())`; `to_dict()`, `from_dict()`, `parents(id)`, `children(id)`, `ancestors(id)`, `descendants(id)`, `topological_order()`, `is_dag()`, `skeleton()`, `colliders()`.
- `graphs`: `d_separated(graph, x, y, conditioned)`, `dag_to_cpdag(graph)`, `enumerate_extensions(graph, max_candidates=128, max_expansions=100000, timeout=5)` returning `.graphs`, `.complete`, `.reason`, `.expansions`; `consistent_extension(graph)`.
- `discovery.pc`: `pc_stable(data, nodes, alpha=.01, max_depth=3, max_tests=10000, timeout=10, oracle=None)` returns JSON-compatible dictionary with `graph`, `status`, `trace`, `tests`, `ambiguous_triples`, `conflicts`, `settings`. `oracle(x,y,conditioning)` returns boolean independent and uses IDs. Statistical tests in `statistics`.
- `scm`: `LinearSCM(nodes, B, intercept, noise_variances, provenance='user-specified')`, `.to_dict()`, `.from_dict()`, `.graph`, `.moments(interventions=None)` -> `(mean,covariance)`, `.condition(values)` -> `(mean,covariance)`, `.simulate(n, seed, interventions=None)`, `.counterfactual(row, interventions)`, `.total_effects()`; `fit_scm(data, graph)`, `check_backdoor(graph,treatment,outcome,adjustment)`.
- `scm.worlds`: `worlds()` list of metadata; `make_world(name, seed=7, n=800)` -> dictionary with `data` ndarray, `nodes`, `truth` LinearSCM or truth descriptor, `description`; `equivalence_models()` list exact LinearSCMs. Built-in IDs: `equivalence`, `collider`, `confounding`, `hidden`, `random`.
- `experiments`: `rank_interventions(models, training_data, values=None)` returns list of dictionaries with `variable`, `value`, `score`, `mean_score`, `covariance_score`; `Campaign(models)` with `.freeze(intervention, n, score=0)` -> plan dictionary, `.update(plan, data, batch_id)` -> dictionary support; `.to_dict()` and `.from_dict()`. Support is normalized plug-in likelihood, with no parameter refit.

## Browser protocol (root implements Python adapter + worker)

Frontend imports `Engine` from `./engine`. `const engine = new Engine(onProgress)`; `await engine.run(action, payload)` returns JSON. `engine.cancel()` terminates/recreates worker; `engine.dispose()`.

Actions:

- `load`: `{world:'equivalence',seed:7,n:800}` or `{csv:string, columns?:string[]}`. Returns session with `id`, `world`, `nodes`, `data` (preview rows), `row_count`, `diagnostics`, `split`, `description`, `truth_available`, `pc:null`, `notears:null`, `candidates:[]`.
- `discover`: `{method:'pc'|'notears',alpha:.01,max_depth:3,lambda1:.1,threshold:.2,standardize:true}` -> complete session. PC sets `pc`, `candidates` (each `{id,graph,model,weight}`), `enumeration`. NOTEARS sets `notears` and may offer `.model`. `selected` candidate ID starts at 0.
- `select`: `{index:number}` -> session.
- `query`: `{interventions:{Y:1},row:0}` -> `{nodes, observational:{mean,covariance},conditional:{mean,covariance},interventional:{mean,covariance},factual,counterfactual,descendants,equations,effects,model_label}`.
- `rank`: `{}` -> `{rankings:[...],label}`.
- `experiment`: `{variable:'Y',value:1,n:100,score:0,csv?:string,simulate_model?:boolean}` -> session with updated `.candidates[].weight`, `.history`; built-in truth only in oracle action. CSV requires measured batch or explicit selected-model simulation.
- `truth`: `{}` -> `{graph,model,description}`; does not modify learner.
- `bootstrap`: `{replicates:10}` -> graph stability + selected graph effect intervals; real progress per replicate.
- `model`: `{nodes,B,intercept,noise_variances}` -> session with separate `.custom_model` selected for queries.
- `export`: `{include_data:true,include_truth:false}` -> versioned experiment dictionary.
- `restore`: `{experiment:object}` -> session.
- `fixture`: `{}` -> deterministic native/browser parity dictionary.

Worker progress: `{stage:string,completed?:number,total?:number,message?:string}`. Session summaries persist outside worker for cancellation recovery. Python session owns raw data and numerical state. All UI results come from this adapter. UI must handle absent results, failures, budgets and empty candidates.

## Milestone status

- [x] Graphs and mathematical fixtures
- [x] PC-stable and NOTEARS
- [x] SCM queries and experiment selection
- [x] Browser worker and workspace
- [x] Persistence, uncertainty, benchmarks
- [x] Native/reference/browser verification and production build

Release verification is recorded in [VERIFICATION.md](VERIFICATION.md), with
raw browser, reference and benchmark artifacts in `benchmarks/results`.
Native and isolated installed-wheel suites each pass 159 tests. The production
browser harness passes 18 checks, including cross-runtime persistence and real
cancellation recovery. Packaging, example campaigns and third-party notices
are present. The GitHub Actions workflow builds and deploys the static site;
browser-engine coverage, memory measurements and benchmark-scope limits remain explicit.
