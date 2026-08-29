# Projection Exactness + Nullspace Lab contract

**Status:** bounded diagnostic contract. It adds no physical law, transfer
family, production solver, force, constitutive state, or persistent numerical
mode.

**Accepted parent:** Projection Foundation Lab at
`beac8861314e9a2c18e59fd65c426cfdbf75882c`, including evidence v2. That
evidence remains immutable and its candidates remain unpromoted.

## 1. Question and state boundary

The exact finite model says that affine center data and a partition-of-unity,
linearly reproducing basis admit the explicit nodal witness

\[
g_i=A(t)x_i+b(t),\qquad Mg=q,
\]

with `M=S^T W S` and `q=S^T W V`. The previous binary64 PCG path produced
small backward residuals but failed affine forward/reconstruction gates. This
lab distinguishes assembly arithmetic, solver conditioning, and Gram
nullspace visibility.

Authoritative physical input remains only packet-center ID, exact mass quanta,
position in metres, and velocity in metres per second. Grid nodes, matrices,
factorizations, high-precision numbers, null vectors, and velocity gradients
are transient diagnostics and never enter a checkpoint or future motion.

The architecture rule remains: a causally active numerical auxiliary must be
uniquely derivable from physical state or represented as explicitly accounted
physical state. No persistent affine or polynomial particle mode is allowed.

## 2. Operators and units

For particles `p` and deterministically ordered active nodes `i`,

\[
S_{pi}=N_i(x_p),\quad W_{pp}=m_p,
\]

\[
M_{ij}=\sum_p m_pS_{pi}S_{pj}\;[\mathrm{kg}],\qquad
q_i=\sum_pm_pS_{pi}V_p\;[\mathrm{kg\,m\,s^{-1}}].
\]

The tensor-product quadratic B-spline gradient is evaluated analytically from
the same normalized coordinate and node index used for `S`:

\[
\nabla N_i(x_p)\;[\mathrm{m^{-1}}].
\]

For a scalar grid null mode `z_i` normalized to a declared `1 m/s` amplitude,
the mechanics-visible gradient is

\[
G_p(z)=\sum_i z_i\nabla N_i(x_p)\;[\mathrm{s^{-1}}].
\]

There is no physical update law in this lab. At diagnostic time `t`, particles
are constructed analytically from the force-free affine map

\[
x_p(t)=x_p(0)+t(A_0x_p(0)+b_0),\qquad V_p(t)=V_p(0),
\]

\[
A(t)=A_0(I+tA_0)^{-1},\qquad b(t)=(I+tA_0)^{-1}b_0,
\]

under the already formalized explicit inverse assumption. Translation has
`A=0`. Orientation acts on the entire physical configuration, not on output
labels.

## 3. Direct affine witness

Before invoking any solver, construct `g` at active-node positions and report
independently:

- `||Mg-q||` and normwise dimensionless backward residual;
- `||Sg-V||` and mass-normalized reconstruction residual;
- partition-of-unity and linear-reproduction residuals; and
- `||sum_i grad N_i||`, the derivative-of-partition residual.

The witness uses the exact binary64 `M`, `q`, stencils, and node positions
assembled by C++. It does not rebuild a friendlier matrix. Failure halts the
lab before PCG, high precision, or nullspace interpretation.

## 4. Backward versus forward error

The accepted PCG implementation is called without changing its initialization,
preconditioner, recurrence, thresholds, or iteration cap. It is a historical
control, not a newly accepted solver.

For each component of every applicable solve report

\[
\eta=\frac{\lVert M\hat v-q\rVert_2}
{\lVert M\rVert_F\lVert\hat v\rVert_2+\lVert q\rVert_2},
\]

the forward error against known `g`, particle reconstruction error, raw and
diagonally preconditioned spectral diagnostics, diagnostic provenance, and
`kappa*eta`. A residual-only pass is never called an accurate solve. Forward
and reconstruction tolerances are dimensionless norms whose dimensional
scales are stated in the preregistration.

Dense Jacobi values and large-system Lanczos/Ritz values are numerical
estimates, not certified condition numbers. The evidence says which path
produced each value. A structural dimension bound is exact; floating rank and
condition diagnostics are not formal certificates.

## 5. Independent higher-precision path

A separate dense solver promotes the already assembled binary64 `M` and `q`
without changing a coefficient. It uses deterministic complete-pivot Gaussian
elimination in an error-free-transform double-double representation with about
106 significand bits—substantially more than binary64. It performs no diagonal
shift, regularization, node drop, pseudoinverse, altered basis, or fallback to
the production PCG path.

The path reports pivot order, numerical rank threshold, backward error,
forward error against `g`, reconstruction error, and a numerical condition
diagnostic. Its rank/condition findings are labeled numerical, not certified.
It is a reference diagnostic and permanently promotion-ineligible.

A separately coded Python decimal oracle reconstructs and solves the smaller
exported full-rank systems from the evidence tables. Shared inputs are allowed;
shared numerical solver code is not.

## 6. Gram nullspace diagnosis

Lean proves over the actual finite operators and strictly positive masses:

\[
M=S^TWS,\qquad \ker(M)=\ker(S).
\]

Consequently, if `Mv1=q` and `Mv2=q`, then `S v1=S v2` without assuming
invertibility. This is an exact center-reconstruction statement, not a claim
that grid derivatives are unique.

Numerically, deterministic Householder QR with column pivoting is applied to
`sqrt(W)S` on selected singular systems. Its rank threshold is preregistered.
It produces diagnostic grid-null vectors. For every emitted mode, the lab
records `Mz`, `Sz`, the residual/reconstruction change between `g` and
`g+alpha z`, and `G_p(z)`. Diagnostic QR representatives or pseudoinverses are
never candidates and never affect packet state.

## 7. Conservation and physical-accounting boundary

Exact mass quanta and center IDs cannot change because every operation is
read-only. No numerical residual is transferred to thermal, stored,
structural, chemical, or other physical energy. Linear/angular/energy values
may be observed, but this lab introduces no physical transition whose
conservation could be claimed.

## 8. Failure modes

Preserve and distinguish:

- affine witness/assembly inconsistency;
- nonfinite or overflowed assembly/metric;
- old PCG structural stop, breakdown, iteration limit, or residual-only pass
  with forward failure;
- unresolved or estimated condition/rank evidence;
- high-precision pivot/rank failure or failure to recover the known witness;
- QR rank ambiguity;
- a claimed null vector with resolved `Mz` or `Sz` error;
- center-invisible but gradient-visible modes;
- phase/orientation dependence;
- independent Python disagreement;
- nondeterministic output, schema mismatch, or manifest/checkpoint regression.

No failed configuration is removed, regularized, or silently replaced.

## 9. Tests and claim boundary

Unit tests cover the analytic B-spline derivative, witness metrics, backward
versus forward separation, double-double arithmetic/solve controls, QR rank
and null-vector construction, `Mz/Sz`, gradient visibility, permutation
determinism, zero/invalid state, overflow, and no persistent state expansion.

Numerical tests do not establish physical validity. Lean proves only the exact
finite algebra it encodes. High precision diagnoses the assembled system; it
does not validate continuum mechanics. The lab ends with a diagnostic result
and cannot promote a transfer or authorize constitutive mechanics.
