# Projection Exactness + Nullspace Lab preregistration

**Frozen before final sweep:** 2026-08-29 on branch
`projection-exactness-nullspace-lab`.  
**Seed:** `260828` for provenance and deterministic adversarial ordering. The
registered lattices themselves are deterministic.

No tolerance or selection below may change after inspecting the final sweep.

## 1. Fixed affine states

Reuse the Projection Foundation translation, rigid-rotation, and general
affine fields exactly. Use physical times `0` and exactly four quanta of the
`1/160 s` clock, hence `t=1/40 s`. At nonzero time construct ballistic center
positions and the analytic convected Eulerian `A(t),b(t)`; do not advance them
through a numerical transfer path.

Reuse phases `p000=(0,0,0)` and `p049_001_083=(0.49,0.01,0.83)h`, and proper
signed-axis orientations `p012_sppp` and `p210_sppm` from the accepted lab.
Density is `1 kg/m^3`, domain is the same half-open unit cube, registered mass
is exactly `4096` quanta or `1 kg`, and node order is lexicographic.

## 2. Frozen 76-system matrix

### Main matrix: 72 systems

Use all Cartesian combinations of:

- three affine fields;
- two analytic times;
- two phases;
- two orientations; and
- the three old levels below.

| Level | `h` m | `dx_p` m | particles | ppc | mass quanta/particle |
|---:|---:|---:|---:|---:|---:|
| 0 | `1/2` | `1/4` | 64 | 8 | 64 |
| 1 | `1/4` | `1/8` | 512 | 8 | 8 |
| 2 | `1/8` | `1/16` | 4,096 | 8 | 1 |

The analytic witness and unchanged-PCG control are emitted for every row,
including structural failures.

### Two full-rank micro controls

Use general affine, `t=0`, `h=1/2 m`, `dx_p=1/8 m`, 512 particles and eight
mass quanta per particle for:

1. `p000/p012_sppp`; and
2. `p049_001_083/p210_sppm`.

### Two ppc=1 singular controls

Use general affine, `t=0`, `h=1/4 m`, `dx_p=1/4 m`, 64 particles and 64 mass
quanta per particle at the hard phase, once per orientation.

Total systems: `72+2+2=76`. No row may be dropped.

## 3. High-precision subset: exactly four systems

The double-double complete-pivot reference runs on:

1. main general-affine `t=0`, level 1, `p000/p012_sppp`;
2. main general-affine `t=0`, level 1,
   `p049_001_083/p210_sppm`; and
3. both full-rank micro controls.

The first two are exact prior-failure geometries. The smaller two permit an
independent Python decimal solve. A high-precision system that is not
numerically full rank remains a failed selected row; it is not replaced.

Double-double pivot rank uses

\[
\tau_{pivot}=2^{12}n\,\epsilon_{dd}\max_{ij}|M_{ij}|,
\]

where `epsilon_dd=2^-104` and `n` is the node count. Backward acceptance is the
same normwise formula as below with tolerance

\[
\tau_{dd}=2^{12}n\epsilon_{dd}.
\]

Forward and reconstructed-particle acceptance both use `5e-10` in their
declared dimensionless norms, inherited from the earlier affine gate. Passing
high-precision residual alone is insufficient.

## 4. Singular subset: exactly ten systems

Run rank/nullspace/gradient diagnosis on:

- main general-affine level 0 at both times, both phases, and both
  orientations: eight systems; and
- both ppc=1 singular controls.

Apply deterministic Householder QR with column pivoting to `sqrt(W)S`. Let
`r00` be the first absolute diagonal pivot. The numerical rank threshold is

\[
\tau_{QR}=128\max(P,N)\epsilon_{64}\max(r_{00},\mathrm{minnormal}).
\]

Emit every constructed free-column null basis vector, scaled so
`max_i |z_i|=1 m/s`. Rank is always labeled a numerical estimate.

## 5. Roundoff-scaled witness gates

Let

\[
\gamma(k)=\frac{k\epsilon_{64}}{1-k\epsilon_{64}},
\]

and fail if its denominator is nonpositive. Let `s` be the largest stencil
size, `c` the largest number of particle contributions to one active node,
and `r` the largest matrix-row nonzero count in that system. Record all three.

| Witness | Dimensionless/absolute tolerance |
|---|---:|
| partition of unity | `32 gamma(s)` |
| linear reproduction | `64 gamma(s) max(1 m,h,||x_p||)` |
| derivative partition | `64 gamma(3s) max(1 m^-1,1/h)` |
| `Sg-V` normalized | `128 gamma(s)` |
| `Mg-q` normwise backward | `128 gamma(max(r,c,2s))` |

`Mg-q` is normalized by

\[
\lVert |M||g|\rVert_2+\lVert q\rVert_2,
\]

