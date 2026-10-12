import copy
import json
import numpy as np
import pytest
from meridian_causal.api import Laboratory
from meridian_causal.data import parse_csv, diagnostics
from meridian_causal.scm import LinearSCM
from meridian_causal.serialization import loads


def js_json_numbers(value):
    """Model JSON.stringify's integral-float and signed-zero rewriting."""
    if isinstance(value,dict):
        return {key:js_json_numbers(item) for key,item in value.items()}
    if isinstance(value,list):
        return [js_json_numbers(item) for item in value]
    if isinstance(value,float) and value.is_integer():
        return int(value)
    return value


def lab():
    l=Laboratory(); l.run('load',{}); l.run('discover',{'method':'pc'}); return l


def test_complete_campaign_restore_and_truth_isolation():
    l=lab()
    assert len(l.state['candidates'])==3
    prior=copy.deepcopy(l.state)
    l.run('truth',{})
    assert l.state==prior
    ranks=l.run('rank',{})['rankings']
    assert ranks[0]['score']>0
    l.run('experiment',{**ranks[0],'n':100})
    assert max(c['weight'] for c in l.state['candidates'])>.95
    snapshot=json.loads(json.dumps(l.run('export',{}),allow_nan=False))
    restored=Laboratory(); restored.run('restore',{'experiment':snapshot})
    assert restored.state==l.state
    assert restored.run('query',{'interventions':{'Y':0}})==l.run('query',{'interventions':{'Y':0}})
    # Subsequent deterministic experiment uses original world and new batch seed.
    restored.run('experiment',{'variable':'Y','value':0,'n':40})
    assert len(restored.state['history'])==2


def test_training_boundary_and_rollback():
    l=lab(); state=copy.deepcopy(l.state)
    with pytest.raises(ValueError):l.run('select',{'index':888})
    assert l.state==state
    # Modifying evaluation rows cannot affect a fresh discovery result.
    original=l.state['pc']['graph']
    l.data[l.state['split']['evaluation']]*=100
    l.run('discover',{'method':'pc'})
    assert l.state['pc']['graph']==original


def test_csv_never_fabricates_experiments():
    l=Laboratory()
    rng=np.random.default_rng(23); x=rng.normal(size=(200,3)); x[:,1]+=.8*x[:,0]; x[:,2]+=.8*x[:,1]
    csv='X,Y,Z\n'+'\n'.join(','.join(map(str,row)) for row in x)
    l.run('load',{'csv':csv}); l.run('discover',{'method':'pc'})
    with pytest.raises(ValueError,match='no experiment oracle'):l.run('experiment',{'variable':'Y','value':1})
    assert not l.state['history']
    with pytest.raises(ValueError,match='No generating truth'):l.run('truth',{})
    exported=l.run('export',{'include_data':False})
    with pytest.raises(ValueError,match='omitted uploaded raw'):Laboratory().run('restore',{'experiment':exported})


def test_invalid_csv_and_explicit_column_selection():
    text='name,A,B\n'+'\n'.join(f'p{i},{i},{i*i}' for i in range(30))
    x,nodes=parse_csv(text,['A','B'])
    assert x.shape==(30,2) and nodes==['A','B']
    with pytest.raises(ValueError,match='nonnumerical'):parse_csv(text)
    assert not diagnostics(np.ones((30,2)),['A','B'])['valid']
    bad='A,B\n'+'\n'.join('1,' for _ in range(30))
    with pytest.raises(ValueError,match='Missing/nonfinite'):Laboratory().run('load',{'csv':bad})


@pytest.mark.parametrize('mutation',[
 lambda e:e.update(schema_version=9),
 lambda e:e['dataset']['data'][0].append(2),
 lambda e:e['dataset']['data'][0].__setitem__(0,float('nan')),
 lambda e:e['state']['split']['training'].append(5),
 lambda e:e['state']['candidates'][0]['model']['noise_variances'].__setitem__(0,-1),
 lambda e:e['state']['candidates'][0]['model']['B'][0].__setitem__(0,1),
])
def test_import_validation(mutation):
    e=lab().run('export',{}); mutation(e)
    with pytest.raises((ValueError,KeyError)):Laboratory().run('restore',{'experiment':e})


def test_safe_json_rejects_infinite_and_deep():
    with pytest.raises(ValueError):loads('{"x":NaN}')
    with pytest.raises(ValueError):loads('['*30+'0'+']'*30)


def test_bootstrap_small_actual_replicates():
    l=lab(); r=l.run('bootstrap',{'replicates':3})
    assert r['replicates']==3 and r['completed']==3
    assert np.asarray(r['effect_lower']).shape==(3,3)
    assert 'not causal probabilities' in r['interpretation']


def campaign_export():
    laboratory=lab()
    laboratory.run('experiment',{'variable':'Y','value':0,'n':30})
    return laboratory.run('export',{})


