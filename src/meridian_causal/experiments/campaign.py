"""Frozen plans and normalized plug-in likelihood support, without refitting."""

from __future__ import annotations

import copy
import hashlib
import json

import numpy as np

from meridian_causal.scm import LinearSCM
from meridian_causal.serialization import validate_json_tree
from .selection import validate_models


def _digest(value):
    # JSON.stringify has one number type: 1.0 becomes 1 and -0.0 becomes 0.
    # Hash numeric values rather than a Python-specific spelling so that a
    # browser export can replay the same models, plans and outcomes natively.
    def canonical(item):
        if isinstance(item, dict):
            return {key: canonical(value) for key, value in item.items()}
        if isinstance(item, (list, tuple)):
            return [canonical(value) for value in item]
        if isinstance(item, float) and np.isfinite(item) and item.is_integer():
            return int(item)
        return item
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _numeric_vector(value, length, label):
    if (not isinstance(value,list) or len(value)!=length or
        any(type(v) not in (int,float) for v in value)):
        raise ValueError(f"{label} must be a numeric list matching candidate count.")
    result=np.asarray(value,dtype=float)
    if not np.isfinite(result).all():
        raise ValueError(f"{label} must be finite.")
    return result


def _batch_rows(data, count, width):
    if isinstance(data,np.ndarray):
        valid=data.shape==(count,width) and data.dtype.kind in 'iuf'
    else:
        valid=(isinstance(data,(list,tuple)) and len(data)==count and
               all(isinstance(row,(list,tuple)) and len(row)==width and
                   all(type(value) in (int,float) for value in row) for row in data))
    if not valid:
        raise ValueError("Experimental batch dimensions and numeric types must match the frozen plan.")
    rows=np.asarray(data,dtype=float)
    if not np.isfinite(rows).all():
        raise ValueError("Experimental batch must contain only finite values.")
    return rows


def intervention_log_likelihood(model, data, interventions):
    """Structural conditional log densities of all nonreplaced mechanisms.

    The clamped variable contributes no density, but its value remains in the
    parent predictors of every other equation. No singular full Gaussian is used.
    """
    interventions = model._values(interventions)
    data = np.asarray(data, dtype=float)
    if data.ndim != 2 or data.shape[1] != len(model.nodes) or not 1 <= len(data) <= 1_000_000 or not np.isfinite(data).all():
        raise ValueError("Experimental data must be a finite, nonempty row matrix aligned with model IDs.")
    for node, value in interventions.items():
        column = data[:, model.nodes.index(node)]
        if not np.allclose(column, value, rtol=1e-10, atol=1e-10):
            raise ValueError(f"Measured column {node} does not match the planned hard intervention {value}.")
    free = [i for i, node in enumerate(model.nodes) if node not in interventions]
    if not free:
        return 0.
    residuals = data[:, free] - model.intercept[free] - data @ model.B[free].T
    variance = model.noise_variances[free]
    with np.errstate(over="ignore", invalid="ignore"):
        result = -.5 * (len(data) * np.log(2 * np.pi * variance).sum() + np.sum(residuals**2 / variance))
    if not np.isfinite(result):
        raise ValueError("Experimental likelihood overflowed; inspect scales and noise variances.")
    return float(result)


