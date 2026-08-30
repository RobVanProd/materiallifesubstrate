# Constitutive Expressivity Lab preregistration

**Frozen before implementation and final numerical data:** 2026-08-30 on
branch `constitutive-expressivity-lab`.

**Accepted parent:** `101296f936f8473effb316b1f9ae4040b5768349`.

**Seed:** `260828`.

This document freezes the finite experiment, tolerances, and decision order.
Changing a registered equation, target, tolerance, or decision condition
after a final sweep requires preserving the failed run and issuing a new
version; it may not rewrite prior evidence.

## 1. Frozen retained representation

The accepted unit-direction central rigidity operator is reused without
modification. The following Git blobs must match in every seal:

| Artifact | Frozen Git blob |
|---|---|
| `include/mls/mechanical_observability_lab.hpp` | `e5007f63ff4984dd5e6fbbb027a26f319cc02e5c` |
| `src/mechanical_observability_lab.cpp` | `9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87` |
| direct rectangular SVD in `src/kelvin_covariance_audit.cpp` | `bcdad1a3edaf9fbf4528438f720261141333b394` |

The accepted evidence release
`relational-observability-confirmation-evidence-v1` and its archive SHA-256
`a2b55a45fb5a2ed30d1df747a307cc18857282c55bad72b443a385005ec74e1c`
are immutable external inputs. Candidate B supplies no decision input.
Candidate D is absent.

## 2. Registered constitutive families

### Pair-separable negative control

`E_pair=(1/2) sum_a h_a e_a^2`, with positive diagonal weights only.

The Cauchy control uses seven unoriented unit directions: the three coordinate
axes with weight `8`, and four body-diagonal lines with weight `9`. Their
second moment is `20 I` and fourth moment is

```
sum_a w_a n_ai n_aj n_ak n_al
  = 4 (delta_ij delta_kl + delta_ik delta_jl + delta_il delta_jk).
```

For homogeneous symmetric strain, the diagonal pair energy therefore has
`lambda=mu`, hence in three dimensions `K/G=5/3` and `nu=1/4`. The exact
moment identities and ratio are verified independently before interpreting
the negative control. If this control escapes `K/G=5/3`, the run stops as an
implementation/control failure.

### Local collective candidate

The selectable candidate is exactly the one-star energy in the contract:

```
E_i = (A_i/2) q_i^2/m_i + (B_i/2) sum_a w_ia(e_a-d_i l_a)^2.
```

On the same seven-direction isotropic bulk quadrature cell,

```
m=60,
q=20 tr(epsilon),
sum w(e^d)^2=8 epsilon_dev:epsilon_dev.
```

With `G=1` and target `K>0`, the preregistered map is

```
A=3K/20,
B=G/4.
```

It yields `E=(K/2)(tr epsilon)^2+G epsilon_dev:epsilon_dev`.
The four exact rational targets are `K/G in {1/3,1,2,10}`. No coefficient is
fit after results are inspected.

A global dense positive `H` may be evaluated as an upper-bound diagnostic,
but it is never selectable and cannot satisfy the final decision by itself.

## 3. Strain and tangent inventory

Every target uses the six orthonormal Kelvin symmetric-strain directions:
three axial bases and the three shear bases whose two symmetric off-diagonal
entries are `1/sqrt(2)`. Registered mixed strains are:

```
M1 = [[ 1/5,  1/7, -1/11], [ 1/7, -2/5, 1/13], [-1/11, 1/13, 1/3]],
M2 = [[-1/4,  1/9,  1/10], [ 1/9,  1/6, -1/8 ], [ 1/10,-1/8,  1/12]],
M3 = [[ 2/7, -1/6,  1/5 ], [-1/6,  1/9,  1/14], [ 1/5, 1/14,-3/11]].
```

For each target, evidence separately reports volumetric coefficient,
deviatoric/shear coefficient, Kelvin tangent, tangent-symmetry residual,
volumetric/deviatoric cross coupling, all registered strain energies,
minimum quadratic energy, and rigid-mode energy.

## 4. Bounded accepted-graph inventory

Only these accepted relational configurations are imported from the sealed
parent bundle:

| Role | Configuration ID |
|---|---|
| exact rigid control | `exact.tetrahedron_k4` |
| exact rigid control | `exact.octahedron_graph` |
| regular bulk | `base.sc3.r180.original` |
| BCC-like bulk | `base.bcc35.r180.original` |
| irregular bulk | `base.jitter27.r180.original` |
| free surface | `base.free_face.r180.original` |
| deletion | `base.sc3_deletion.delete25.original` |
| intentionally floppy | `exact.tetrahedron_k4_minus_edge` |

