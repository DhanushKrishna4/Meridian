# Computed examples

- `exact-fixture.json`: exact three-model observational-equivalence fixture,
  including intervention moments and the forward-chain counterfactual.
- `campaign.json`: an actual observe–discover–intervene–update run with 800
  observations, seed 7, fitted PC candidate models, one selected experiment,
  its 100 outcomes and normalized plug-in likelihood support. Import this file
  into Meridian to restore the investigation without rerunning the experiment.
  It includes raw synthetic observations; it excludes simulator truth.
- `observations.csv`: 200 complete observations of X, Y and Z from the seeded
  forward-chain simulator (seed 7), for trying the local CSV workflow. Uploading
  this file treats it as observational data and does not grant an experiment
  oracle or ground-truth access.

Regenerate from the repository root after installing the native package:

```sh
.venv/bin/meridian fixture --output examples/exact-fixture.json
.venv/bin/meridian demo --seed 7 --rows 800 --output examples/campaign.json
.venv/bin/python - <<'PY'
import numpy as np
from meridian_causal.scm.worlds import make_world
world = make_world('equivalence', seed=7, n=200)
np.savetxt('examples/observations.csv', world['data'], delimiter=',',
           header=','.join(world['nodes']), comments='', fmt='%.17g')
PY
```

Exact values and seeded observations are reproducible. Recorded timing and
runtime-version metadata may differ between environments; last-bit numerical
rounding can also differ between native Python and WebAssembly.
