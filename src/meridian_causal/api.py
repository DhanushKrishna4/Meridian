"""Transactional laboratory shared by native CLI and the Pyodide worker.

Simulator truth is accessed only by world loading, explicit reveal, and the
experiment oracle AFTER its plan is frozen. Learners only receive training rows.
"""
from __future__ import annotations
import copy
import json
import platform
import numpy as np
from . import __version__
from .data import parse_csv, diagnostics, split_indices, dataset_id, validate_nodes
from .graphs import Graph, enumerate_extensions, dag_to_cpdag, validate_pdag
from .scm import LinearSCM, fit_scm, check_backdoor, find_backdoor_sets
from .scm.worlds import make_world, simulate_world_experiment, equivalence_models, worlds
from .experiments import Campaign, rank_interventions
from .serialization import validate_json_tree


def _integer(value, low, high, label):
    if isinstance(value,bool) or not isinstance(value,int) or not low <= value <= high:
        raise ValueError(f'{label} must be an integer in [{low}, {high}].')
    return value


def _moments(pair):
    return {'mean':pair[0].tolist(), 'covariance':pair[1].tolist()}


def _units(value, nodes):
    if value is None:
        return {node:'original units' for node in nodes}
    if (not isinstance(value,dict) or set(value)!=set(nodes) or
        any(not isinstance(unit,str) or not unit.strip() or len(unit)>80 for unit in value.values())):
        raise ValueError('Units must map every variable ID to a nonempty label of at most 80 characters.')
    return dict(value)


def _selected_model(state):
    selected = state.get('selected')
    if selected == 'custom':
        raw = state.get('custom_model')
    elif selected == 'notears':
        raw = (state.get('notears') or {}).get('model')
    elif type(selected) is int and 0 <= selected < len(state['candidates']):
        raw = state['candidates'][selected]['model']
    else:
        raw = None
    if raw is None:
        raise ValueError('Select a valid fitted candidate or specify an acyclic structural model first.')
    return LinearSCM.from_dict(raw)


def _discovery_graph(result, nodes, method):
    """Validate stored completion claims without rerunning statistical discovery."""
    if not isinstance(result,dict):
        raise ValueError('Stored discovery result must be an object.')
    graph=Graph.from_dict(result.get('graph'))
    if list(graph.nodes)!=nodes:
        raise ValueError('Discovery variable IDs disagree.')
    if method=='pc':
        status=result.get('status')
        if status not in ('complete','budget_exhausted','numerical_failure','inconsistent_graph'):
            raise ValueError('Unknown PC completion status.')
        claimed_complete=result.get('graph_type')=='CPDAG'
        if claimed_complete != (status=='complete'):
            raise ValueError('PC completion status and CPDAG label disagree.')
        if claimed_complete and (not validate_pdag(graph,require_cpdag=True)['valid'] or
                                 result.get('conflicts') or result.get('ambiguous_triples') or result.get('invalid_tests')):
            raise ValueError('Stored PC result is not a consistent completed CPDAG.')
        trace=result.get('trace')
        if (not isinstance(trace,list) or not trace or not isinstance(trace[-1],dict) or
            trace[-1].get('type')!='finish' or trace[-1].get('status')!=status or trace[-1].get('graph')!=graph.to_dict()):
            raise ValueError('PC evidence trace does not match the final result.')
        for event in trace:
            if not isinstance(event,dict):
                raise ValueError('PC trace entries must be objects.')
            if 'graph' in event and list(Graph.from_dict(event['graph']).nodes)!=nodes:
                raise ValueError('PC trace graph IDs disagree.')
    else:
        status=result.get('status')
        if status not in ('complete','optimizer did not converge','budget exhausted','numerical failure','invalid candidate'):
            raise ValueError('Unknown NOTEARS completion status.')
        if type(result.get('graph_valid')) is not bool or result['graph_valid']!=graph.is_dag():
            raise ValueError('NOTEARS graph validity does not match its support.')
        if type(result.get('converged')) is not bool or (status=='complete' and not result['converged']):
            raise ValueError('NOTEARS convergence status is inconsistent.')
        if status=='complete' and not graph.is_dag():
            raise ValueError('A complete NOTEARS candidate must be acyclic.')
        if result.get('model') is not None:
            model=LinearSCM.from_dict(result['model'])
            if (list(model.nodes)!=nodes or model.graph!=graph or not graph.is_dag() or
                status in ('numerical failure','budget exhausted','invalid candidate')):
                raise ValueError('NOTEARS refit does not match a usable selected graph.')
    return graph


