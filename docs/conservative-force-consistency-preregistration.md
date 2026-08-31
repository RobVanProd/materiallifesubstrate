# Conservative Force Consistency Lab preregistration

**Frozen before implementation and final numerical data:** 2026-08-30 on
branch `conservative-force-consistency-lab`.

**Accepted parent:** `2de8843faf76a75d16b3a3012897e719291c52cf`.

**Accepted evidence:** `constitutive-expressivity-lab-evidence-v1`.

**Seed:** `260828`.

Changing a registered equation, case, tolerance, or decision condition after
a final sweep requires preserving that run and creating a new evidence
version.  A failed run may not be rewritten or relabelled.

## 1. Frozen inherited energy

The following accepted blobs are read-only inputs and must match in the final
seal:

| Artifact | Frozen Git blob |
|---|---|
| `include/mls/constitutive_expressivity_lab.hpp` | `ba5743419cd956d9bc77b979ea3ec803cd5c4547` |
| `src/constitutive_expressivity_lab.cpp` | `1186bc643b8677ca8d72dba4347e26d5d07e8031` |
| `apps/constitutive_expressivity_diagnostic.cpp` | `ed6fd9eb0704262ca041c30fe8e091e4923028a6` |
| accepted constitutive preregistration | `4afa56de497035338b1c9b9299740b2691f471c3` |

The force lab consumes the accepted `RelationEnergyOperator` and its canonical
relation ordering.  It may add a separate read-only evaluator, but it may not
modify the inherited energy builder or accepted producer.

### Pre-final symmetric-storage audit

The sealed parent reports small nonzero binary64 `H` symmetry residuals (from
zero through `2^-53` across the 24 registered graph/policy rows).  Therefore
directly treating the two independently accumulated
triangles as an exactly symmetric matrix would make `g=H e` disagree in high
precision with the derivative of `U=(1/2)e^THe`.

Before final data, force-lab setup creates one canonical reference matrix:

```text
H_force[i,j] = H_force[j,i]
             = (H_parent[i,j]+H_parent[j,i])/2.
```

Each unordered pair is evaluated once with one binary64 addition followed by
multiplication by exactly representable `1/2`, then mirrored byte-for-byte;
the diagonal is copied unchanged.  Evidence records both parent entries, the
frozen entry, and maximum correction.  Setup fails if the correction exceeds
`32768 d eps max(max_abs(H_parent),tiny)`, the accepted parent-class symmetry
scale.  This preserves the exact quadratic form because the removed component
is antisymmetric.  It does not shift eigenvalues, add a diagonal, alter
locality, or use current geometry.  All evaluations use only `H_force`.

Only the local incident-collective family is selectable.  The three registered
policies use `G=1`, `B=1/4`, and `A=3(K/G)/20` in the accepted finite-graph
convention:

```text
K/G = 1/3: A=1/20, B=1/4
K/G = 2:   A=3/10, B=1/4
K/G = 10:  A=3/2,  B=1/4.
```

No coefficient is fitted after results are inspected.  The complete parent
`H`, canonical `H_force`, correction, reference lengths, weights,
coefficients, graph, and semantic coordinate map are exported and
integrity-bound.

## 2. Bounded graph and deformation inventory

The exact eight accepted parent configurations are:

| Role | Configuration ID |
|---|---|
| exact rigid | `exact.tetrahedron_k4` |
| exact rigid | `exact.octahedron_graph` |
| regular bulk | `base.sc3.r180.original` |
| BCC-like bulk | `base.bcc35.r180.original` |
| jittered bulk | `base.jitter27.r180.original` |
| free surface | `base.free_face.r180.original` |
| relation deletion | `base.sc3_deletion.delete25.original` |
| intentionally floppy | `exact.tetrahedron_k4_minus_edge` |

Each policy uses the reference state plus these current homogeneous probes,
applied about the packet centroid:

```text
F_general  = [[21/20, 1/20,-1/40], [0,19/20,1/25], [1/50,0,11/10]]
F_shear    = [[1,3/20,0], [0,1,1/20], [0,0,1]]
F_compress = diag(4/5,9/10,17/20).
```

All determinants are positive and bounded away from zero.  Reference rows
must report exactly zero extension, energy, conjugate force, and packet force
within arithmetic representation.

