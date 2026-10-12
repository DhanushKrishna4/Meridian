"""Linear NOTEARS, squared loss with nonnegative L1 variable splitting.

Zheng et al. (2018); author convention W[parent,child] is B.T here.
Optimization weights, thresholded graph and OLS refit are distinct objects.
"""
from __future__ import annotations
import time
import numpy as np


def reconstruction(B, X):
    residual = X - X @ B.T
    return float(np.sum(residual * residual) / (2 * len(X))), -(residual.T @ X) / len(X)


def acyclicity(B):
    from scipy.linalg import expm
    e = expm(B * B)
    return float(np.trace(e) - len(B)), 2 * B * e.T


def threshold_graph(B, nodes, threshold):
    from meridian_causal.graphs import Graph
    if not np.isfinite(threshold) or threshold < 0:
        raise ValueError('Edge threshold must be finite and nonnegative.')
    weights = np.where(np.abs(B) >= threshold, B, 0.0)
    np.fill_diagonal(weights, 0)
    edges = [(nodes[p], nodes[c]) for c, p in zip(*np.nonzero(weights))]
    # A numerical optimizer can return opposing arrows. Preserve the raw weights,
    # but do not construct a contradictory simple-graph object from them.
    graph = None if any((b, a) in edges for a, b in edges) else Graph(nodes, edges)
    return graph, weights


def notears_steps(data, nodes, lambda1=.1, threshold=.2, standardize=True,
                  max_outer=30, max_inner=150, h_tol=1e-8, rho_max=1e16, timeout=20):
    """Yield completed bounded L-BFGS-B calls, then a final result event.

    A worker can yield its event loop between calls. Time checked during objective
    evaluations too. Bounds pin diagonal entries to zero without posthoc repair.
    """
    from scipy.optimize import minimize
    x = np.asarray(data, dtype=float)
    if x.ndim != 2 or x.shape[1] != len(nodes) or len(x) < 5 or not np.isfinite(x).all():
        raise ValueError('NOTEARS requires at least five complete finite rows matching variable IDs.')
    if len(nodes) != len(set(nodes)) or not 2 <= len(nodes) <= 15:
        raise ValueError('Use 2–15 unique variable IDs.')
    if not (0 <= lambda1 <= 100 and 0 <= threshold <= 100 and 0 < timeout <= 120):
        raise ValueError('Invalid NOTEARS penalty, threshold, or time budget.')
    if not (1 <= max_outer <= 100 and 1 <= max_inner <= 1000 and 0 < h_tol < 1):
        raise ValueError('Invalid optimization iteration budget or tolerance.')
    means = x.mean(axis=0)
    scales = x.std(axis=0, ddof=0) if standardize else np.ones(x.shape[1])
    if np.any(x.std(axis=0) <= 1e-14):
        raise ValueError('Constant columns cannot be used by NOTEARS.')
    z = (x - means) / scales
    d = z.shape[1]
    w = np.zeros(2 * d*d)
    bounds = [(0., 0.) if i == j else (0., None) for _ in range(2) for i in range(d) for j in range(d)]
    rho, multiplier, previous_h = 1., 0., np.inf
    trace, start = [], time.monotonic()
    converged, reason, iterations = False, 'outer iteration budget exhausted', 0
    B = np.zeros((d, d))
    status = 'optimizer did not converge'

    class Budget(Exception):
        pass

    def unpack(v):
        return (v[:d*d] - v[d*d:]).reshape(d, d)

    def objective(v):
        if time.monotonic() - start > timeout:
            raise Budget
        b = unpack(v)
        loss, grad = reconstruction(b, z)
        h, gh = acyclicity(b)
        val = loss + lambda1 * v.sum() + multiplier*h + rho*h*h/2
        g = grad + (multiplier + rho*h)*gh
        if not np.isfinite(val) or not np.isfinite(g).all():
            raise FloatingPointError('Nonfinite optimizer objective or gradient.')
        return val, np.concatenate([(g + lambda1).ravel(), (-g + lambda1).ravel()])

    try:
        for outer in range(max_outer):
            while rho < rho_max:
                solution = minimize(objective, w, jac=True, method='L-BFGS-B', bounds=bounds,
                                    options={'maxiter': max_inner, 'ftol': 1e-12, 'gtol': 1e-8, 'maxls': 30})
                candidate = unpack(solution.x)
                h, _ = acyclicity(candidate)
                loss, _ = reconstruction(candidate, z)
                iterations += int(solution.nit)
                event = {'outer': outer+1, 'inner_iterations': int(solution.nit), 'loss': loss,
                         'penalty': float(lambda1*np.abs(candidate).sum()), 'h': h, 'rho': rho,
                         'inner_success': bool(solution.success), 'message': str(solution.message),
                         'elapsed_seconds': time.monotonic()-start}
                trace.append(event)
                yield {'stage': 'NOTEARS optimization', 'completed': len(trace), 'message': f'Augmented step {outer+1}; h={h:.3g}', 'diagnostic': event}
                # Preserve only completed calls. Increasing rho retries the same dual iterate.
                B = candidate
                if h > .25 * previous_h:
                    rho *= 10
                else:
                    break
            w = np.concatenate([np.maximum(B,0).ravel(), np.maximum(-B,0).ravel()])
            previous_h, _ = acyclicity(B)
            multiplier += rho * previous_h
            if previous_h <= h_tol and trace[-1]['inner_success']:
                converged, reason, status = True, 'acyclicity tolerance and inner solver convergence reached', 'complete'
                break
            if rho >= rho_max:
                reason = 'penalty limit reached'
                break
    except Budget:
        status, reason = 'budget exhausted', 'elapsed-time budget exhausted; last completed inner solve retained'
    except (FloatingPointError, ValueError, OverflowError) as exc:
        status, reason = 'numerical failure', str(exc)
    graph, selected = threshold_graph(B, nodes, threshold)
    valid = graph is not None and graph.is_dag()
    if not valid:
        status = 'invalid candidate'
        reason += '; thresholded support contains a directed cycle (no edges silently removed)'
    h, _ = acyclicity(B)
    loss, _ = reconstruction(B, z)
    original_weights = B * scales[:, None] / scales[None, :]
    result = {'method': 'linear NOTEARS', 'status': status, 'converged': converged,
              'termination_reason': reason, 'graph_valid': valid,
              'graph': graph.to_dict() if graph is not None else {'nodes': list(nodes), 'directed': [], 'undirected': [],
                          'conflicts': [[nodes[p],nodes[c]] for c,p in zip(*np.nonzero(selected))]},
              'raw_weights': B.tolist(), 'raw_weights_original_units': original_weights.tolist(),
              'selected_weights': selected.tolist(), 'loss': loss,
              'penalty': float(lambda1*np.abs(B).sum()), 'h': h, 'iterations': iterations,
              'trace': trace, 'elapsed_seconds': time.monotonic()-start,
              'settings': {'lambda1': lambda1, 'threshold': threshold, 'max_outer': max_outer,
                           'max_inner': max_inner, 'h_tol': h_tol, 'timeout': timeout},
              'preprocessing': {'mode': 'standardized training data' if standardize else 'centered original units',
                                'mean': means.tolist(), 'scale': scales.tolist(), 'fit_role': 'training'},
              'interpretation': 'A score-selected candidate; directions are not observational proof of causation.'}
    yield {'result': result}


def notears(data, nodes, **kwargs):
    for event in notears_steps(data, nodes, **kwargs):
        if 'result' in event:
            return event['result']