The importer accepts only the sealed packet/topology data and verifies their
manifest hashes. Unit weights are used on these graphs. For every previously
rigid graph, the collective energy must have the same numerical nullity and
no resolved non-rigid zero-energy mode. The K4-minus-edge graph must retain
its accepted non-rigid nullity. Pair response is measured but is not eligible
for selection.

## 5. Finite objectivity and metamorphic inventory

Finite tests use actual reference/current lengths. For each bounded graph,
the following are registered:

- translation `(7/13,-5/11,3/17)`;
- proper rotation: axis `(1,2,3)` and angle `0.731` radians;
- rotation followed by the registered translation;
- uniform reference/current similarities `s in {1/2,2}`;
- reverse and SplitMix64(`260828`) packet permutations;
- reverse and SplitMix64 relation permutations;
- reverse, cyclic, and SHA-256 packet-ID bijections with endpoints renamed;
- a small finite nonsingular deformation
  `F=[[21/20,1/20,-1/40],[0,19/20,1/25],[1/50,0,11/10]]`.

Translations and proper rotations must preserve energy. Similarities must
produce `E_scaled/E_base=s^2` whenever base energy is nonzero and both must be
zero for a rigid probe. Semantic graph canonicalization precedes comparisons;
row sign/order changes may not affect energy.

## 6. Locality, positivity, and kernel diagnostics

Evidence records the complete relation-space `H` sparsity pattern. For the
local candidate an off-diagonal entry is allowed only for relations sharing a
packet. It records nonzeros, density, maximum graph-hop coupling radius
(`<=1`), and maximum Euclidean endpoint coupling radius. Any nonlocal entry is
a decisive implementation failure.

For every graph and ratio, diagnostics include:

- minimum eigenvalue of the symmetric relation-space `H`;
- symmetry residual of `H` and `K=R^T H R`;
- `rank(R)`, `rank(LR)`, and their nullities using direct rectangular paths;
- complete accepted null-vector energy residuals;
- rigid translation/rotation energy residuals;
- positive energy on every accepted non-rigid resolved mode;
- equality of the collective-energy kernel and the accepted `R` kernel.

No regularization, eigenvalue shift, dropped relation, rank repair,
pseudoinverse decision, or stabilization is permitted.

## 7. Frozen numerical tolerances

Let binary64 `eps=2^-52` and
`d=max(6,3*packet_count,relation_count)`. Each reported comparison uses a
declared scale `S=max(1,largest compared magnitude)`.

```
algebra/objectivity absolute tolerance = 32768 d eps S
matrix symmetry tolerance              = 32768 d eps
tangent relative tolerance             = 65536 d eps
target K/G relative tolerance           = 131072 d eps
rigid/null energy tolerance             = 65536 d eps S
positive eigenvalue threshold           = 4096 d eps max(lambda_max,smallest_normal)
rank ambiguity band                     = [tau/8,8 tau]
```

The direct rectangular SVD rank threshold remains
`tau=512 d eps max(sigma_max,smallest_normal)`, matching the accepted
representation lab. A value in an ambiguity band stops the run. Independent
high-precision checks use at least 80 decimal digits. Twin final output must
be byte-identical.

## 8. Independent verification and evidence

A Python implementation independently reconstructs the seven-direction
moments, pair Cauchy ratio, collective energies/tangents, finite length
energies, graph locality, selected exact rational Hessian ranks, high-
precision spectra, metamorphic transformations, and final decision. It does
not accept C++ summary fields as premises. Mutation tests must demonstrate
rejection of altered energy, locality, target ratio, ID mapping, kernel,
source provenance, twin bytes, and decision.

The final seal requires a clean exact source SHA; complete source snapshot;
warning-as-error GCC, Clang, and MSVC builds; unfiltered CTest; distinct twin
producers; independent validation; Python exact control; pinned Lean build;
axiom/source trust reports; public CI replication; and an immutable public
tag. Failed runs are preserved outside the canonical seal.

## 9. Decision order

1. Any implementation, exact-reference, Cauchy-control, objectivity, ID,
   permutation, nondeterminism, positivity, source, or rank ambiguity gives
   `stop_inconclusive_or_implementation_failure`.
2. If the pair-separable control escapes the registered Cauchy restriction,
   stop and investigate.
3. If the local collective law cannot independently realize all four bulk/
   shear targets, record
   `local_collective_constitutive_parameterization_or_locality_failure` and
   stop.
4. If only a dense/global `H` succeeds, record
   `representation_expressive_but_local_constitutive_law_unresolved`.
5. If the local collective distance-only energy realizes all targets,
   remains positive/objective/local, preserves every eligible rigid-only
   kernel, preserves the intentionally floppy control, and passes every
   exact/metamorphic gate, record
   `retain_local_collective_relational_energy_for_research`.

Every result is `NO PROMOTION` to mechanics or dynamics.