The intentionally floppy graph is additionally displaced along its accepted
linearized non-rigid mechanism at amplitudes
`epsilon/L in {2^-8,2^-12,2^-16,2^-20}`.  Its force divided by epsilon must
converge to zero at reference; the energy may respond at higher nonlinear
order.  The law may not fabricate a linear restoring mode absent from `R0`.

## 3. Independent gradient inventory

Every binary64 row is reconstructed independently from exported data.
High-precision directional checks are limited to K4, the octahedron, and the
jittered bulk, all three policies, and `F_general`.

For each such evaluation use:

- the three normalised global translations;
- three normalised infinitesimal rotations about the current centroid;
- six normalised SplitMix64(`260828` plus semantic case index) directions.

The high-precision symmetric directional difference uses 100 decimal digits
and dimensionless steps relative to characteristic length

```text
h/L in {10^-8,10^-12,10^-16,10^-20}.
```

It compares `dU/dalpha` with `-f dot d`.  The four raw centred estimates are
retained.  The registered numerical estimate is their deterministic
Richardson extrapolation to `h^2=0`: interpolate the four `(h_k^2,D(h_k))`
pairs with exact high-precision arithmetic and evaluate that degree-three
polynomial at zero.  This removes the registered `h^2`, `h^4`, and `h^6`
terms without changing or adding sample levels.  A direction passes when the
analytic value agrees with that extrapolated estimate to relative `1e-45` or
absolute `1e-55 J` after the registered dimensional normalisation, and at
least the first three nonzero raw truncation errors decrease.  Translation
and rotation directions also require the analytic derivative to satisfy the
high-precision zero-work bound `1e-55 J`.

### Pre-final estimator consistency amendment

Before any final sweep, an implementation-audit K4 sample showed the expected
second-order raw residual sequence of approximately `1.279e-18`, `1.279e-26`,
`1.279e-34`, and `1.279e-42` at the four registered levels.  Therefore a raw
`h=1e-20` centred difference cannot by itself satisfy `1e-45`; treating it as
the oracle would make the preregistration internally inconsistent.  The
Richardson definition above makes the already named "best pre-roundoff
high-precision estimate" explicit.  This amendment does not relax a
tolerance, omit a raw row, add a smaller step, or use final-sweep results.

Ordinary binary64 finite differences are recorded only as diagnostics and
cannot satisfy the independent-gradient gate.

## 4. Reference tangent limit

For every graph and all three policies, use six normalised deterministic
packet-displacement directions: three SplitMix64 directions, one isotropic
affine direction, one pure-shear direction, and one general affine direction.
Evaluate

```text
f(X+epsilon u)/epsilon -> -R0^T H R0 u
```

at

```text
epsilon/L in {2^-6,2^-9,2^-12,2^-15,2^-18,2^-21}.
```

Errors are measured in a scale-normalised infinity norm.  Before roundoff
dominates, at least three consecutive refinement pairs must decrease, the
median observed order over those pairs must lie in `[0.75,1.25]`, and the
minimum relative error must be at most `2e-5`.  An exactly zero target uses the
registered absolute force scale instead of division by zero.

## 5. Force, torque, and power identities

Every non-reference evaluation reports independently accumulated:

- total force;
- torque about the origin;
- torque about `o=(7/13,-5/11,3/17) m`;
- `g dot Rv`, `-f dot v`, and their residual.

Velocity probes are the three global translations, the three rigid rotations
used above, a registered affine velocity

```text
A_v=[[1/7,-1/11,1/13],[2/17,-1/19,1/23],[-1/29,2/31,1/37]] s^-1,
b_v=(1/5,-1/7,1/11) m/s,
```

and two normalised SplitMix64 velocity fields.  Rigid velocities must perform
zero work.  No result is interpreted as a discrete-time conservation claim.

## 6. Objectivity, covariance, and semantic invariance

Every graph/policy uses `F_general` as the baseline for:

- current translation `t=(7/13,-5/11,3/17) m`;
- common proper rotation about axis `(1,2,3)` by `0.731` radians;
- common rotation plus translation;
- common similarities `s in {1/2,2}`;
- reverse and SplitMix64 packet permutations;
- reverse and SplitMix64 relation permutations;
- reverse, cyclic, and SHA-256-derived packet-ID bijections;
- all relation endpoints reversed.

