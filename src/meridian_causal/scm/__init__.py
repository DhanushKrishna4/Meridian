"""Explicit acyclic linear Gaussian structural models in original data units.

Every coefficient is ``B[child, parent]``. A fitted or specified SCM is an
assumption-bearing object, distinct from a causal-discovery result.
"""

from .linear import LinearSCM, fit_scm, check_backdoor, find_backdoor_sets

__all__ = ["LinearSCM", "fit_scm", "check_backdoor", "find_backdoor_sets"]
