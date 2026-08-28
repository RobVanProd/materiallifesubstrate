# Moving APIC limit diagnostic contract

**Scope:** force-free diagnostic only. This contract adds no solver, force,
constitutive law, boundary physics, or promotion candidate. Paths named below
remain experimental controls.

## Fixed continuum problem

The initial material support is the half-open cube

\[
\Omega_0=[-1,1)^3\ \mathrm{m},
\qquad \rho_0=1\ \mathrm{kg\,m^{-3}}.
\]

`Omega_0` is an initial sampling domain, not a physical wall. The sparse grid
is unbounded, and particles are neither clipped, wrapped, reflected, nor
deleted after leaving the initial cube.

Every resolution samples the same global affine velocity field

\[
v(x)=Ax+b.
\]

The field is the prior general-affine case under the fixed proper signed-axis
orientation `p210_sppm`:

\[
A=\begin{bmatrix}
3/20&2/5&7/20\\
1/4&-1/10&-11/20\\
-3/10&7/10&1/5
\end{bmatrix}\ \mathrm{s^{-1}},
\qquad
b=\begin{bmatrix}111/125\\-129/200\\-74/125\end{bmatrix}
\ \mathrm{m\,s^{-1}}.
\]

At particle center `x_p`, initialize

\[
v_p=Ax_p+b,\qquad B_p=A D_p,
\]

where `D_p` is recomputed from that particle's complete 27-node
tensor-product quadratic B-spline stencil. Consequently
`B_p D_p^-1=A`; no constant cached `D_p` is assumed by the experiment.

The no-force material reference is

\[
x_p(t)=x_p(0)+t v_p(0),\qquad v_p(t)=v_p(0).
\]

For Eulerian affine comparisons, the analytic field is

\[
A(t)=A(I+tA)^{-1},\qquad b(t)=(I+tA)^{-1}b.
\]

All inverses used by the executed levels must pass the implementation's
finite and conditioning guards. A rejected inverse is a preserved failed row,
not an omitted configuration.

## Exact physical-time and mass scales

The **new fixed-domain and particles/cell scopes** use a time quantum of
exactly `1/160 s`. Their fixed physical horizon is exactly `16` quanta or
`1/10 s`. `Tick` is not reinterpreted as time. The unchanged fixed-particle
control retains its already sealed `1/80 s` quantum and eight-quanta horizon;
evidence must not compare the two integer clock fields without their declared
unit metadata.

The declared characteristic speed is

\[
U_\mathrm{ref}=5/2\ \mathrm{m\,s^{-1}},
\]

which exceeds the maximum initial speed on the closed cube. Every main level
holds

\[
U_\mathrm{ref}\Delta t/h=1/8
\]

exactly.

The mass quantum is fixed across both new scopes at exactly

\[
q_m=1/4096\ \mathrm{kg}.
\]

The cube contains exactly `8 kg = 32768 q_m`. Particles are placed at the
centers of a lexicographically indexed Cartesian sampling lattice:

\[
x_j=-1+(j+1/2)\Delta x_p.
\]

Particle mass is `rho_0 * dx_p^3`; it must map to the exact integer counts in
the preregistration. IDs are assigned in a documented lexicographic order and
must be unique and identical between paths at a given configuration.

## Paths

### E -- published moving-state APIC path

Path E is the already implemented Jiang--Schroeder--Teran 2017 no-force path.
It retains the published `B_p` returned by its G2P state update and feeds it to
the next step. Its equation mapping remains the one frozen in the Affine
Advection Lab contract. This lab does not make E promotion-eligible.

### E_oracleB -- analytic affine-state intervention

Each `E_oracleB` step calls the existing
`jst2017_moving_apic_no_force_step` exactly once. Old weights, canonical
reductions, P2G, force-free grid evolution, G2P position and velocity, and the
paper-computed pre-override `B_p` are therefore the E transition on that
step's input.

