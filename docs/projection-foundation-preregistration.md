# Projection Foundation Lab preregistration

**Frozen before final sweep:** 2026-08-28 on branch
`projection-foundation-lab`.  
**Seed:** `260828`. Lattices are deterministic; the seed is retained for
provenance and adversarial permutations.

The equations, state boundary, solve policy, metric definitions, and failure
semantics are frozen in
[`projection-foundation-lab-contract.md`](projection-foundation-lab-contract.md).
The primary-source boundary is frozen in
[`projection-foundation-source-audit.md`](projection-foundation-source-audit.md).

## 1. Fixed physical problem

The initial sampling support is the half-open cube

\[
\Omega_0=[-1/2,1/2)^3\ \mathrm m,
\qquad \rho_0=1\ \mathrm{kg\,m^{-3}}.
\]

It contains exactly `1 kg`. It is not a wall; the transient grid is unbounded,
and particles are not clipped, wrapped, reflected, or deleted.

The mass quantum is exactly `1/4096 kg`; total mass is exactly `4096` quanta.
The time quantum is exactly `1/160 s`. Main trajectories end at exactly four
quanta or `1/40 s`. The characteristic speed is declared as `U_ref=5/2 m/s`.

Particles are at Cartesian cell centers

\[
x_j=-1/2+(j+1/2)\Delta x_p
\]

with lexicographic IDs. Mass per particle is `rho_0 dx_p^3` and must map to
the registered integer quanta exactly.

## 2. Velocity fields

All physical initial states are shared between methods.

### Translation

\[
v(x)=(9/20,-3/10,1/5)\ \mathrm{m\,s^{-1}}.
\]

### Rigid rotation plus translation

With `omega=(3/10,-1/5,2/5) s^-1`,

\[
v(x)=\omega\times x+(3/20,-1/10,1/20)\ \mathrm{m\,s^{-1}}.
\]

### General affine

\[
A=\begin{bmatrix}
3/20&2/5&7/20\\
1/4&-1/10&-11/20\\
-3/10&7/10&1/5
\end{bmatrix}\ \mathrm{s^{-1}},
\quad
b=(111/125,-129/200,-74/125)\ \mathrm{m\,s^{-1}},
\]

\[
v(x)=Ax+b.
\]

### Smooth non-affine

\[
v(x)=\begin{bmatrix}
1/5+(7/20)\sin(\pi y)\cos(\pi z)\\
-3/20+(3/10)\sin(\pi z)\cos(\pi x)\\
1/10+(1/4)\sin(\pi x)\cos(\pi y)
\end{bmatrix}\ \mathrm{m\,s^{-1}}.
\]

The non-affine path is compared with the ballistic material reference only;
it has no exact grid-reproduction gate.

## 3. Phases and orientations

Grid phase fractions are `p000=(0,0,0)` and
`p049_001_083=(0.49,0.01,0.83)` multiplied by `h`.

Proper signed-axis orientations are

\[
Q_0=I\quad\text{(`p012_sppp`)},
\]

and

\[
Q_1=\begin{bmatrix}0&0&1\\0&1&0\\-1&0&0\end{bmatrix}
\quad\text{(`p210_sppm`)}.
\]

For an oriented run, positions, velocities, affine matrices, and grid origin
are transformed by `Q`; results are transformed back by `Q^T` before
comparison. The cube and sampling density remain the same physical problem.

## 4. Candidate set

Exactly six labels are emitted:

1. `lumped_PIC`;
2. `full_consistent`;
3. `FMPM_1`;
4. `FMPM_2`;
5. `FMPM_3`; and
6. `FMPM_4`.

`FMPM_1` is an identity control and must match `lumped_PIC`; it is not counted
as an independent algorithmic discovery.

## 5. Main fixed-domain co-refinement

`h`, `dt`, and particle spacing halve together. Density, domain, total mass,
particles/cell, horizon, and `U_ref dt/h=1/8` remain fixed.

| Level | `h` m | `dt` s | dt quanta | steps | cells/axis | particles/axis | particles | ppc | `dx_p` m | mass quanta/particle |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | `1/2` | `1/40` | 4 | 1 | 2 | 4 | 64 | 8 | `1/4` | 64 |
| 1 | `1/4` | `1/80` | 2 | 2 | 4 | 8 | 512 | 8 | `1/8` | 8 |
| 2 | `1/8` | `1/160` | 1 | 4 | 8 | 16 | 4096 | 8 | `1/16` | 1 |

The complete main matrix is:

- four fields;
- six candidate labels;
- two phases;
- two orientations; and
- three refinement levels.

It contains exactly `4*6*2*2*3 = 288` raw rows. Failed solves remain rows.

## 6. Particles-per-cell sweep

This separate sweep fixes `h=1/4 m`, `dt=1/80 s`, two steps, the hard phase,
orientation `p210_sppm`, and the same cube/density/mass. It uses the general
affine and smooth non-affine fields.

| Level | ppc | particles/axis/cell | `dx_p` m | particles | mass quanta/particle |
|---:|---:|---:|---:|---:|---:|
| 0 | 1 | 1 | `1/4` | 64 | 64 |
| 1 | 8 | 2 | `1/8` | 512 | 8 |
| 2 | 64 | 4 | `1/16` | 4096 | 1 |

This contains `2*6*3 = 36` raw rows. The ppc=1 full matrix is expected to be
structurally rank deficient when active nodes exceed particles; that expected
failure must be demonstrated and preserved rather than bypassed.

## 7. Exact finite-order angular control