class Laboratory:
    def __init__(self):
        self.data = None
        self.state = {}
        self.campaign = None
        self.progress = None

    def run(self, action, payload=None):
        for event in self.steps(action,payload or {}):
            if 'result' in event:
                return event['result']

    def steps(self, action, payload):
        """Commit only a successfully completed operation; yield real work units."""
        before = copy.deepcopy((self.data,self.state,self.campaign))
        committed = False
        try:
            for event in self._steps(action,payload):
                # A delivered final result is the commit boundary. Closing a
                # generator at any earlier progress yield rolls its work back.
                committed = 'result' in event
                yield event
        finally:
            if not committed:
                self.data,self.state,self.campaign = before

    @property
    def train(self):
        return self.data[self.state['split']['training']]

    def session(self):
        return copy.deepcopy({**self.state,'data':self.data[:100].tolist(),'row_count':len(self.data)})

    def selected_model(self):
        return _selected_model(self.state)

    def _steps(self, action, p):
        if not isinstance(p,dict): raise ValueError('Action payload must be an object.')
        if action == 'fixture':
            models=equivalence_models()
            yield {'result':{'covariances':[m.moments()[1].tolist() for m in models],
                'do_y1':[m.moments({'Y':1})[0].tolist() for m in models],
                'do_y0_covariances':[m.moments({'Y':0})[1].tolist() for m in models],
                'counterfactual':models[0].counterfactual([1,1,1],{'Y':0}).tolist()}}
            return
        if action == 'load':
            seed=_integer(p.get('seed',7),0,2**32-1,'Seed')
            if 'csv' in p:
                x,nodes=parse_csv(p['csv'],p.get('columns'))
                name='csv'
                description='Local observational CSV. Directions require assumptions. Recommended experiments are proposals; measured batches must be imported separately.'
            else:
                n=_integer(p.get('n',800),20,5000,'Rows')
                name=p.get('world','equivalence')
                world=make_world(name,seed,n)
                x,nodes,description=world['data'],world['nodes'],world['description']
            report=diagnostics(x,nodes)
            if not report['valid']:
                raise ValueError('Input diagnostics: '+json.dumps(report)+' No rows were changed. Fix or deselect the affected columns.')
            self.data=x.copy()
            split=split_indices(len(x),seed)
            train_report=diagnostics(x[split['training']],nodes)
            if not train_report['valid']:
                raise ValueError('Training split is numerically invalid: '+json.dumps(train_report))
            self.state={'id':dataset_id(x,nodes),'world':name,'seed':seed,'nodes':list(nodes),
                'units':_units(p.get('units'),nodes),'diagnostics':report,
                'split':split,'description':description,'truth_available':name!='csv','pc':None,'notears':None,
                'candidates':[],'selected':None,'history':[],'custom_model':None,
                'assumptions':['linear Gaussian additive mechanisms','acyclicity','causal Markov','faithfulness','causal sufficiency','independent samples']}
            self.campaign=None
            yield {'result':self.session()}
            return
        if action == 'restore':
            self.restore(p.get('experiment'))
            yield {'result':self.session()}
            return
        if self.data is None: raise ValueError('Load a built-in world or local CSV first.')
        if action == 'discover':
            method=p.get('method','pc')
            if method == 'pc':
                from .discovery.pc import pc_stable
                yield {'stage':'PC-stable','message':'Testing conditional independences on training observations.'}
                result=pc_stable(self.train,self.state['nodes'],alpha=float(p.get('alpha',.01)),
                    max_depth=_integer(p.get('max_depth',3),0,13,'Conditioning depth'),
                    max_tests=_integer(p.get('max_tests',10000),1,20000,'Test budget'),
                    timeout=10,progress=self.progress)
                self.state['pc']=result
                self.state['candidates']=[]
                self.state['history']=[]
                self.state.pop('bootstrap',None)
                self.state['selected']=None
                self.campaign=None
                self.state['enumeration']={'complete':False,'reason':'Discovery did not yield a verified CPDAG','count':0}
                if result['status']=='complete' and result.get('graph_type')=='CPDAG':
                    yield {'stage':'Alternative explanations','message':'Enumerating compatible DAGs within a bounded search.'}
                    extensions=enumerate_extensions(Graph.from_dict(result['graph']),max_candidates=128,max_expansions=100000,timeout=5)
                    self.state['enumeration']={'complete':extensions.complete,'reason':extensions.reason,
                        'count':len(extensions.graphs),'expansions':extensions.expansions,
                        'label':'exhaustive' if extensions.complete else 'nonexhaustive bounded candidate list'}
                    models=[]
                    for i,g in enumerate(extensions.graphs):
                        models.append(fit_scm(self.train,g))
                        yield {'stage':'Fitting candidates','completed':i+1,'total':len(extensions.graphs)}
                    if models:
                        self.campaign=Campaign(models,candidate_set_complete=extensions.complete)
                        self.state['candidates']=[{'id':i,'graph':g.to_dict(),'model':m.to_dict(),'weight':1/len(models)}
                                                  for i,(g,m) in enumerate(zip(extensions.graphs,models))]
                        self.state['selected']=0
            elif method == 'notears':
                from .discovery.notears import notears_steps
                options={key:p[key] for key in ('lambda1','threshold','standardize') if key in p}
                for event in notears_steps(self.train,self.state['nodes'],**options):
                    if 'result' in event: result=event['result']
                    else: yield event
                result['model']=None
                if result['graph_valid'] and result['status'] not in ('numerical failure','budget exhausted'):
                    result['model']=fit_scm(self.train,Graph.from_dict(result['graph'])).to_dict()
                    result['refit']='Unpenalized OLS structural equations refitted on the same training rows; raw optimizer weights retained separately.'
                self.state['notears']=result
                if self.state.get('selected')=='notears': self.state.pop('bootstrap',None)
                if self.state.get('selected')=='notears' and result['model'] is None: self.state['selected']=None
            else: raise ValueError('Unknown discovery method.')
            yield {'result':self.session()}
        elif action == 'select':
            self.state['selected']=p.get('index')
            self.selected_model()
            self.state.pop('bootstrap',None)
            yield {'result':self.session()}
        elif action == 'model':
            model=LinearSCM.from_dict({**p,'provenance':'user-specified','fit_metadata':{}})
            if tuple(self.state['nodes'])!=model.nodes:
                raise ValueError('Custom model variable IDs and order must match the current dataset.')
            self.state.update(custom_model=model.to_dict(),selected='custom')
            self.state.pop('bootstrap',None)
            yield {'result':self.session()}
        elif action == 'query':
            model=self.selected_model()
            intervention=model._values(p.get('interventions',{}))
            row=_integer(p.get('row',0),0,len(self.data)-1,'Factual row')
            factual=self.data[row]
            descendants=sorted(set().union(*(model.graph.descendants(n) for n in intervention))) if intervention else []
            equations=[f'{node} := {intervention[node]:g} (structural equation replaced)' if node in intervention else
                f'{node} = {model.intercept[i]:.4g} '+''.join(f'{model.B[i,j]:+.4g} {other} ' for j,other in enumerate(model.nodes) if model.B[i,j]!=0)+f'+ U_{node}; Var(U)={model.noise_variances[i]:.4g}' for i,node in enumerate(model.nodes)]
            result={'nodes':list(model.nodes),'units':copy.deepcopy(self.state['units']),'observational':_moments(model.moments()),
                'conditional':_moments(model.condition(intervention)),'interventional':_moments(model.moments(intervention)),
                'factual':factual.tolist(),'counterfactual':model.counterfactual(factual,intervention).tolist(),
                'descendants':descendants,'equations':equations,'effects':model.total_effects().tolist(),
                'model_label':f'{model.provenance}; selected model {self.state["selected"]}; original units',
                'note':'Counterfactual conditional on this SCM, using its own abducted residuals. Graph uncertainty is not included.'}
            if p.get('treatment') and p.get('outcome'):
                result['backdoor']=check_backdoor(model.graph,p['treatment'],p['outcome'],p.get('adjustment',[]))
            yield {'result':result}
        elif action == 'rank':
            if self.campaign is None: raise ValueError('A valid PC candidate set is required for experiment disagreement ranking.')
            ranks=rank_interventions(list(self.campaign.models),self.train,values=p.get('values'),bounds=p.get('bounds'),
                                    candidate_set_complete=self.campaign.candidate_set_complete)
            yield {'result':{'rankings':ranks,'label':'Normalized mean + covariance disagreement heuristic across the current candidate list; not expected information gain.',
                            'candidate_set_complete':self.state['enumeration']['complete']}}
        elif action == 'experiment':
            if self.campaign is None: raise ValueError('Discover and fit candidate explanations before an experiment.')
            n=_integer(p.get('n',100),20,1000,'Experiment sample count')
            intervention=self.campaign.models[0]._values({p.get('variable'):p.get('value')})
            # The frozen plan is made before any simulator or future outcome access.
            plan=self.campaign.freeze(intervention,n,score=p.get('score',0))
            round_number=len(self.state['history'])+1
            seed=(self.state['seed']+10007*round_number)%(2**32)
            if p.get('csv') is not None:
                batch,nodes=parse_csv(p['csv'],self.state['nodes'])
                if nodes!=self.state['nodes'] or len(batch)!=n:
                    raise ValueError('Measured intervention CSV must match variable IDs and the frozen sample count.')
                source='imported measured intervention batch'
            elif self.state['world']=='csv':
                if not p.get('simulate_model'):
                    raise ValueError('Uploaded data has no experiment oracle. Import a measured batch or explicitly choose a selected-model simulation.')
                batch=self.selected_model().simulate(n,seed,intervention)
                source='selected-model simulation; not measured evidence'
            else:
                batch=simulate_world_experiment(self.state['world'],seed,n,intervention,world_seed=self.state['seed'])
                source='simulated experiment oracle'
            record=self.campaign.update(plan,batch,batch_id=f'{self.state["id"]}:round:{round_number}')
            record.update(source=source,seed=seed,outcomes=batch.tolist())
            self.state['history'].append(record)
            for candidate,weight in zip(self.state['candidates'],self.campaign.weights): candidate['weight']=float(weight)
            yield {'result':self.session()}
        elif action == 'truth':
            if self.state['world']=='csv': raise ValueError('No generating truth is available for uploaded observations.')
            truth=make_world(self.state['world'],self.state['seed'],1)['truth']
            if isinstance(truth,LinearSCM):
                result={'graph':truth.graph.to_dict(),'model':truth.to_dict(),'description':'Simulator ground truth, revealed after inference. This does not change discovery results.'}
            else:
                model=LinearSCM.from_dict(truth['model'])
                result={'graph':model.graph.to_dict(),'model':truth['model'],'description':truth['description'],'assumption_violation':truth['assumption_violation']}
            yield {'result':result}
        elif action == 'bootstrap':
            from .discovery.pc import pc_stable
            replicates=_integer(p.get('replicates',10),2,40,'Bootstrap replicates')
            model=self.selected_model()
            rng=np.random.default_rng(self.state['seed']+500000)
            edges, directed, effects, failures, effect_failures={}, {}, [], [], []
            completed=0
            settings=(self.state.get('pc') or {}).get('settings',{})
            for i in range(replicates):
                draw=self.train[rng.integers(0,len(self.train),len(self.train))]
                result=pc_stable(draw,self.state['nodes'],alpha=settings.get('alpha',.01),max_depth=settings.get('max_depth',3),max_tests=3000,timeout=3)
                if result['status']=='complete':
                    completed+=1
                    graph=Graph.from_dict(result['graph'])
                    for edge in graph.skeleton(): edges[' — '.join(edge)]=edges.get(' — '.join(edge),0)+1
                    for edge in graph.directed: directed[' → '.join(edge)]=directed.get(' → '.join(edge),0)+1
                else: failures.append({'replicate':i,'status':result['status']})
                try: effects.append(fit_scm(draw,model.graph).total_effects())
                except ValueError as exc: effect_failures.append({'replicate':i,'reason':str(exc)})
                yield {'stage':'Bootstrap','completed':i+1,'total':replicates,'message':f'{completed} successful graph replicates; {len(failures)} incomplete/failed.'}
            result={'replicates':replicates,'completed':completed,'failures':failures,'effect_failures':effect_failures,
                'status':'complete' if not failures and not effect_failures else 'completed with failed replicates',
                'skeleton_frequency':{k:v/completed for k,v in edges.items()} if completed else {},
                'orientation_frequency':{k:v/completed for k,v in directed.items()} if completed else {},
                'effect_lower':np.quantile(effects,.025,axis=0).tolist() if effects else None,
                'effect_upper':np.quantile(effects,.975,axis=0).tolist() if effects else None,
                'selected_model':self.state['selected'],
                'interpretation':'Graph frequencies are bootstrap stability among successful replicates, not causal probabilities. Percentile effect intervals condition on the chosen graph and omit graph uncertainty.'}
            self.state['bootstrap']=result
            yield {'result':result}
        elif action == 'export':
            yield {'result':self.export(bool(p.get('include_data',True)),bool(p.get('include_truth',False)))}
        else: raise ValueError(f'Unknown action: {action!r}')

    def export(self, include_data=True, include_truth=False):
        if self.data is None: raise ValueError('No experiment to export.')
        result={'schema_version':1,'package_version':__version__,
            'dataset':{'id':self.state['id'],'nodes':list(self.state['nodes']),'data':self.data.tolist() if include_data else None,
                       'world':self.state['world'],'seed':self.state['seed'],'rows':len(self.data),
                       'units':copy.deepcopy(self.state['units']),'raw_data_included':include_data},
            'state':copy.deepcopy(self.state),'campaign':self.campaign.to_dict() if self.campaign else None,
            'reproducibility':{'python':platform.python_version(),'numpy':np.__version__,
                               'matrix_convention':'B[child,parent]','truth_included':include_truth,
                               'replay':'Stored choices, parameters and outcomes; restore never reruns discovery or a campaign.'}}
        if include_truth and self.state['world']!='csv': result['simulator_truth']=self.run('truth',{})
        return result

    def restore(self, experiment):
        # Bound the untrusted tree before copying or allocating numeric arrays.
        e=validate_json_tree(experiment)
        if not isinstance(e,dict) or type(e.get('schema_version')) is not int or e['schema_version']!=1:
            raise ValueError('Unsupported experiment schema; Meridian expects schema_version 1.')
        d=e.get('dataset',{})
        if not isinstance(d,dict): raise ValueError('Stored dataset must be an object.')
        nodes=validate_nodes(d.get('nodes'))
        n=_integer(d.get('rows'),20,5000,'Stored row count')
        seed=_integer(d.get('seed'),0,2**32-1,'Stored seed')
        name=d.get('world')
        if name not in ['csv']+[w['id'] for w in worlds()]: raise ValueError('Invalid dataset provenance.')
        raw=d.get('data')
        if type(d.get('raw_data_included')) is not bool or d['raw_data_included']!=(raw is not None):
            raise ValueError('Raw data inclusion flag disagrees with the stored dataset.')
        if raw is not None and (not isinstance(raw,list) or len(raw)!=n or
            any(not isinstance(row,list) or len(row)!=len(nodes) or
                any(type(value) not in (int,float) for value in row) for row in raw)):
            raise ValueError('Stored data dimensions/types are invalid.')
        # Validate row/column bounds before making a second copy of the import
        # or allocating generated/numerical arrays. Detach only a valid shape.
        e=copy.deepcopy(e)
        d=e['dataset']
        raw=d.get('data')
        generated=make_world(name,seed,n) if name!='csv' else None
        if generated is not None and generated['nodes']!=nodes:
            raise ValueError('Built-in provenance does not match the stored variable IDs.')
        if raw is None:
            if name=='csv': raise ValueError('This export omitted uploaded raw data. Restore requires a data-inclusive export.')
            x=generated['data']
        else:
            x=np.array(raw,dtype=float)
        if raw is None and dataset_id(x,nodes)!=d.get('id'):
            raise ValueError('Regenerated dataset identity differs on this runtime. Restore a data-inclusive export for exact replay.')
        if not np.isfinite(x).all() or dataset_id(x,nodes)!=d.get('id'):
            raise ValueError('Dataset values or identity do not match this experiment.')
        # Stored bytes define identity. Regeneration checks provenance within a
        # tight tolerance because native and WebAssembly BLAS may round apart.
        if generated is not None and not np.allclose(generated['data'],x,rtol=1e-12,atol=1e-12):
            raise ValueError('Built-in provenance does not match the stored observations.')
        s=e.get('state')
        if not isinstance(s,dict) or s.get('nodes')!=nodes or s.get('id')!=d['id'] or s.get('world')!=name or s.get('seed')!=seed:
            raise ValueError('Stored state and dataset identity disagree.')
        if s.get('split')!=split_indices(n,seed): raise ValueError('Stored data split is inconsistent.')
        units=_units(s.get('units'),nodes)
        if 'units' in d and _units(d['units'],nodes)!=units: raise ValueError('Stored variable units disagree.')
        if type(s.get('truth_available')) is not bool or s['truth_available']!=(name!='csv'):
            raise ValueError('Simulator truth availability disagrees with dataset provenance.')
        if not diagnostics(x,nodes)['valid'] or not diagnostics(x[s['split']['training']],nodes)['valid']:
            raise ValueError('Stored observations or training split fail input diagnostics.')
        history=s.get('history')
        if not isinstance(history,list) or len(history)>1000: raise ValueError('Invalid experiment history.')
        pc_graph=None
        for key in ('pc','notears'):
            if s.get(key) is not None:
                graph=_discovery_graph(s[key],nodes,key)
                if key=='pc': pc_graph=graph
        candidates=s.get('candidates')
        if not isinstance(candidates,list) or len(candidates)>128: raise ValueError('Invalid candidate count.')
        seen_graphs=set()
        for i,c in enumerate(candidates):
            if not isinstance(c,dict): raise ValueError('Stored candidate must be an object.')
            m=LinearSCM.from_dict(c['model']); g=Graph.from_dict(c['graph'])
            if list(m.nodes)!=nodes or list(g.nodes)!=nodes or not g.is_dag() or m.graph!=g or type(c.get('id')) is not int or c['id']!=i:
                raise ValueError('Invalid candidate graph or model.')
            if (pc_graph is None or s['pc']['status']!='complete' or dag_to_cpdag(g)!=pc_graph or
                not pc_graph.directed<=g.directed or g.directed in seen_graphs):
                raise ValueError('Candidate is duplicate or not a consistent extension of the stored PC graph.')
            seen_graphs.add(g.directed)
            if type(c.get('weight')) not in (int,float) or not 0<=c['weight']<=1: raise ValueError('Invalid candidate support weight.')
        if candidates and abs(sum(c['weight'] for c in candidates)-1)>1e-8: raise ValueError('Support weights do not sum to one.')
        enumeration=s.get('enumeration')
        if pc_graph is not None or candidates:
            if (not isinstance(enumeration,dict) or type(enumeration.get('complete')) is not bool or
                type(enumeration.get('count')) is not int or enumeration['count']!=len(candidates)):
                raise ValueError('Stored candidate enumeration metadata is inconsistent.')
            if enumeration['complete'] and (not candidates or s['pc']['status']!='complete'):
                raise ValueError('An exhaustive candidate set requires completed PC discovery and at least one DAG.')
            if enumeration.get('label') not in (None,'exhaustive' if enumeration['complete'] else 'nonexhaustive bounded candidate list'):
                raise ValueError('Stored candidate enumeration label is inconsistent.')
        if s.get('custom_model') is not None:
            model=LinearSCM.from_dict(s['custom_model'])
            if list(model.nodes)!=nodes or model.provenance!='user-specified': raise ValueError('Custom model IDs or provenance disagree.')
        campaign=Campaign.from_dict(e['campaign']) if e.get('campaign') is not None else None
        if bool(candidates)!=bool(campaign): raise ValueError('Candidate campaign is missing or inconsistent.')
        if campaign:
            for c,m,w in zip(candidates,campaign.models,campaign.weights):
                if c['model']!=m.to_dict() or abs(c['weight']-w)>1e-10: raise ValueError('Campaign candidates/support disagree.')
            if (len(candidates)!=len(campaign.models) or len(history)!=len(campaign.history) or
                campaign.candidate_set_complete!=enumeration['complete']):
                raise ValueError('Campaign history or candidate scope does not match.')
            # Stored outcomes replay exactly; never call a simulator on restore.
            for saved,record in zip(history,campaign.history):
                if not isinstance(saved,dict): raise ValueError('Stored experiment record must be an object.')
                for k,v in record.items():
                    if saved.get(k)!=v: raise ValueError('Campaign records were altered.')
                _integer(saved.get('seed'),0,2**32-1,'Stored experiment seed')
                if saved.get('source') not in ('imported measured intervention batch','selected-model simulation; not measured evidence','simulated experiment oracle'):
                    raise ValueError('Stored experiment evidence source is invalid.')
                if name=='csv' and saved['source']=='simulated experiment oracle':
                    raise ValueError('Uploaded observations cannot have simulator oracle outcomes.')
                campaign.verify_outcomes(record,saved.get('outcomes'))
        elif history:
            raise ValueError('Experiment history requires its fixed candidate campaign.')
        if s.get('selected') is not None: _selected_model(s)
        s['units']=units
        # Direct restore() calls are atomic too: no mutation precedes validation.
        self.data=x; self.state=s; self.campaign=campaign
