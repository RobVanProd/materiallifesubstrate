# Mechanical Observability Lab contract

**Status:** bounded representation experiment. It selects no material law,
force law, mechanics solver, transfer family, or production representation.

**Accepted parent:** Projection Exactness + Nullspace Lab at
`2e175396ff30faea8a4d96d5a0336ab9ba042f12`. Its sealed evidence and RED
verdict for the tested center-only quadratic-B-spline representation remain
immutable.

## 1. Question and forbidden repairs

This lab asks only which low-level state can distinguish non-rigid
deformation without a hidden numerical gauge. It must not introduce stiffness,
stress, pressure, viscosity, force integration, contact, fracture kinetics,
gravity, chemistry kinetics, organisms, rendering, or GPU work.

A preferred pseudoinverse, minimum-norm grid representative, diagonal shift,
regularization, numerical gauge, hourglass penalty, or unaccounted auxiliary
mode cannot make a representation observable. Such a path is rejected rather
than measured as a candidate.

The sparse grid may enumerate candidate neighbors and retain the frozen
quadratic-grid negative control. It cannot authorize an interaction or supply
candidate B, C, or D with a velocity gradient, strain, deformation, stress, or
persistent mechanics state.

## 2. Shared physical input and state boundary

Every packet has a stable ID, exact mass quanta, position in metres, and test
velocity in metres per second. Candidate B additionally has a dimensioned
support radius. Candidate C has an explicit canonical simple graph of generic
two-packet distance relations. Conditional candidate D has explicit canonical
ordered four-packet volume relations. Graph and volume topology are physical
input; they are not inferred from voxel adjacency or object labels.

Relations cannot be named solid, spring, rope, sheet, beam, or another
macroscopic function. Self-relations, duplicate/reversed edges, repeated sites
inside a volume relation, zero-length edges, and noncanonical topology are
rejected. Connectivity and intentional deletion remain visible evidence.

Neighbors, moment matrices, corrected gradients, operator matrices, grid
nodes, factorizations, pivots, and null vectors are transient diagnostics. The
lookup grid is rebuildable and excluded from authoritative state.

## 3. Candidate A: frozen quadratic-grid control

On a packet configuration, let `S_A` sample a transient quadratic-B-spline
nodal velocity field at packet centers. Let `D_A` sample the symmetric part of
its analytic grid gradient at those centers. Both operate on the same nodal
degrees of freedom:

\[
(S_Au)_p=\sum_iN_i(x_p)u_i,
\qquad
(D_Au)_p=\operatorname{sym}\sum_i u_i\otimes\nabla N_i(x_p).
\]

`R_A=D_A` is audited over nodal degrees of freedom, but a packet-center
operator exists only if it is constant on the equivalence classes induced by
`S_A`:

\[
\ker S_A\subseteq\ker D_A.
\]

The sealed negative control is unchanged. No inverse or preferred lift from
centers to nodes is constructed. A valid `S_A` null mode with a resolved
`D_A` image is a quotient/gauge failure.

## 4. Candidate B: corrected local packet gradient

For a packet `p`, deterministic Euclidean neighbors `q` satisfy
`0 < ||r_pq||^2 < H_p^2`, where `r_pq=x_q-x_p`. Candidate lookup must agree
exactly with a brute-force sorted-ID reference. Define the MLS-specific compact
rational influence

\[
w_{pq}=\left(1-\frac{\lVert r_{pq}\rVert^2}{H_p^2}\right)^2,
\]

\[
M_p=\sum_qw_{pq}r_{pq}r_{pq}^{T},\qquad
B_p(v)=\sum_qw_{pq}(v_q-v_p)r_{pq}^{T},
\]

\[
G_p(v)=B_p(v)M_p^{-1}.
\]

`M_p` has units `m^2`, `B_p` has units `m^2/s`, and `G_p` has units `1/s`.
The mechanical observability row block is
`R_B(v)_p=vec(sym(G_p(v)))`. The full `G_p` is retained separately for affine
reproduction. A singular moment or a numerical condition estimate above the
preregistered bound fails explicitly; there is no pseudoinverse or shift.

For `v(x)=Ax+b`, exact arithmetic gives `B_p=A M_p` and hence `G_p=A` whenever
`M_p` is nonsingular. This necessary affine property is not sufficient for
mechanical observability; the complete kernel of `R_B` is still required.

## 5. Candidate C: objective central-distance relations