After semantic canonicalisation, translations and rotations require `U'=U`
and `f'=Qf`; similarities require `U'=s^2U`, `f'=sf`, and unchanged tangent;
ID/order/orientation probes require identical semantic packet forces and
relation conjugates.  H is permuted explicitly where relation coordinates
move and is never rebuilt from transformed current geometry.

## 7. Finite tangent and conservativity subset

For K4, the octahedron, and jittered bulk; all three policies; and
`F_general` plus `F_compress`, export the complete material, geometric, total
energy-Hessian, and force-Jacobian matrices.

The independent 100-decimal path rebuilds the analytic Hessian and estimates
the force Jacobian with symmetric directional differences at
`h/L in {10^-8,10^-12,10^-16,10^-20}`.  It requires:

- `K_total = K_material+K_geometric`;
- `df/dx=-K_total`;
- symmetry of the energy Hessian;
- equality of mixed partials;
- high-precision directional agreement to relative `1e-40` or absolute
  `1e-50 N/m` after dimensional normalisation.

The finite-tangent numerical estimate uses the same registered polynomial
extrapolation in `h^2` over all four raw centred levels.  Every raw level and
its residual remains in evidence; extrapolation cannot hide nonconvergence.

Material and geometric terms remain separate in evidence.  No normal-equation
or nonsymmetric approximation can replace the scalar-potential Hessian.

## 8. Positive collapse approach and exact-coincidence gate

Use K4 and the octahedron at `K/G in {1/3,2,10}`.  Select the lowest semantic
relation, hold one endpoint fixed, and move the other along its original line
while all other packets remain fixed.  Registered positive ratios are

```text
r/l0 in {1,2^-4,2^-8,2^-12,2^-16,2^-20,2^-24,2^-28,2^-32}.
```

Additional diagnostic-only ratios `{2^-36,2^-40,2^-44,2^-48}` probe the
binary64 boundary but cannot weaken the registered `2^-32` domain floor.
Each raw producer row records force magnitude,
material/geometric/total tangent norms, condition estimate, a
`binary64_gradient_error_n` diagnostic, and one-ulp coordinate sensitivity.
The producer may not label that diagnostic independent or high precision.  The
final validator independently recomputes the registered high-precision
collapse-gradient checks from exported inputs and binds their result in its
validation receipt and decision.  Any nonfinite result, direction loss, failed
high-precision gradient, or failure to distinguish adjacent positive lengths
at or above `2^-32` records numerical degeneracy before the registered limit.

At `r=0` the evaluator must return the explicit `coincident_relation` domain
failure before emitting partial energy or force.  No epsilon direction,
repulsion, altered `H`, or regularisation is allowed.

## 9. Frozen binary64 arithmetic gates

Let `eps=2^-52`, `tiny` be the smallest positive normal binary64 value, and
`d=max(6,3*packet_count,relation_count)`.  For a sum of vector/scalar terms,
`S_abs` is the sum of the absolute term magnitudes in the same physical unit.
For comparing quantities, `S_cmp=max(abs(values),tiny)`.

```text
force/torque/power balance tolerance = 65536 d eps max(S_abs,tiny)
energy/force covariance tolerance    = 65536 d eps S_cmp
force-gradient identity tolerance    = 131072 d eps S_cmp
tangent decomposition/symmetry       = 262144 d eps S_cmp
reference zero-force tolerance        = 65536 d eps max(H_scale L,tiny)
scaling-law relative tolerance        = 131072 d eps
```

All tolerance scales and raw residuals are exported.  Integer counts,
semantic mappings, manifest hashes, exact coincidence status, and twin bytes
must match exactly.  A residual inside tolerance is numerical evidence only,
not by itself a claim of physical validity.

## 10. Evidence and replication gates

The final evidence requires:

- a clean exact source SHA and frozen inherited blobs;
- deterministic twin C++ producer bundles;
- a deterministic independent Python materialisation stage applied separately
  to each producer bundle, followed by byte-identical final bundles;
- independent Python reconstruction and mutation tests;
- high-precision gradient/tangent controls;
- warning-as-error GCC, Clang, and MSVC builds with unfiltered CTest;
- pinned Lean build, source scan, and exported axiom report;
- public CI at the exact source SHA;
- canonical checkpoint/round-trip evidence where a producer checkpoint exists;
- an immutable public tag, outer seal, deterministic archive, and fresh public
  download verification.