def test_restore_rejects_changed_outcomes_even_with_a_new_matching_digest():
    import hashlib
    snapshot=campaign_export()
    saved=snapshot['state']['history'][0]
    saved['outcomes'][0][0]+=1
    with pytest.raises(ValueError,match='digest'):
        Laboratory().restore(snapshot)
    # Recomputing a digest cannot substitute for recomputing the fixed-model
    # structural likelihoods. This checks the numerical replay boundary too.
    digest=hashlib.sha256(json.dumps(js_json_numbers({'intervention':saved['plan']['intervention'],'data':saved['outcomes']}),
                                    sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    saved['batch_digest']=digest
    snapshot['campaign']['history'][0]['batch_digest']=digest
    snapshot['campaign']['batch_digests']=[digest]
    with pytest.raises(ValueError,match='likelihoods.*replay'):
        Laboratory().restore(snapshot)


def test_restore_recomputes_likelihood_even_when_weights_still_replay():
    snapshot=campaign_export()
    # A common likelihood shift preserves every weight. A full export must
    # still reject it because the recorded observations have fixed densities.
    for record in (snapshot['state']['history'][0],snapshot['campaign']['history'][0]):
        record['log_likelihoods']=[value+10 for value in record['log_likelihoods']]
    with pytest.raises(ValueError,match='likelihoods.*replay'):
        Laboratory().restore(snapshot)


@pytest.mark.parametrize('outcomes',[[],[[1,0]]*30,[[True,0,1]]*30,[[1,0,'1']]*30])
def test_restore_rejects_invalid_outcome_dimensions_and_types(outcomes):
    snapshot=campaign_export()
    snapshot['state']['history'][0]['outcomes']=outcomes
    with pytest.raises(ValueError,match='batch dimensions'):
        Laboratory().restore(snapshot)


@pytest.mark.parametrize('mutation',[
    lambda e:e.update(schema_version=True),
    lambda e:e['state'].update(selected=True),
    lambda e:e['dataset'].update(raw_data_included=False),
    lambda e:e['state']['units'].update(X=''),
    lambda e:e['dataset']['units'].update(X='different units'),
    lambda e:e['state']['pc'].update(status='made up'),
    lambda e:e['state']['pc'].update(status='budget_exhausted'),
    lambda e:e['state']['pc'].update(graph_type='DAG'),
    lambda e:e['state']['pc']['trace'][-1].update(status='inconsistent_graph'),
    lambda e:e['state']['enumeration'].update(count=100),
    lambda e:e['state']['enumeration'].update(complete=False),
    lambda e:e['state']['candidates'][0].update(weight=True),
    lambda e:e['state'].update(truth_available=False),
])
def test_restore_rejects_inconsistent_completion_and_scope_metadata(mutation):
    snapshot=lab().export()
    mutation(snapshot)
    with pytest.raises(ValueError):
        Laboratory().restore(snapshot)


def test_restore_rejects_candidate_outside_the_discovered_equivalence_class():
    snapshot=lab().export()
    collider=LinearSCM(['X','Y','Z'],[[0,0,0],[.8,0,.8],[0,0,0]],[0,0,0],[1,1,1])
    snapshot['state']['candidates'][0].update(graph=collider.graph.to_dict(),model=collider.to_dict())
    with pytest.raises(ValueError,match='consistent extension'):
        Laboratory().restore(snapshot)


def test_direct_restore_failure_preserves_all_existing_state():
    laboratory=lab()
    before=laboratory.export()
    invalid=copy.deepcopy(before)
    invalid['state']['selected']=999
    with pytest.raises(ValueError):
        laboratory.restore(invalid)
    assert laboratory.export()==before


def test_closing_incomplete_operation_rolls_back_discovery_and_campaign():
    laboratory=lab()
    laboratory.run('experiment',{'variable':'Y','value':0,'n':30})
    before=laboratory.export()
    operation=laboratory.steps('discover',{'method':'pc','alpha':.02})
    for event in operation:
        if event.get('stage')=='Alternative explanations':
            break
    assert laboratory.state['history']==[]
    operation.close()
    assert laboratory.export()==before
    # Returning at the final event is the commit boundary used by the worker.
    operation=laboratory.steps('select',{'index':1})
    assert 'result' in next(operation)
    operation.close()
    assert laboratory.state['selected']==1


def test_fit_failure_rolls_back_new_discovery(monkeypatch):
    laboratory=lab()
    before=laboratory.export()
    def fail_fit(*args,**kwargs):
        raise ValueError('test numerical failure')
    monkeypatch.setattr('meridian_causal.api.fit_scm',fail_fit)
    with pytest.raises(ValueError,match='numerical failure'):
        laboratory.run('discover',{'method':'pc','alpha':.02})
    assert laboratory.export()==before


def test_units_model_provenance_and_candidate_scope_follow_query_and_rank():
    laboratory=Laboratory()
    units={'X':'mm','Y':'kg','Z':'seconds'}
    laboratory.run('load',{'units':units})
    laboratory.run('discover',{})
    assert laboratory.run('query',{})['units']==units
    ranking=laboratory.run('rank',{'values':{'Y':[0]}})
    assert ranking['candidate_set_complete']
    assert ranking['rankings'][0]['candidate_set_complete']
    custom=laboratory.selected_model().to_dict()
    laboratory.run('model',custom)
    assert laboratory.selected_model().fit_metadata=={}
    assert 'user-specified' in laboratory.run('query',{})['model_label']
    restored=Laboratory()
    restored.restore(laboratory.export())
    assert restored.run('query',{})['units']==units


def test_native_wasm_last_bit_differences_do_not_reject_included_data(monkeypatch):
    import meridian_causal.api as api
    laboratory=lab()
    included=laboratory.export()
    omitted=laboratory.export(include_data=False)
    original=api.make_world
    def changed_rounding(*args,**kwargs):
        world=original(*args,**kwargs)
        world['data'][0,0]=np.nextafter(world['data'][0,0],np.inf)
        return world
    monkeypatch.setattr(api,'make_world',changed_rounding)
    restored=Laboratory()
    restored.restore(included)
    assert restored.state==laboratory.state
    np.testing.assert_array_equal(restored.data,laboratory.data)
    with pytest.raises(ValueError,match='data-inclusive'):
        Laboratory().restore(omitted)


def test_json_rejects_duplicate_keys_and_deep_payload_before_copy():
    with pytest.raises(ValueError,match='Duplicate'):
        loads('{"schema_version":1,"schema_version":1}')
    value=[]
    for _ in range(1500): value=[value]
    with pytest.raises(ValueError,match='nesting'):
        Laboratory().restore(value)


@pytest.mark.parametrize('mutation',[
    lambda e:e['dataset'].update(rows=5001),
    lambda e:e['dataset'].update(data=e['dataset']['data']+[e['dataset']['data'][0]]),
    lambda e:e['dataset']['data'][0].append(1),
])
def test_import_dimensions_are_checked_before_copying_or_allocating(mutation,monkeypatch):
    snapshot=lab().export()
    mutation(snapshot)
    def forbidden(*args,**kwargs):
        raise AssertionError('Unvalidated dataset was copied or generated.')
    monkeypatch.setattr('meridian_causal.api.copy.deepcopy',forbidden)
    monkeypatch.setattr('meridian_causal.api.make_world',forbidden)
    with pytest.raises(ValueError,match='row count|dimensions'):
        Laboratory().restore(snapshot)


def test_export_and_restore_are_detached_from_mutable_callers():
    laboratory=lab()
    before=laboratory.export()
    snapshot=laboratory.export()
    snapshot['dataset']['nodes'][0]='changed'
    snapshot['state']['candidates'][0]['model']['B'][0][0]=999
    assert laboratory.export()==before
    restored=Laboratory()
    restored.restore(before)
    expected=restored.export()
    before['state']['nodes'][0]='changed'
    before['dataset']['data'][0][0]=999
    before['campaign']['models'][0]['fit_metadata']['n']=999
    assert restored.export()==expected


def test_complete_campaign_restores_after_browser_number_serialization():
    laboratory=lab()
    laboratory.run('experiment',{'variable':'Y','value':-0.0,'n':30})
    snapshot=js_json_numbers(json.loads(json.dumps(laboratory.export())))
    assert type(snapshot['state']['candidates'][0]['model']['fit_metadata']['diagnostics'][0]['condition']) is int
    restored=Laboratory()
    restored.restore(snapshot)
    assert restored.state==laboratory.state
    assert restored.campaign.to_dict()==laboratory.campaign.to_dict()
    restored.run('experiment',{'variable':'Y','value':1,'n':30})
    assert len(restored.state['history'])==2


def test_csv_signed_zero_identity_survives_browser_export():
    from meridian_causal.data import dataset_id
    laboratory=Laboratory()
    rng=np.random.default_rng(51)
    rows=rng.normal(size=(100,2))
    rows[0,0]=-0.0
    csv='A,B\n'+'\n'.join(','.join(map(str,row)) for row in rows)
    laboratory.run('load',{'csv':csv})
    assert np.signbit(laboratory.data[0,0])
    snapshot=js_json_numbers(laboratory.export())
    restored=Laboratory()
    restored.restore(snapshot)
    assert restored.state['id']==dataset_id(rows,['A','B'])
    np.testing.assert_array_equal(restored.data,laboratory.data)
    assert np.signbit(laboratory.data[0,0])  # identity computation never changes data