Only after G2P returns does the control:

1. advance the analytic global field to `t_next`;
2. recompute each `D_p(next)` from the complete quadratic stencil at the new
   particle position; and
3. replace only `B_p` with `A_exact(t_next) D_p(next)`.

That replacement feeds the next step. Position, velocity, mass, IDs, grid
state, and physical energy are not corrected. E_oracleB is a causal
intervention, not an independent APIC implementation, and is permanently
promotion-ineligible.

The evidence retains both the pre-override paper residuals and the
post-override representation totals. It also records

\[
\max_p\frac{\lVert B_p-A_\mathrm{exact}D_p\rVert_F}
{\max(1,\lVert B_p\rVert_F,\lVert A_\mathrm{exact}D_p\rVert_F)}.
\]

The override magnitude itself is a report-only intervention measurement, not
an error that E is required to minimize.

## Error definitions

All floating metrics are finite binary64 values reduced in stable particle-ID
or grid-index order. Missing, `NaN`, or infinite values fail their row.

For particle vector state `q`, use the mass-weighted normalized RMS error

\[
E_q=\frac{\sqrt{\sum_p m_p\lVert q_p-q_p^*\rVert^2/\sum_p m_p}}
{\max(1,\sqrt{\sum_p m_p\lVert q_p^*\rVert^2/\sum_p m_p})}.
\]

All numeric values in these normalizations are expressed in the declared SI
unit for the metric. For scalar, vector, or matrix totals use the symmetric
relative form

\[
R(a,r)=\frac{\lVert a-r\rVert}
{\max(1,\lVert a\rVert,\lVert r\rVert)},
\]

with absolute value, Euclidean norm, or Frobenius norm respectively. The
one-step causal controls use this symmetric matrix form.

For terminal affine state define each particle's effective matrix and local
intercept by

\[
C_p=B_pD_p^{-1},\qquad d_p=v_p-C_px_p.
\]

Their global estimates are the mass-weighted means `C_bar` and `d_bar`.
Affine-gradient and intercept errors are `R(C_bar,A_exact)` and
`R(d_bar,b_exact)`. Cross-particle dispersion is the maximum of two separately
normalized RMS values:

\[
\max\left(
\frac{\sqrt{\sum m_p\lVert C_p-\bar C\rVert_F^2/M}}
     {\max(1,\lVert A_{exact}\rVert_F)},
\frac{\sqrt{\sum m_p\lVert d_p-\bar d\rVert^2/M}}
     {\max(1,\lVert b_{exact}\rVert)}
\right).
\]

This avoids mixing unnormalized inverse-seconds and metres-per-second in one
dispersion scalar. The sealed old control retains its historical columns and
is never pooled into these new values.

The required eleven convergence metrics are:

1. immediate static particle-velocity reconstruction;
2. immediate effective affine reconstruction, using `B_p D_p^-1`;
3. occupied-grid affine reconstruction;
4. affine-gradient error against `A(t)`;
5. recovered-intercept error against `b(t)`;
6. cross-particle affine/intercept dispersion;
7. trajectory-position error;
8. material-velocity error;
9. linear-momentum error;
10. center orbital-angular-momentum error; and
11. center physical particle-kinetic-energy error.

The first three come from a separate `dt=0` probe at the initial state:
particle velocity is compared by the particle RMS above; effective `C_p` is
compared by the analogous mass-weighted Frobenius RMS; and occupied-grid
velocity is a grid-mass-weighted RMS against `A x_i+b` at each old grid node.
They are not inferred from a physical-time step. Metrics 7 and 8 compare
matching canonical IDs to the ballistic material reference. Metrics 9--11
use the symmetric relative form between initial and terminal totals.

For the phase pair at each main level, compare matching particle IDs after the
same horizon and record normalized RMS differences in terminal position,
velocity, and effective affine gradient. These three phase-sensitivity
metrics form separate three-level convergence groups. Phase zero is the
reference argument to the particle RMS denominator; canonical IDs, rather
than container order, define the matching.