class Campaign:
    """Fixed candidate snapshots, immutable plans, each experimental batch used once.

    A content digest detects accidental plan/model mutation; it is not a security
    signature. No world object, truth coefficient, or evaluation data is accepted.
    """

    def __init__(self, models, *, candidate_set_complete=True):
        validate_models(models)
        if not isinstance(candidate_set_complete, bool):
            raise ValueError("candidate_set_complete must be boolean.")
        self._models = tuple(LinearSCM.from_dict(model.to_dict()) for model in models)
        self._candidate_digest = _digest([model.to_dict() for model in self._models])
        self.candidate_set_complete = candidate_set_complete
        self._log_support = np.zeros(len(models))
        self._plans = {}
        self._used_batches = set()
        self._used_plans = set()
        self._batch_digests = set()
        self._history = []

    @property
    def models(self):
        return tuple(LinearSCM.from_dict(model.to_dict()) for model in self._models)

    @property
    def weights(self):
        shifted = self._log_support - self._log_support.max()
        probability = np.exp(shifted)
        return probability / probability.sum()

    @property
    def history(self):
        return copy.deepcopy(self._history)

    def freeze(self, intervention, n, score=0):
        values = self._models[0]._values(intervention)
        if not values:
            raise ValueError("An experimental plan must replace at least one equation.")
        if isinstance(n, bool) or not isinstance(n, (int, np.integer)) or not 1 <= n <= 5000:
            raise ValueError("Experimental batch size must be an integer from 1 to 5000.")
        if isinstance(score, (bool, str)) or not np.isscalar(score) or not np.isfinite(score) or score < 0:
            raise ValueError("The frozen disagreement score must be finite and nonnegative.")
        if len(self._plans) >= 1000:
            raise ValueError("Campaign plan budget exhausted (1000).")
        plan = {"sequence": len(self._plans), "intervention": values, "n": int(n), "score": float(score),
                "candidate_digest": self._candidate_digest, "candidate_count": len(self._models),
                "candidate_set_complete": self.candidate_set_complete}
        plan["plan_id"] = _digest(plan)
        self._plans[plan["plan_id"]] = copy.deepcopy(plan)
        return copy.deepcopy(plan)

    def update(self, plan, data, batch_id):
        if not isinstance(plan, dict) or not isinstance(plan.get("plan_id"), str) or plan.get("plan_id") not in self._plans or plan != self._plans[plan["plan_id"]]:
            raise ValueError("Experiment must use an unaltered plan frozen before outcomes are supplied.")
        if _digest([model.to_dict() for model in self._models]) != self._candidate_digest:
            raise ValueError("Campaign candidate parameters changed after freezing.")
        if not isinstance(batch_id, str) or not batch_id or len(batch_id) > 200:
            raise ValueError("Every evidence batch requires a nonempty ID of at most 200 characters.")
        if batch_id in self._used_batches or plan["plan_id"] in self._used_plans:
            raise ValueError("This evidence batch or frozen plan was already used; evidence cannot be counted twice.")
        rows = _batch_rows(data,plan["n"],len(self._models[0].nodes))
        # IDs alone cannot prevent relabeling the same numerical batch.
        batch_digest = _digest({"intervention": plan["intervention"], "data": rows.tolist()})
        if batch_digest in self._batch_digests:
            raise ValueError("These experimental observations have already been counted under another batch ID.")
        log_likelihoods = np.array([intervention_log_likelihood(model, rows, plan["intervention"]) for model in self._models])
        # Subtract the common offset every round; weights remain stable indefinitely.
        updated = self._log_support + log_likelihoods - log_likelihoods.max()
        if not np.isfinite(updated).all():
            raise ValueError("Cumulative likelihood overflowed; no evidence was added.")
        self._log_support = updated - updated.max()
        self._used_batches.add(batch_id)
        self._used_plans.add(plan["plan_id"])
        self._batch_digests.add(batch_digest)
        record = {"batch_id": batch_id, "batch_digest": batch_digest, "plan": copy.deepcopy(plan),
                  "log_likelihoods": log_likelihoods.tolist(), "weights": self.weights.tolist(),
                  "label": "normalized plug-in likelihood support; not Bayesian posterior probabilities",
                  "candidate_set_complete": self.candidate_set_complete}
        self._history.append(copy.deepcopy(record))
        return record

    def verify_outcomes(self, record, data):
        """Replay stored observations without consuming evidence or calling an oracle.

        Campaign summaries can check likelihood arithmetic alone. A full
        laboratory restore additionally checks these exact outcome contents and
        recomputes every nonreplaced structural density from its fixed models.
        """
        plan=record['plan']
        rows=_batch_rows(data,plan['n'],len(self._models[0].nodes))
        digest=_digest({'intervention':plan['intervention'],'data':rows.tolist()})
        if digest!=record['batch_digest']:
            raise ValueError('Stored experiment outcomes do not match their evidence digest.')
        likelihoods=np.array([intervention_log_likelihood(model,rows,plan['intervention']) for model in self._models])
        if not np.allclose(likelihoods,record['log_likelihoods'],rtol=1e-10,atol=1e-9):
            raise ValueError('Stored experimental likelihoods do not replay from the recorded outcomes.')

    def to_dict(self):
        return {"schema_version": 1, "models": [model.to_dict() for model in self._models],
                "candidate_set_complete": self.candidate_set_complete, "candidate_digest": self._candidate_digest,
                "log_support": self._log_support.tolist(), "plans": list(copy.deepcopy(self._plans).values()),
                "used_batches": sorted(self._used_batches), "used_plans": sorted(self._used_plans),
                "batch_digests": sorted(self._batch_digests), "history": self.history}

    @classmethod
    def from_dict(cls, payload):
        validate_json_tree(payload)
        if not isinstance(payload, dict) or type(payload.get("schema_version")) is not int or payload["schema_version"] != 1:
            raise ValueError("Unsupported campaign schema version.")
        models = payload.get("models")
        if not isinstance(models, list) or not 1 <= len(models) <= 128:
            raise ValueError("Campaign requires 1–128 serialized models.")
        result = cls([LinearSCM.from_dict(model) for model in models], candidate_set_complete=payload.get("candidate_set_complete", True))
        if payload.get("candidate_digest") != result._candidate_digest:
            raise ValueError("Campaign candidate digest does not match its models.")
        logs = _numeric_vector(payload.get('log_support'),len(models),'Campaign log support')
        for key in ("plans", "used_batches", "used_plans", "batch_digests", "history"):
            if not isinstance(payload.get(key), list) or len(payload[key]) > 1000:
                raise ValueError(f"Campaign {key} must be a bounded list.")
        for plan in payload["plans"]:
            if not isinstance(plan, dict):
                raise ValueError("Invalid frozen campaign plan.")
            expected = result.freeze(plan.get("intervention"), plan.get("n"), plan.get("score"))
            if expected != plan:
                raise ValueError("Frozen plan content or identity was modified.")
        try:
            used_batches, used_plans, batch_digests = (set(payload[key]) for key in ("used_batches", "used_plans", "batch_digests"))
        except TypeError as exc:
            raise ValueError("Campaign identifiers must be strings.") from exc
        if any(not isinstance(item, str) or not item or len(item) > 200 for values in (used_batches, used_plans, batch_digests) for item in values):
            raise ValueError("Campaign identifiers must be bounded nonempty strings.")
        if not used_plans <= result._plans.keys() or any(len(payload[key]) != len(values) for key, values in zip(("used_batches", "used_plans", "batch_digests"), (used_batches, used_plans, batch_digests))):
            raise ValueError("Campaign has duplicate evidence IDs or unknown used plans.")
        history = payload["history"]
        if not len(history) == len(used_batches) == len(used_plans) == len(batch_digests):
            raise ValueError("Campaign evidence history is inconsistent.")
        replay_logs = np.zeros(len(models))
        seen_batches, seen_plans, seen_digests = set(), set(), set()
        for record in history:
            if not isinstance(record, dict) or not isinstance(record.get("plan"), dict):
                raise ValueError("Invalid campaign evidence record.")
            plan = record["plan"]
            batch_id, batch_digest, plan_id = record.get("batch_id"), record.get("batch_digest"), plan.get("plan_id")
            if any(not isinstance(value,str) for value in (batch_id,batch_digest,plan_id)):
                raise ValueError('Campaign evidence identities must be strings.')
            if (batch_id not in used_batches or batch_id in seen_batches or batch_digest not in batch_digests or batch_digest in seen_digests
                or plan_id not in used_plans or plan_id in seen_plans or plan != result._plans[plan_id]):
                raise ValueError("Campaign evidence record has duplicate or unknown identities.")
            if (type(record.get('candidate_set_complete')) is not bool or
                record['candidate_set_complete']!=result.candidate_set_complete or
                record.get('label')!='normalized plug-in likelihood support; not Bayesian posterior probabilities'):
                raise ValueError('Campaign evidence interpretation or candidate scope was changed.')
            likelihoods = _numeric_vector(record.get('log_likelihoods'),len(models),'Campaign likelihoods')
            with np.errstate(over='ignore',invalid='ignore'):
                replay_logs += likelihoods - likelihoods.max()
                replay_logs -= replay_logs.max()
            if not np.isfinite(replay_logs).all():
                raise ValueError('Campaign replay overflowed; accumulated support is invalid.')
            weights = np.exp(replay_logs)
            weights /= weights.sum()
            recorded_weights=_numeric_vector(record.get('weights'),len(models),'Campaign weights')
            if not np.allclose(recorded_weights, weights, rtol=1e-10, atol=1e-12):
                raise ValueError("Campaign weights do not replay from recorded likelihoods.")
            seen_batches.add(batch_id)
            seen_plans.add(plan_id)
            seen_digests.add(batch_digest)
        if not np.allclose(logs - logs.max(), replay_logs, rtol=1e-10, atol=1e-10):
            raise ValueError("Campaign accumulated support does not match evidence history.")
        result._log_support = replay_logs
        result._used_batches, result._used_plans, result._batch_digests = used_batches, used_plans, batch_digests
        result._history = copy.deepcopy(history)
        return result
