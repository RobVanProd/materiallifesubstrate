# Particle/grid transfer laboratory contract

**Status:** experimental reference code on `time-transfer-lab`. No candidate is
part of the authoritative `World` transition ABI, and no result in this lab is
a continuum-mechanics validation.

The implementation is `mls::experimental` in
`include/mls/transfer_lab.hpp` and `src/transfer_lab.cpp`. It compares transfer
operators only. There is no stress, constitutive response, grid force, contact,
gravity, fracture, diffusion, reaction kinetics, or material-point time
integrator.

## State variables and units

| State | Representation | Unit / role |
|---|---|---|
| particle ID | unsigned 64-bit integer | canonical reduction order only |
| particle mass | positive signed 64-bit quanta | exact; converted by declared kg/quantum |
| particle position | binary64 vector | metres |
| particle velocity | binary64 vector | metres/second |
| APIC affine matrix `C` | binary64 3x3 matrix | inverse seconds; maps offset to velocity |
| grid spacing and origin | binary64 | metres |
| grid mass | binary64 | kilograms |
| grid momentum | binary64 vector | kilogram-metres/second |
| grid velocity | binary64 vector | metres/second |

Particle mass quanta remain unchanged by every transfer round trip and are
summed with checked signed-integer arithmetic. Grid mass and all velocity-based
quantities are numerical approximations. They are never entered into the exact
MLS matter or energy ledgers.

The affine matrix is a numerical representation of a local velocity field. In
this lab it is not packet spin, a couple, deformation, stored energy, or any
other physical state. Promoting it to authoritative state would require a new
ontology and accounting review.

## Kernel and physical support

For grid node `i`, particle `p`, spacing `h`, and offset

\[
r_{ip}=x_i-x_p,
\]

the lab uses a tensor-product quadratic B-spline weight

\[
w_{ip}=\prod_{d=1}^{3}\phi((x_{p,d}-x_{i,d})/h),
\]

with

\[
\phi(q)=
\begin{cases}
3/4-q^2,& |q|<1/2,\\
\tfrac12(3/2-|q|)^2,&1/2\le |q|<3/2,\\
0,&\text{otherwise}.
\end{cases}
\]

Every particle uses its complete 27-node stencil on an unbounded grid. This
gives, up to binary64 evaluation error,

\[
\sum_i w_{ip}=1,
\qquad
\sum_i w_{ip}r_{ip}=0,
\qquad
D_p=\sum_i w_{ip}r_{ip}r_{ip}^{T}=\frac{h^2}{4}I.
\]

The code computes `D_p` from the actual samples and inverts it; it does not
silently substitute the analytic value. A clipped stencil would invalidate the
contract. Grid indexing finds candidate support, while the kernel weight
defines participation. Voxel adjacency is not an independent authorization for
an interaction.

Binary64 cannot preserve an arbitrary subcell phase when very large global
coordinates are divided by a small `h`. The reference lab therefore requires
the absolute particle coordinate, grid origin, and their displacement—each
divided by `h`—to remain strictly below `2^14` grid units per axis. Near that
bound the binary64 spacing is below `2^-38` grid units. A larger sparse world
must transfer in rebased brick-local coordinates; it may not silently rely on a
large global binary64 coordinate and claim phase invariance.

## Transfer candidates and update laws

All reductions sort particles by stable ID and grid nodes by integer coordinate.
Zero-mass nodes are never divided.

### PIC

Particle to grid:

\[
m_i=\sum_p w_{ip}m_p,
\qquad
q_i=\sum_p w_{ip}m_pv_p,
\qquad
u_i=q_i/m_i.
\]

Grid to particle:

\[
v'_p=\sum_i w_{ip}u_i.
\]

PIC is expected to reproduce constant velocity. Its averaging removes
particle modes and generally dissipates kinetic energy over repeated remaps.
That loss is a numerical residual, not heat.

### APIC

Particle to grid:

\[
q_i=\sum_p w_{ip}m_p\left(v_p+C_pr_{ip}\right).
\]

Grid to particle:

\[
v'_p=\sum_iw_{ip}u_i,
\qquad
B'_p=\sum_iw_{ip}u_ir_{ip}^{T},
\qquad
C'_p=B'_pD_p^{-1}.
\]

For a complete nonsingular stencil, APIC should reproduce a globally affine
velocity field in a frozen-position transfer cycle. This is the transfer-only,
zero-grid-update specialization. The full moving-step angular result in the
published APIC formulation also depends on its time-aware update; this lab does
not silently claim that result.

### FLIP diagnostic

The lab uses PIC for particle-to-grid initialization, retains the pre-update
grid velocity `u_i`, and evaluates

\[
v'_p=v_p+\sum_iw_{ip}(u_i^{new}-u_i^{old}).
\]

