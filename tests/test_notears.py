import numpy as np
import pytest
from meridian_causal.discovery.notears import reconstruction, acyclicity, notears, threshold_graph


def finite_difference(fun, x):
    gradient=np.zeros_like(x)
    for index in np.ndindex(x.shape):
        hi,lo=x.copy(),x.copy()
        hi[index]+=1e-6; lo[index]-=1e-6
        gradient[index]=(fun(hi)-fun(lo))/2e-6
    return gradient


def test_gradients_and_author_convention():
    from scipy.linalg import expm
    rng=np.random.default_rng(17)
    x=rng.normal(size=(31,4))
    B=rng.normal(scale=.2,size=(4,4)); np.fill_diagonal(B,0)
    value,grad=reconstruction(B,x)
    np.testing.assert_allclose(grad,finite_difference(lambda b:reconstruction(b,x)[0],B),atol=1e-8)
    h,gh=acyclicity(B)
    np.testing.assert_allclose(gh,finite_difference(lambda b:acyclicity(b)[0],B),atol=1e-8)
    # Independent author equations use W[parent,child], X @ W.
    W=B.T
    residual=x-x@W
    assert value==pytest.approx(.5/len(x)*(residual**2).sum())
    np.testing.assert_allclose(grad,(-x.T@residual/len(x)).T)
    e=expm(W*W)
    assert h==pytest.approx(np.trace(e)-4)
    np.testing.assert_allclose(gh,(e.T*W*2).T)


def test_small_h_does_not_imply_thresholded_dag():
    B=np.array([[0,0,.001],[.001,0,0],[0,.001,0]])
    assert acyclicity(B)[0]<1e-8
    graph,_=threshold_graph(B,['X','Y','Z'],.0001)
    assert not graph.is_dag()
    graph,_=threshold_graph(np.array([[0,.01],[.01,0]]),['X','Y'],.001)
    assert graph is None  # explicitly invalid opposing arrows


def test_real_optimization_records_and_thresholds():
    rng=np.random.default_rng(21)
    x=rng.normal(size=(400,3)); x[:,1]+=1.2*x[:,0]; x[:,2]+=.8*x[:,1]
    result=notears(x,['X','Y','Z'],max_outer=20,timeout=10,standardize=False)
    assert len(result['trace'])>0
    assert result['graph_valid']
    assert np.diag(result['raw_weights']).tolist()==[0,0,0]
    assert result['h']<1e-5
    assert result['preprocessing']['mode']=='centered original units'
    assert result['iterations']>0
    assert result['status'] in ('complete','optimizer did not converge')


def test_budget_and_inner_failure_not_success():
    rng=np.random.default_rng(2)
    x=rng.normal(size=(200,5)); x[:,1]+=x[:,0]
    result=notears(x,list('ABCDE'),max_outer=1,max_inner=1)
    assert not result['converged']
    assert result['status']!='complete'
    result=notears(x,list('ABCDE'),timeout=1e-12)
    assert result['status']=='budget exhausted'
    assert result['termination_reason'].startswith('elapsed-time')


@pytest.mark.parametrize('data',[np.ones((20,2)),np.array([[np.nan,2]]*20)])
def test_bad_input(data):
    with pytest.raises(ValueError):notears(data,['X','Y'])
