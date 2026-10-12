"""Bundle shared Python and a pinned self-hosted Pyodide runtime. No compute service.

Use --offline after first download. Repeated builds verify package hashes and
refresh Python sources without redownloading. Pure Python ZIP has stable metadata.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.27.7'
BASE = f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'


def prepare(offline=False):
    runtime = ROOT/'web/public/runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT/'scripts/runtime-manifest.json').read_text())
    def obtain(name, digest=None):
        digest = digest or manifest.get(name)
        target = runtime/name
        if target.exists() and (digest is None or hashlib.sha256(target.read_bytes()).hexdigest() == digest):
            return target
        if offline:
            raise SystemExit(f'Missing runtime asset {name}; first run requires downloading pinned open-source assets.')
        print('Downloading', name, flush=True)
        # System curl uses the platform trust store (including macOS certificates).
        content = subprocess.check_output(['curl','--fail','--silent','--show-error','--location','--retry','2','--max-time','120',BASE+name])
        if digest and hashlib.sha256(content).hexdigest() != digest:
            raise ValueError('Runtime package integrity check failed: '+name)
        target.write_bytes(content)
        return target
    lock = json.loads(obtain('pyodide-lock.json').read_text())
    if lock['info']['version'] != VERSION:
        raise ValueError('Unexpected Pyodide version')
    for name in ['pyodide.mjs','pyodide.asm.js','pyodide.asm.wasm','python_stdlib.zip']:
        obtain(name)
    loaded = set()
    def package(name):
        if name in loaded:
            return
        item=lock['packages'][name]
        for dependency in item['depends']:
            package(dependency)
        obtain(item['file_name'],item['sha256'])
        loaded.add(name)
    package('numpy')
    package('scipy')
    out = ROOT/'web/public/python'
    out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(out/'meridian.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT/'src/meridian_causal').rglob('*.py')):
            info=zipfile.ZipInfo(path.relative_to(ROOT/'src').as_posix(),date_time=(2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,path.read_bytes())
    versions={'pyodide':VERSION,'python':lock['info']['python'],**{name:lock['packages'][name]['version'] for name in sorted(loaded)}}
    (ROOT/'web/public/runtime-versions.json').write_text(json.dumps(versions,indent=2)+'\n')
    print('Static runtime prepared:',versions)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--offline',action='store_true')
    prepare(parser.parse_args().offline)