component by component. `Sg-V` uses the particle mass norm divided by
`max(sqrt(sum_p m_p||V_p||^2),sqrt(sum_p m_p)*(1 m/s))`. A zero denominator is
an implementation error, not an automatic pass.

If any selected system fails any witness gate, set the bounded decision to
`stop_assembly_or_basis_inconsistency` and do not execute PCG, high precision,
or nullspace diagnosis in the final run.

## 6. Solver error metrics and acceptance

For PCG and high precision, report per component:

\[
\eta=\frac{\lVert M\hat v-q\rVert_2}
{\lVert M\rVert_F\lVert\hat v\rVert_2+\lVert q\rVert_2}.
\]

Grid forward error uses the lumped-mass norm

\[
E_g=\frac{\sqrt{\sum_iD_i(\hat v_i-g_i)^2}}
{\max(\sqrt{\sum_iD_i g_i^2},\sqrt{\sum_iD_i}(1\;m/s))}.
\]

Particle reconstruction uses the analogous `W` norm against `V`. The target
for both is `5e-10`. Record `kappa*eta`; never substitute it for measured
forward error. The old PCG termination threshold remains unchanged and is
reported separately. An old residual pass with `E_g` failure is explicitly
`backward_pass_forward_fail`, never `accurate`.

Condition provenance must be one of `dense_numerical_estimate`,
`ritz_lanczos_estimate`, `high_precision_inverse_norm_estimate`, or
`unavailable`. Only a mathematically proved bound may be labeled certified;
none is preregistered here.

## 7. Nullspace and gradient gates

For each unit-amplitude mode, require

\[
\frac{\lVert Mz\rVert_2}{\max(\lVert M\rVert_F\lVert z\rVert_2,
\mathrm{minnormal})}
\le 512\max(P,N)\epsilon_{64},
\]

and

\[
\frac{\lVert Sz\rVert_2}{\max(\lVert S\rVert_F\lVert z\rVert_2,
\mathrm{minnormal})}
\le 512\max(P,N)\epsilon_{64}.
\]

The same `Sz` bound gates reconstruction change between `g` and `g+z`; the
same `Mz` bound gates residual change. A mode failing either is not accepted as
a numerical null mode and remains a failure row.

For each particle compute a conservative floating evaluation bound

\[
B_p=128\gamma(3s)\sum_i |z_i|\lVert\nabla N_i(x_p)\rVert.
\]

Let `B=max_p B_p`. A valid center-invisible mode is gradient-visible only when

\[
\max_p\lVert G_p(z)\rVert > \max(10^{-10}\;s^{-1},10^4 B).
\]

Record the maximum, RMS, bound, ratio, phase, and orientation. Intermediate
values are never rounded before the decision.

## 8. Decision order

1. Any analytic-witness failure:
   `stop_assembly_or_basis_inconsistency`.
2. Witnesses pass, selected full-rank high precision recovers `g` and particle
   values, while PCG misses:
   record `prior_affine_failure_is_solver_or_conditioning`.
3. A selected high-precision solve is full-rank by its numerical diagnostic,
   meets its backward gate, but misses affine forward/reconstruction gates:
   `stop_contradiction_or_implementation_defect`.
4. Any accepted center-invisible null mode is gradient-visible:
   `stop_center_state_gradient_nullspace_blocker`. This takes precedence over
   a solver-only classification because it is mechanics-visible.
5. All accepted null modes are center- and derivative-invisible:
   `stop_retain_quotient_or_gauge_for_future_lab`.
6. Rank/QR/high-precision ambiguity that prevents those decisions:
   `stop_inconclusive_rank_or_solver_diagnosis`.

Every outcome is **NO PROMOTION** and ends the lab. Multiple supported findings
are recorded even when one determines the bounded-decision string.

## 9. Evidence and replication gate

The full bundle must contain deterministic tables for systems, particles,
nodes, stencils including analytic gradients, sparse `M`, `q`, witnesses,
PCG error separation, high precision, null vectors, per-mode gradient metrics,
checkpoint/state-boundary controls, summary, and SHA-256 manifest.

All binary64 inputs are emitted as canonical hexadecimal floating literals;
higher-precision outputs use canonical decimal strings. The independent
validator rebuilds `M` and `q` from `S,W,V`, recomputes witness and null-mode
relations, validates the 76/4/10 selection, recomputes decisions, and rejects
missing/extra/duplicate or silently inapplicable rows.

Before sealing: two full executions must be byte-identical; C++ tests must pass
under local warnings-as-errors and CI Linux GCC, Linux Clang, and Windows/MSVC;
the Python exact/oracle and validator mutation tests must pass; pinned Lean
must build with `--wfail`; source must contain zero `sorry`, `admit`, `sorryAx`,
or project-defined axioms; and every exported theorem must have `#print axioms`
coverage. Preserve all failed attempts and publish the sealed evidence. Stop
without starting another transfer family or any constitutive mechanics.