There is no modeled grid update here, so `u_new = u_old` and this path is an
identity diagnostic. A test-only explicit uniform delta checks the implemented
formula. Identity in this setup says nothing about FLIP accuracy or stability,
so FLIP is preregistered as ineligible for promotion.

## Conservation claims and angular boundary

Partition of unity gives P2G mass and linear-momentum conservation for PIC. The
first-moment identity gives PIC P2G point-orbital angular-momentum conservation.
APIC's affine term has zero net linear momentum under the same first-moment
identity.

Published APIC angular conservation is for the augmented particle quantity

\[
L_{aug}=\sum_p\left[
x_p\times(m_pv_p)+
m_p\sum_iw_{ip}\,r_{ip}\times(C_pr_{ip})
\right].
\]

The second term is reported as `affine_auxiliary` and the first is reported as
`center_orbital`. Grid orbital angular momentum can equal their sum while not
equaling the center-only orbital quantity. MLS-0's authoritative point-packet
ledger contains only the center term. The lab therefore reports all three
values and does not use the APIC theorem to assert conservation of the existing
physical ledger. The bakeoff evaluates APIC's center-plus-affine total as the
candidate's declared numerical angular state. A numerical APIC win would still
require a separate head-agent decision before that affine state could enter the
authoritative packet ontology.

Likewise, the lab separately reports center kinetic energy and the represented
affine auxiliary

\[
K_{aff}=\frac12\sum_p m_p\operatorname{tr}(C_pD_pC_p^T).
\]

`K_aff` is a transfer diagnostic, not physical packet energy. Signed P2G and
round-trip energy differences are emitted only as `numerical_energy_residual`.

## Numerical approximation

- IEEE-754 binary64 arithmetic;
- finite support and lumped grid mass;
- deterministic but not associative floating-point sums;
- computed 3x3 moment-matrix inversion;
- exact signed-integer particle mass, but approximate distributed grid mass;
- unbounded logical grid with no boundary treatment; and
- frozen-position remaps, except the separately identified ballistic/regrid
  timestep experiment.

The reference implementation does not prove identical floating-point bits
across compiler families. CI records each compiler result, while canonical
ordering removes deliberate schedule nondeterminism.

## Failure modes

The implementation rejects nonpositive/nonfinite spacing or mass scale,
nonpositive particle mass, duplicate particle IDs, nonfinite state, unsafe grid
indices, nonfinite node coordinates, exact-mass overflow, missing stencil nodes,
zero/nonfinite grid mass, a singular moment matrix, and global/normalized
coordinates whose binary64 spacing is too coarse to retain the lab's required
subcell phase.

Known scientific failure modes include PIC damping, FLIP null modes/noise, APIC
transfer of center orbital content into an unphysical auxiliary under the
current packet ontology, boundary-stencil clipping, grid-phase anisotropy,
finite-precision drift, and failure of a frozen transfer rule when repeatedly
regridded through physical time. A unit-test pass does not make any of these
physically valid.

## Tests and preregistered evidence

Unit tests cover kernel moments across grid phases, invalid/overflow state,
constant translation, frozen affine APIC reconstruction, the APIC angular
accounting distinction, PIC damping, FLIP identity/delta behavior, and canonical
particle reduction order.

The sealed sweep and promotion rule are in
[`time-transfer-preregistration.md`](time-transfer-preregistration.md). Final
evidence must include every PIC, APIC, and FLIP diagnostic row, refinement and
timestep convergence tables, losing candidates, and failures. The C++ harness
can issue only a provisional numerical ordering. A separate verifier must
reread the files, check SHA-256 digests and exact Cartesian-product counts,
compare an independent deterministic rerun, and combine checkpoint, local
build, Python, Lean, clean-source, and CI gates before the bundle can state an
overall recommendation.

## Primary-method references

- Jiang, Schroeder, and Teran, [*An Angular Momentum Conserving Affine-Particle-In-Cell Method*](https://www.math.ucdavis.edu/~jteran/papers/JST17.pdf), Journal of Computational Physics, 2017.
- Jiang et al., [*The Affine Particle-In-Cell Method*](https://doi.org/10.1145/2766996), ACM Transactions on Graphics, 2015.
- Brackbill, Kothe, and Ruppel, [*FLIP: A low-dissipation, particle-in-cell method for fluid flow*](https://doi.org/10.1016/0010-4655(88)90020-3), Computer Physics Communications, 1988.
- Hu et al., [*A Moving Least Squares Material Point Method with Displacement Discontinuity and Two-Way Rigid Body Coupling*](https://yuanming.taichi.graphics/publication/2018-mlsmpm/mls-mpm-cpic.pdf), ACM Transactions on Graphics, 2018.

The last title is written in full because “MLS” already means Material Life
Substrate in this repository. No component here is named `MLS-MPM`, and this
transfer-only experiment is not an implementation of that full method.
