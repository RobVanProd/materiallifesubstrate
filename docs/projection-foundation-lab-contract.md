# Projection Foundation Lab contract

**Status:** bounded force-free projection experiment.  
**Promotion authority:** none. A result may retain or reject a research
candidate, but it cannot start constitutive mechanics.

## 1. Architecture boundary

The only persistent physical inputs used by this lab are particle center
position, exact positive mass quanta, center velocity, and exact physical
clock. A transient grid may be reconstructed from those values and discarded.

A causally active numerical auxiliary that affects later physical motion must
be uniquely derivable from authoritative physical state or be declared as
accounted physical state. Consequently no persistent `B`, `C`, affine mode,
polynomial mode, grid velocity, solver iterate, factorization, correction
field, angular reservoir, or numerical-energy reservoir is permitted.

The lab adds no force, stress, elasticity, plasticity, gravity, contact,
fracture, diffusion, chemistry, organism, rendering, or GPU path.

## 2. Center state, units, and support

Each experimental center contains:

| Variable | Unit/type | Meaning |
|---|---|---|
| `id` | unsigned integer | deterministic debug/replay identity |
| `mass_quanta` | checked positive integer | exact extensive mass |
| `position_m` | binary64 metres | physical center position |
| `velocity_m_per_s` | binary64 m/s | physical center velocity |

`TransferConfig` supplies grid spacing in metres, origin in metres, and
kilograms per exact mass quantum. The complete tensor-product quadratic
B-spline stencil supplies `S_pi=N_i(x_p)`. Grid adjacency is not physical
locality; the grid is only the declared projection basis.

Particles are reduced in ascending ID order. Active nodes are the union of
all exactly nonzero stencil weights and are ordered lexicographically by
integer `(x,y,z)` index. There is no epsilon weight pruning. Every matrix,
vector, hash, and serialization uses these orders.

## 3. Common finite projection

For particles `p` and active nodes `i`, let

\[
S_{pi}=N_i(x_p),\quad W=\operatorname{diag}(m_p),
\]

\[
M=S^TWS,\quad q=S^TWV,
\quad D_{ii}=\sum_jM_{ij}=\sum_pm_pS_{pi}.
\]

The matrix is assembled or applied in particle-ID, local-row, local-column
order. Its scalar coefficients are shared by X, Y, and Z. `q`, not `Dv`, is
the grid momentum conjugate to the consistent velocity degrees of freedom.

All paths reconstruct particle center velocity as

\[
V'_p=\sum_iS_{pi}v_i.
\]

This direct reconstruction is the MLS experimental cycle described in the
source audit. It is not Love–Sulsky Eq. (32).

## 4. Experimental paths

### Lumped mass / PIC

\[
v_i=D_{ii}^{-1}q_i.
\]

This is the historical negative control.

### Full consistent mass

\[
Mv=q.
\]

The unregularized full system is the reference candidate. A deterministic
preconditioned conjugate-gradient solve may apply `M` matrix-free, but the
reported residual is always evaluated against the defined full matrix
operator. A small dense independent solve is required on bounded audit cases.

The implementation never adds a diagonal shift, blends with lumped mass,
drops a node/configuration, chooses a pseudoinverse, or changes the basis.

### FMPM(k)

Use the revised 2026 recurrence with `A=I-D^-1M`:

\[
\delta v^{(1)}=D^{-1}q,
\]

\[
\delta v^{(\ell)}=\delta v^{(\ell-1)}
 -D^{-1}M\delta v^{(\ell-1)},
\quad
v^{(k)}=\sum_{\ell=1}^k\delta v^{(\ell)}.
\]

Only `k=1,2,3,4` are tested. FMPM(1) must match the separately implemented
lumped/PIC result. The audit identity

\[
q-Mv^{(k)}=D\delta v^{(k+1)}
\]

is checked independently. No momentum or angular post-correction is allowed.

## 5. Solve and conditioning contract

Invalid inputs throw before a transition. A valid but unsolved projection
returns a failed status, complete diagnostics, and unchanged particle state.

Required statuses include `solved`, `empty`, `structurally_rank_deficient`,
`numerically_rank_deficient`, `ill_conditioned`, `breakdown`,
`iteration_limit`, and `residual_failed`.

Required diagnostics include:

- particle and active-node counts, nonzero/shape-entry counts, and deterministic
  node-order digest;
- exact mass before and after;
- structural rank upper bound `min(particles,active_nodes)`;
- numerical rank method and estimate, with an explicit `estimated` flag;
- smallest/largest pivot or Ritz value and raw/preconditioned condition
  estimate;
- matrix symmetry, row-sum, partition-unity, and linear-reproduction residuals;
- per-component absolute and normalized `Mv-q` residuals;
- iteration counts and named termination reason.

`active_nodes > particles` is a proof of rank deficiency. It is not the only
possible singularity. Dense pivot diagnostics are used for preregistered small
cases. Larger cases use deterministic scaled Lanczos/PCG diagnostics and must
label condition/rank values as estimates. An unresolved, nonfinite, or
threshold-exceeding condition fails closed.

