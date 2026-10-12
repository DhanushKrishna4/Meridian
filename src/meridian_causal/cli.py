"""Reproducible local entry points. All outputs are computed by the package."""
import argparse
import json
from pathlib import Path
from .api import Laboratory


def main():
    parser=argparse.ArgumentParser(prog='meridian',description='Local causal inference laboratory')
    commands=parser.add_subparsers(dest='command',required=True)
    demo=commands.add_parser('demo',help='Run observe/discover/intervene/update and save a replayable experiment')
    demo.add_argument('--seed',type=int,default=7)
    demo.add_argument('--rows',type=int,default=800)
    demo.add_argument('--output',type=Path,default=Path('meridian-experiment.json'))
    fixture=commands.add_parser('fixture',help='Print exact covariance/intervention/counterfactual fixtures')
    fixture.add_argument('--output',type=Path)
    discover=commands.add_parser('discover',help='Analyze a local complete numerical CSV')
    discover.add_argument('csv',type=Path)
    discover.add_argument('--method',choices=['pc','notears'],default='pc')
    discover.add_argument('--columns',nargs='+')
    discover.add_argument('--output',type=Path,default=Path('meridian-experiment.json'))
    args=parser.parse_args()
    lab=Laboratory()
    if args.command=='fixture':
        output=lab.run('fixture')
    elif args.command=='demo':
        lab.run('load',{'world':'equivalence','seed':args.seed,'n':args.rows})
        lab.run('discover',{'method':'pc'})
        rankings=lab.run('rank')['rankings']
        chosen=rankings[0]
        lab.run('experiment',{**chosen,'n':100})
        output=lab.run('export',{'include_data':True})
        print(f'Experiment do({chosen["variable"]}={chosen["value"]:.4g}); candidates={len(lab.state["candidates"])}')
        print('Normalized plug-in likelihood support:',[round(c['weight'],6) for c in lab.state['candidates']])
    else:
        lab.run('load',{'csv':args.csv.read_text(), 'columns':args.columns})
        lab.run('discover',{'method':args.method})
        output=lab.run('export',{'include_data':True})
    text=json.dumps(output,indent=2,allow_nan=False)+'\n'
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text)
        print(f'Wrote {args.output}')
    else: print(text,end='')

if __name__=='__main__':main()