For an explicit edge `e=(i,j)`, define `r_e=x_j-x_i`, length `l_e>0`, and
unit direction `n_e=r_e/l_e`. The finite observable is actual length. Its
linearized rate is

\[
(R_Cv)_e=n_e\mathbin{\cdot}(v_j-v_i).
\]

The exported exact-rank row may be multiplied by `l_e`:

\[
l_e(R_Cv)_e=r_e\mathbin{\cdot}(v_j-v_i),
\]

which is half the derivative of squared length and has the same kernel. This
is the actual bar-and-joint rigidity matrix. It is an observable relation, not
a spring, force, energy, damage, or peridynamic constitutive law.

Finite proper rigid transforms must preserve actual edge lengths. Candidate C
does not imply that classical central pair forces can reproduce arbitrary
isotropic materials; their Cauchy/Poisson restrictions remain explicit prior-
art limitations outside this lab.

## 6. Conditional candidate D: oriented-volume relations

Candidate D is enabled only because preregistered ordinary three-dimensional
candidate-C controls contain non-rigid modes during the diagnostic pilot. The
only permitted enrichment type is frozen before the final sweep.

For an explicit ordered tuple `(i,j,k,l)`, let

\[
a=x_j-x_i,\quad b=x_k-x_i,\quad c=x_l-x_i,
\quad \tau=\det(a,b,c).
\]

Its objective linearized rate is

\[
\dot\tau=(b\times c)\cdot(v_j-v_i)
 +(c\times a)\cdot(v_k-v_i)
 +(a\times b)\cdot(v_l-v_i).
\]

`R_D` is the vertical concatenation of the C rigidity rows and these explicit
volume rows. A tuple's ordering and sign convention are physical provenance.
No angle, higher polynomial mode, penalty, or later enrichment may be added
after inspecting final data. Proper translations and rotations preserve both
length and oriented volume; reflections are not objectivity controls.

## 7. Central kernel gate

For packet-domain operators, construct six rigid generators about the packet
centroid: three translations and three fields
`v_i=omega cross (x_i-c)`. Let `T(x)` be their matrix and let
`Rigid(x)=range(T(x))`. The six parameters need not have a six-dimensional
sampled image on degenerate geometry: a collinear filament has generator rank
five because axial rotation vanishes. This is reported, never overwritten.

For every candidate, verify `R T` is zero to the registered floating bound.
Compute a complete numerical null basis without regularization. A full-span,
adequately connected 3D solid gate passes only when

\[
\ker R=\operatorname{Rigid}(x).
\]

Equivalently, rigid containment and `rank(R)=3N-rank(T)` must both hold with a
complete accepted null basis. Non-rigid nullity is reported independently.
Thin sheets, filaments, and declared underconnected graphs are intentional
flexibility controls; their modes are not silently recategorized as solid
passes. A full-dimensional graph meeting the frozen connectivity gate but
having extra kernel modes is an accidental representation failure.

Rows are scaled to unit Euclidean norm before numerical rank determination.
This preserves the kernel while preventing B, C, and D units from setting the
rank threshold. A zero or nonfinite row is rejected, not normalized.

## 8. Objectivity and affine tests

Each applicable operator is tested on uniform translation, infinitesimal
rigid rotation, isotropic expansion, pure shear, and a general affine field.
Candidate B must reproduce the full affine gradient wherever its moment is
accepted. Candidate C must match the analytic central length rate. Candidate D
must additionally match `dot(tau)=trace(A) tau`.

Candidate C and D finite observables are tested under two proper rotations and
translation using actual lengths and oriented volumes. Translation, proper
rotation, uniform scaling, packet permutation, lookup-grid phase, and
orientation variants are separate metamorphic evidence. Scale covariance is
not called objectivity.

## 9. Conservation and accounting boundary

The experiment is read-only. It changes no mass, momentum, energy, clock, or
physical relation. Numerical rank residuals and discarded modes remain
diagnostics and are never converted to heat or another physical ledger.

## 10. Failure preservation and claim boundary

Preserve singular moments, ill-conditioning, invalid topology, insufficient
affine span, incomplete null bases, ambiguous pivots, non-rigid modes,
objectivity failures, scale/rotation/translation sensitivity, grid-phase
dependence, independent-oracle disagreement, checkpoint changes, and
nondeterministic evidence. No failed row is dropped or repaired.

Formal proofs cover exact finite relational operators. They do not certify
binary64 rank, corrected-gradient sufficiency, material behavior, or a future
mechanics solver. Passing this lab retains only a representation class for
later research; it cannot authorize constitutive mechanics.