The frozen full-solve numerical policy is:

| Quantity | Gate |
|---|---:|
| zero/negative lumped node mass | fail |
| structural rank upper bound below active nodes | fail |
| dense relative pivot | `> 1e-12` |
| estimated raw condition | `<= 1e10` |
| estimated preconditioned condition | `<= 1e8` |
| normalized component residual | `<= 5e-12` |
| iterations | at most `min(4*n,10000)` |
| Lanczos diagnostic steps | `min(n,64)` |

These thresholds diagnose this reference implementation; they are not
properties supplied by the literature. A low residual cannot override a rank
or condition failure.

## 6. Force-free time transition

After projection, every path uses the same Nairn–Hammerquist trapezoidal
center update with `alpha=1/2`:

\[
x_p^{n+1}=x_p^n+rac{\Delta t}{2}(V_p^n+V_p^{n+1}).
\]

The grid is discarded and rebuilt at the next step from center state only.
The analytic force-free material reference is

\[
x_p^*(t)=x_p(0)+tV_p(0),\qquad V_p^*(t)=V_p(0).
\]

Exact elapsed time is stored as integer time quanta. `Tick` is not silently
reinterpreted as seconds. Binary64 `dt` is a dimensioned numerical input and
must agree with the declared quantum scale.

## 7. Canonical experimental checkpoint

A lab checkpoint contains format/version, projection-independent config,
exact clock scale and elapsed quanta, and centers sorted by ID. It contains no
grid, active-node map, matrix, RHS, factorization, recurrence increment,
solver state, or diagnostic residual.

Serialization is canonical little-endian with a checksum. Decode rejects
duplicates, invalid mass/time, noncanonical ordering, nonfinite center state,
corruption, trailing bytes, and unsupported versions. A byte round trip must
be exact. Continuing the same method from original and restored center state
must reproduce canonical terminal bytes in deterministic reference mode.

This codec is experimental and does not change the authoritative MLS World
checkpoint or physics ABI.

## 8. Metrics

Every applicable result records these quantities independently:

1. exact mass quanta and exact clock;
2. material velocity normalized RMS error;
3. material trajectory normalized RMS error;
4. particle linear momentum relative error;
5. center orbital angular momentum relative error;
6. center physical kinetic-energy relative change;
7. consistent grid quadratic energy `q dot v / 2`;
8. grid representation error against the accurately solved full reference;
9. particle reconstruction error;
10. full-system projection residual;
11. matrix rank and condition diagnostics;
12. phase and proper signed-axis orientation sensitivity; and
13. for FMPM(k), grid and reconstructed-particle distance from full mass.

For affine fields, grid representation additionally compares nodal values to
the exact affine Eulerian field at the current particle configuration when the
map is invertible. For the smooth non-affine field, no exact-reproduction
requirement is invented; only refinement against the force-free material
reference and distance to the full discrete reference are gated.

Normalized particle RMS for vector state `z` is

\[
E_z=\frac{\sqrt{\sum_pm_p\lVert z_p-z_p^*\rVert^2/\sum_pm_p}}
{\max(1,\sqrt{\sum_pm_p\lVert z_p^*\rVert^2/\sum_pm_p})}.
\]

Scalar/vector totals use the symmetric relative error

\[
R(a,b)=\frac{\lVert a-b\rVert}{\max(1,\lVert a\rVert,\lVert b\rVert)}.
\]

FMPM distance to full is reported in both lumped `D` norm on the grid and
mass `W` norm after particle reconstruction. Missing, inapplicable, and failed
full-reference values remain explicit `NA`, never zero.

## 9. Momentum, angular momentum, and energy boundaries

Under exact normal equations and partition of unity, direct consistent
reconstruction preserves linear momentum. With linear reproduction, it also
preserves center orbital angular momentum at unchanged particle positions.
These static statements do not automatically prove a time-transition
invariant.

Finite FMPM preserves linear momentum in exact arithmetic but has no generic
angular theorem. Its angular error equals a rotational moment of its
consistent-system residual and is an expected candidate property.

Center particle kinetic energy is physical diagnostic state. Consistent grid
quadratic energy, projection loss/gain, solve error, FMPM residual, and
candidate/full distance are numerical diagnostics. None is converted into
thermal, stored, structural, chemical, or other physical energy merely to
close a ledger. Generic kinetic-energy conservation is not a candidate gate.

## 10. Failure preservation and interpretation

Evidence preserves invalid configuration, integer/count/index overflow,
duplicate ID, empty/zero state, zero lumped mass, singularity, ill
conditioning, nonconvergence, solver breakdown, nonfinite output, residual
failure, input-order dependence, phase/orientation sensitivity, timestep
sensitivity, particle-quadrature sensitivity, checkpoint/replay disagreement,
and independent-oracle disagreement.

A unit test establishes only its stated software property. It does not make
an observed behavior physically valid. A failed full solve cannot be hidden
by a visually plausible FMPM result. No result from this lab authorizes
constitutive mechanics.