Failures are preserved outside canonical evidence.  Failed solves/checks are
evidence and may not be filtered from the final tables.

### Two-stage evidence boundary

The C++ producer is forbidden to populate or pass the registered 100-decimal
fields.  It emits a closed raw producer bundle containing frozen inputs,
binary64 analytic force/tangent results and registered binary64 tangent step
rows, an explicit `high_precision_stage=pending` marker, and no final
scientific decision.  The independent directional-derivative table does not
exist in the raw inventory; its directions are bound through the exported
evaluation/current-packet rows and are materialised only by Python.

An independent Python materialiser first validates that raw manifest, copies
the complete producer tree byte-for-byte under `producer/`, computes the
registered high-precision rows from exported inputs, and writes a distinct
final manifest/summary.  The final validator recomputes the finite energy,
gradient, tangent, and high-precision controls from `producer/` rather than
accepting either C++ pass fields or materialised pass fields as premises.
Both full pipelines are executed independently and the final trees must be
byte-identical.  This division is preregistered before the first full sweep;
it prevents binary64 C++ from claiming an impossible decimal oracle result.

### Pre-final integration-audit clarifications

Before any final sweep, cross-implementation audit found several places where
the closed evidence representation needed to be made explicit.  These rules
do not change the registered cases, tolerances, or decision order:

- the producer consumes the accepted Constitutive Expressivity bundle's
  selected top-level `configurations.csv`, `packets.csv`, and `relations.csv`
  directly, with their accepted selected-subset hashes; the earlier complete
  relational fixture hashes remain parent provenance and are not a second
  producer input;
- a producer `pass` field records only the binary64 predicate documented for
  that producer row.  Independent Decimal/high-precision failures are recorded
  separately and drive the bounded scientific decision; disagreement with the
  producer's scientific conclusion is not converted into a schema failure;
- every registered random, affine, permutation, endpoint-reversal, ID, and
  similarity probe is independently reconstructed from its semantic ID, the
  frozen seed, and registered formula.  Exported maps are checked against that
  reconstruction rather than accepted as premises.  Submitted packet order is
  retained so packet-order probes remain auditable;
- the independent directional table includes the directional work computed
  from exported C++ packet forces as well as the independently derived Decimal
  analytic work and high-precision energy derivative.  The C++ work is checked
  against both independent values using the frozen dimensionally appropriate
  arithmetic bound; the Decimal analytic/Richardson pair retains the registered
  high-precision tolerance;
- positive-collapse `force_norm_n` is the Euclidean norm of the complete `3N`
  packet-force vector.  Each tangent norm is the Frobenius norm of the complete
  matrix.  These rotationally invariant definitions replace no registered
  threshold and are used identically by producer and validator;
- comparisons use the dimensioned `S_cmp=max(abs(values),tiny)` rule above;
  no bare unitless `1` is inserted into joule, newton, watt, or newton-metre
  scales.  The similarity-ratio tolerance is exactly the dimensionless
  `131072 d eps`, without multiplication by the ratio magnitude;
- an irrational reference distance stored in binary64 need not equal the exact
  Decimal norm of the exported binary64 coordinates.  The producer's exact
  zero-at-reference arithmetic contract and the independent real-valued
  reconstruction are both retained and compared with a declared dimensioned
  representation-roundoff bound; frozen reference lengths are never silently
  recomputed from current geometry.

## 11. Decision order

1. Any inherited-blob, implementation, provenance, exact-reference,
   nondeterminism, high-precision, source, or decisive arithmetic ambiguity
   gives `stop_inconclusive_or_implementation_failure`.
2. Energy/gradient disagreement gives `reject_force_implementation`.
3. Resolved nonzero total force or torque outside registered arithmetic bounds
   gives `reject_force_conservation`.
4. Failed reference-tangent limit or nonsymmetric conservative tangent gives
   `reject_finite_force_consistency`.
5. If all ordinary noncoincident checks pass but the positive collapse path is
   numerically unresolved at or above `r/l0=2^-32`, record
   `retain_force_but_block_dynamics_on_degeneracy`.
6. If every registered noncoincident case passes gradient, objectivity,
   force/torque, power, tangent, semantic, and collapse-domain gates, record
   `retain_conservative_relational_force_for_research`.

Every result is `NO_PROMOTION` to dynamics.  The lab stops after sealing.
