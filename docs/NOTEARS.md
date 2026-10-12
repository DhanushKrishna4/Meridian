# Linear NOTEARS

Meridian minimizes `||X - X B.T||²/(2n) + lambda1 ||B||₁` under
`h(B) = trace(expm(B ∘ B)) - d = 0`, with `B[child,parent]`.
The squared-loss derivative is `-(X-X B.T).T X/n`; the constraint derivative
is `2 B ∘ expm(B ∘ B).T`. Nonnegative positive/negative variables make the
L1 term smooth; both diagonal blocks are fixed to zero in the optimizer bounds.

The augmented Lagrangian uses multiplier updates and a geometrically increased
penalty, with bounded L-BFGS-B calls. Progress contains completed optimizer calls,
loss, penalty, acyclicity residual, penalty strength, elapsed time, inner solver
status, and iteration count. The worker yields between calls. The wall-time
budget is also checked during objective evaluation. Native numerical errors,
time limits, inner nonconvergence and outer limits remain visible.

Convergence requires both the requested acyclicity tolerance and inner solver
success. **Thresholded support is checked separately for directed cycles.** A
small residual is not a substitute. Opposing arrows produce an explicit invalid
candidate, with raw weights retained; no direction is silently selected. A
thresholded DAG from an unconverged run may be inspected and refitted, but its
optimizer status is retained and must not be called a converged optimum.

Centering or standardization parameters are fit on training observations only.
`raw_weights` uses the optimization units; `raw_weights_original_units` applies
`B_original[i,j] = B_scaled[i,j] * scale[i]/scale[j]`. The edge threshold is in
optimization units. The selected graph is refitted by unpenalized OLS in original
units for SCM queries; those coefficients are separate from penalized weights.

Changing measurement scale can change the selected graph. Standardization is
explicit and does not make NOTEARS directions observationally identified.
Results are candidate model choices, conditional on an acyclic linear model and
a sparsity objective; observational equivalence remains relevant.

## References and verification

- [Zheng et al., DAGs with NO TEARS (2018)](https://arxiv.org/abs/1803.01422)
- [Author implementation](https://github.com/xunzheng/notears/blob/master/notears/linear.py): its `W[parent,child]` is Meridian's `B.T`.
- [Reisach et al., Beware of the Simulated DAG! (2021)](https://proceedings.neurips.cc/paper_files/paper/2021/hash/e987eff4a7c7b7e580d659feb6f60c1a-Abstract.html)

`tests/test_notears.py` finite-difference checks both gradients, compares objective
and derivatives against the transposed author formulas, exercises genuine
optimization and iteration/time failures, and includes a cyclic-support fixture
whose acyclicity residual is below `1e-8`.