An independent rational oracle uses one bilinear unit cell, four unit masses
at `(0.9,0.2)`, `(0.1,0.9)`, `(0.7,0.9)`, `(0.2,0.2)`, and rigid velocity
`(-y,x)`. Its full mass matrix has exact 1-norm condition `2514/343`.

Full consistent projection must recover the field and angular momentum within
the dense-solve gate. FMPM(1–4) must preserve linear momentum exactly in the
rational oracle and reproduce these angular deltas:

| k | exact angular delta |
|---:|---:|
| 1 | `-921401/1895040` |
| 2 | `-91802668277/359117660160` |
| 3 | `-9282539024459489/68054233070960640` |
| 4 | `-953607378962630674973/12896549383879325122560` |

This is an expected recurrence fingerprint, not an MLS pass and not an
implementation bug.

## 8. Hard per-row gates

Every raw row emits all gates with explicit applicability.

| Gate | Tolerance/requirement |
|---|---:|
| exact mass | exactly 4096 quanta before/after |
| exact clock | exactly registered quanta |
| missing/unexpected/duplicate IDs or particle-count drift | zero |
| nonfinite values | zero |
| partition of unity | `<=5e-14` |
| linear reproduction | `<=5e-13` m |
| matrix symmetry | `<=5e-15` relative |
| row-sum identity | `<=5e-13` relative |
| grid mass error | `<=2e-13` relative |
| linear momentum | `<=2e-11` relative |
| full normalized solve residual | `<=5e-12` |
| full raw condition estimate | `<=1e10` |
| full preconditioned condition estimate | `<=1e8` |
| full affine particle reconstruction | `<=5e-10` |
| full affine grid representation | `<=5e-10` |
| full affine orbital angular error | `<=5e-10` |
| FMPM residual identity | `<=5e-11` |
| FMPM(1)/PIC identity | `<=5e-13` |
| checkpoint byte round trip/replay | exact |

Rank-deficient/ill-conditioned rows must fail their full-solve gates; they are
not configuration omissions. Kinetic-energy change is never a generic hard
gate. For represented affine full-projection rows, it is recorded with an
expected near-zero diagnostic threshold of `5e-9` but cannot repair another
failure.

## 9. Three-level convergence rule

For nonnegative errors `(e0,e1,e2)`, a family passes only if either:

1. all levels are below that metric's hard floor; or
2. `e1<=0.80 e0`, `e2<=0.80 e1`, `e2<=0.40 e0`, and the finest value is below
   the metric's registered ceiling.

The roundoff guard is `5e-14`: below it, a tiny nonmonotone change does not
itself fail the all-below branch. Missing, nonfinite, negative, failed-solve,
or inapplicable required values fail.

| Metric family | hard floor | finest ceiling |
|---|---:|---:|
| affine material velocity/trajectory, full | `5e-10` | `5e-8` |
| smooth non-affine material velocity | `2e-8` | `2e-2` |
| smooth non-affine trajectory | `2e-8` | `2e-3` |
| linear momentum | `2e-11` | `2e-9` |
| orbital angular momentum | `5e-10` | `5e-5` |
| phase/orientation particle sensitivity | `5e-10` | `5e-3` |
| candidate/full grid or particle distance | `5e-10` | `2e-2` |

No post-result tolerance change is allowed.

## 10. FMPM order-to-full rule

At every configuration where full mass solves, report `D`-norm grid distance
and `W`-norm reconstructed-particle distance for k=1–4. An order family
approaches full only if either all four values are at most `5e-10`, or

- every successor is no larger than its predecessor plus `5e-13`; and
- the k=4 distance is at most `0.50` of the k=1 distance.

This order rule is necessary but not sufficient for retention. FMPM(4) must
also pass its co-refinement momentum, angular, material-velocity, trajectory,
phase, orientation, and non-affine gates. Literature performance cannot
override those gates.

## 11. Evidence completeness

| Table | Required full rows |
|---|---:|
| main co-refinement raw | 288 |
| particles/cell raw | 36 |
| exact angular-control methods | 6 |
| all primary rows | 330 |
| convergence decisions | 896 |
| order-to-full decisions | 108 |
| phase-sensitivity rows | 480 |
| orientation-sensitivity rows | 480 |
| hard-gate rows | 6,480 |
| solver/checkpoint rows | 324 each |

Derived convergence, order, phase, orientation, hard-gate, solver-failure, and
per-metric tables must enumerate every expected family from these raw rows.
The derived counts above are the complete Cartesian family counts; the earlier
provisional arithmetic value `768` was rejected because it omitted 128
registered phase/orientation-derived families. No rows were removed to fit the
provisional value. The sensitivity tables include 192 additional FMPM-to-full
distance rows each (64 three-level families per phase/orientation table).
Every count is independently reconstructed by the Python
validator. Smoke output is
provisional and cannot satisfy full counts.

The final bundle includes raw CSV files, complete per-metric decisions,
solver/rank failure rows, exact-oracle result, checkpoint/replay hashes,
compiler/tool versions, seed/config manifest, source/branch/dirty state,
command log, stdout/stderr, file hashes, and a bundle manifest whose own hash
is excluded from its pre-hash payload.

## 12. Decision logic

1. If well-conditioned, accurately solved full mass fails affine or proper
   co-refinement requirements, stop and reconsider the particle/grid
   architecture.
2. If full mass passes but FMPM(1–4) fails the order-to-full rule, retain full
   mass as a reference only and reject the tested approximation.
3. If full mass passes and FMPM approaches it, retain FMPM as a research
   candidate only if FMPM(4) also passes every MLS momentum/angular/time gate.
4. If failures correlate with structural rank, condition diagnostics, or ppc,
   classify and isolate those before considering another transfer family.
5. In every outcome, stop. Do not begin constitutive mechanics.
