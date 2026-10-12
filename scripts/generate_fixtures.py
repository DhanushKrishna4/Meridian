"""Generate real native outputs consumed by the browser verification page."""
from pathlib import Path
import json
import platform
import numpy as np
from meridian_causal.api import Laboratory

root=Path(__file__).resolve().parents[1]
lab=Laboratory()
exact=lab.run('fixture')
lab.run('load',{'world':'equivalence','seed':7,'n':800})
lab.run('discover',{'method':'pc'})
result={'generated_with':{'python':platform.python_version(),'numpy':np.__version__},
        'exact':exact,'experiment':lab.run('export',{'include_data':True}),
        'query':lab.run('query',{'interventions':{'Y':1},'row':0})}
(root/'web/public/native-fixture.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
print('Generated native parity fixture with',len(lab.state['candidates']),'fitted candidates')
