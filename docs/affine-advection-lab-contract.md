# Affine Advection Lab implementation contract

**Status:** experimental force-free diagnostic on `affine-advection-lab`.
Nothing here is an authoritative `World` transition or an approval of
continuum mechanics.

## State variables and units

| State | Representation | Unit / meaning |
|---|---|---|
| particle ID | unsigned 64-bit | canonical order only |
| particle mass | positive signed 64-bit quanta | exact; declared kg/quantum conversion |
| particle/grid position | binary64 vector | metre |
| particle/grid velocity | binary64 vector | metre/second |
| Eulerian affine `A` or APIC `C` | binary64 3x3 | inverse second |
| global affine intercept `b` | binary64 vector | metre/second |
| paper state `D_p` | binary64 3x3 | square metre |
| paper state `B_p=C_pD_p` | binary64 3x3 | square metre/second |
| physical timestep | exact time quanta plus binary64 SI conversion | second; never `Tick` |

`C`, `B`, `D`, and their reported auxiliary energies are numerical
representation state. They are not physical spin, internal energy, stress,
deformation, or a new authoritative MLS ledger channel.

## Force-free affine law

For `v(x)=A x+b`, the particle update is

\[
x'=(I+\Delta t A)x+\Delta t b.
\]

With explicitly checked invertibility, the implementation evaluates

\[
A'=A(I+\Delta t A)^{-1},\quad b'=(I+\Delta t A)^{-1}b.
\]

It rejects nonfinite state, nonpositive timestep, and a singular or
numerically unresolved map. The analytic control uses direct 3x3 binary64
inversion; Lean states the algebra with explicit inverse identities rather
than an invertibility axiom.

## Path update laws

Path A preserves each particle's velocity and applies `x += dt*v`, with the
analytic field advanced by the equations above. Path B repeatedly calls the
sealed static APIC transfer at unchanged positions and advances no clock.
Path C calls the sealed `transfer_cycle(..., APIC)` and then the same ballistic
position update used by the accepted lab. Path D performs Path C and replaces
each numerical affine matrix with the analytic convected gradient. D is a
causal control, not a proposed solver.

Path E independently implements Jiang, Schroeder, and Teran's moving-state
APIC equations. For old offset `r_ip=x_i^n-x_p^n`:

\[
m_i^n=\sum_p m_pw_{ip}^n,
\qquad
D_p^n=\sum_iw_{ip}^nr_{ip}r_{ip}^T,
\]

\[
m_i^nv_i^n=\sum_pw_{ip}^nm_p
\left[v_p^n+B_p^n(D_p^n)^{-1}r_{ip}\right].
\]

With no force, `v_tilde_i=v_i`. The conceptual new grid point is

\[
\widetilde x_i^{n+1}=x_i^n+\Delta t v_i^n.
\]

The fixed Cartesian grid does not physically move. Using the **old** weights:

\[
v_p^{n+1}=\sum_iw_{ip}^n\widetilde v_i^{n+1},
\qquad
x_p^{n+1}=\sum_iw_{ip}^n\widetilde x_i^{n+1},
\]

\[
B_p^{n+1}=\frac12\sum_iw_{ip}^n\left[
\widetilde v_i(r_{ip}+\widetilde r_{ip})^T+
(r_{ip}-\widetilde r_{ip})\widetilde v_i^T\right],
\]

where
`r_tilde_ip=x_tilde_i^(n+1)-x_p^(n+1)`. The code computes `D_p` from the
complete quadratic B-spline stencil and uses `B_p D_p^-1` in that order.
Zero-mass nodes are skipped and old weights are not recomputed at the new
particle location.

These are JST 2017 Eqs. (18), (24)–(26), (29)–(30), and (37)–(39). In the
force-free case the `lambda` parameter cancels because old and new grid
velocities agree. Equation (38)'s second transpose-coupled term is retained.

## Conservation and numerical residuals

Exact particle mass quanta cannot change and are summed with checked integer
arithmetic. Distributed grid mass, linear momentum, orbital angular momentum,
and energy are binary64 diagnostics under the kernel assumptions.

The force-free physical comparison uses particle-center kinetic energy only.
P2G grid-energy differences and center-plus-affine representation-energy
differences are emitted as signed numerical residuals. They are never
converted to heat, stored energy, chemistry, boundary energy, or another
ledger channel. No moving-advection invariant is claimed for the affine
auxiliary energy.

## Numerical approximation and failure modes

The lab uses deterministic binary64 arithmetic, canonical particle/node order,
an unbounded complete 27-node tensor-product quadratic B-spline stencil, and
direct computed moment matrices. It inherits the sealed local-coordinate
`2^14` grid-unit guard.

Failure modes include singular/ill-conditioned affine maps or moment matrices,
finite-precision drift, reduction-order dependence, grid phase/orientation
sensitivity, APIC mixing between particles, stale Eulerian affine state,
incorrect old/new weight usage, accidental transposition or omission in the
`B_p` update, and convergence failure under more remaps. Passing a unit test
does not establish physical validity.

## Tests

Unit tests cover velocity preservation, full-step versus two-half-step analytic
semigroup behavior, the exact stale-gradient witness, Path C/D separation,
singular-map rejection, the original isolated-particle APIC result, and an
independently implemented one-step Path E comparison.

The final axes, tolerances, causal decision, evidence completeness, and stop
rule are frozen in
[`affine-advection-preregistration.md`](affine-advection-preregistration.md).

## Primary method source

- Jiang, Schroeder, and Teran,
  [*An Angular Momentum Conserving Affine-Particle-In-Cell Method*](https://math.ucdavis.edu/~jteran/papers/JST17.pdf),
  Journal of Computational Physics 338 (2017),
  [DOI](https://doi.org/10.1016/j.jcp.2017.02.050).