### Exact and hard row gates

The hard/exact failure table contains every named gate below, including zero
failure counts:

| Gate field | Applicability | Required result |
|---|---|---|
| `exact_mass_ok` | every row | New scopes: input and terminal mass exactly `32768` quanta under `q_m=1/4096 kg`; old control: exact equality under its sealed `1/8 kg` quantum. |
| `exact_clock_ok` | every row | New scopes: exactly `16` quanta under `q_t=1/160 s`; old control: exactly its sealed eight quanta under `1/80 s`. |
| `max_p2g_mass_error` | every transfer row | `<= 2e-13` |
| `max_p2g_linear_error` | every transfer row | `<= 2e-12` |
| `max_g2p_linear_error` | every transfer row | `<= 2e-12`; this is the paper G2P particle-linear total. |
| `max_p2g_paper_augmented_angular_error` | every transfer row | `<= 2e-11` |
| `max_g2p_paper_augmented_angular_error` | every transfer row | `<= 2e-11` |
| `static_grid_error` | every transfer row | `<= 5e-11` for this nontranslation field. |
| `oracle_B_constraint_error` | E_oracleB rows only | Post-override `B=A_exact D` error `<= 5e-11`. |
| `nonfinite_or_missing_count` | every row | exactly zero across required input, state, residual, and diagnostic fields. |
| `configuration_error_count` | every row | exactly zero; cells, particles, particles/cell, level, phase, `h`, `dt`, `dx_p`, units, mass quanta, and path must equal the preregistered tuple. |
| `id_error_count` | every row | exactly zero duplicate, missing, reordered-without-canonicalization, or mismatched particle IDs. |
| `first_step_D_stationarity_error` | co-refinement causal controls | `D_next=D_old` error `<= 5e-11`. |
| `first_step_B_identity_error` | co-refinement causal controls | paper pre-override `B_next=A_initial D_old` error `<= 5e-11`. |
| `first_step_C_retention_error` | co-refinement causal controls | paper pre-override `B_next D_next^-1=A_initial` error `<= 5e-11`. |
| `first_step_discrepancy_witness_error` | co-refinement causal controls | observed `C_next-A_exact(next)` agrees with `dt A_initial^2(I+dt A_initial)^-1` to `<= 5e-11`. |
| `oracle_first_step_C_exact_error` | E_oracleB co-refinement controls only | post-override `B D_next^-1=A_exact(next)` error `<= 5e-11`. |

These 17 names are the complete hard-gate vocabulary. The evidence emits all
17 rows for every preregistered scope/path/phase family, marking inapplicable
ones explicitly rather than omitting them.

Immediate static particle-velocity and effective-affine reconstruction are
also required metrics with the `5e-11` hard branch in the convergence table;
they are listed there rather than silently folded into `static_grid_error`.
The old control's unit-tagged integers are never compared directly with the
new-scope integers.

All eleven time/trajectory/affine convergence metrics use a `2e-9` hard
tolerance, except the three static metrics, which retain `5e-11`. The three
phase-pair metrics use `2e-9`.

### Energy separation

Center particle kinetic energy is the only energy quantity in the physical
trajectory comparison. P2G center-energy residual, affine auxiliary energy,
center-plus-affine representation energy, the pre/post-override difference,
and E_oracleB override work are numerical diagnostics only. They never close
a physical ledger and cannot be relabeled as heat, stored, chemical, or
structural energy.

## Failure modes retained by the evidence

The bundle must preserve singular or ill-conditioned `D_p`/affine maps,
integer overflow, exact-mass mismatch, duplicate IDs, missing stencil nodes,
non-finite values, phase dependence, boundary-of-sampled-domain effects,
reduction-order drift, non-monotone refinement, a failed old-control replay,
and disagreement between E and the intervention control. Passing a unit test
does not establish physical validity.
