# Relational Observability Confirmation preregistration

**Frozen before implementation and final data:** 2026-08-29 on branch
`relational-observability-confirmation`.  
**Accepted parent:** `baa6beb0b89e70dc2a5baa141366be3f2530a19d`.  
**Accepted Candidate-C source:**
`a71decf8a60c9937e568e712cf9bf13cb68c9bb7`.  
**Seed family:** `260828` (base), with explicitly derived seeds below.

This is a bounded, read-only kinematic confirmation. It cannot promote a
mechanics solver or constitutive law. Candidate C is the only selectable
representation. Candidate B supplies no input to a C gate. Candidate D is not
instantiated unless an eligible generic Candidate-C graph first has a resolved
non-rigid null mode. No force, stiffness, stress, elasticity, pressure,
damping, potential, contact, damage, fracture, gravity, chemistry, organism,
rendering, or GPU work is in scope.

## 1. Frozen representation and provenance

For an explicit undirected relation `(i,j)`, let

```
r_ij = x_j - x_i,       n_ij = r_ij / |r_ij|,
R_ij u = n_ij . (u_j-u_i).
```

Positions `x` are in metres and input velocities `u` are in metres per
second, so the raw unit-direction row is dimensionless and its observable is
in metres per second. Relations are generic physical links. They are not
springs, solids, ropes, or force laws.

The existing `build_bond_rigidity_operator` implementation is reused without
modification. The final evidence records these inherited Git blob hashes and
fails closed if they differ:

| Artifact | Frozen Git blob |
|---|---|
| `include/mls/mechanical_observability_lab.hpp` | `e5007f63ff4984dd5e6fbbb027a26f319cc02e5c` |
| `src/mechanical_observability_lab.cpp` | `9ed0ab945a4178286c59aad9e8f9fd9eb1ac8c87` |
| inherited fixture producer | `ca8082460ba9b34264b393cfb43feaccc8583d99` |
| inherited C++ tests | `b334c2b43dcd7438403b4c87f72e442dcbaec504` |

The direct rectangular one-sided-Jacobi SVD from the accepted Kelvin audit is
the only C++ spectrum path. It acts on `R` itself and never forms `R^T R` or
`R R^T`. Its inherited implementation blob is
`bcdad1a3edaf9fbf4528438f720261141333b394`. No singular value is deleted and
no rank repair, shift, regularization, stabilization, pseudoinverse, or
hourglass penalty is permitted.

The 59 inherited configurations are reproduced from the accepted Mechanical
Observability evidence tables. A full run accepts those fixture tables only
when their complete byte hashes are:

| Table | SHA-256 |
|---|---|
| `configurations.csv` | `557e4327867171aff7fcb34601e6c9548081cd2d6a3a735d2eabaf6dd3f2eb34` |
| `packets.csv` | `b8525b53ace3a87d05d7fc32f0193eaa698d43b3af31321143d3314cd38d258c` |
| `relations.csv` | `89c8189a64cfe27a6d4133dd2a6f5d9d38e96e29fcaea39b0512ea705e7ae6f9` |

Only packet geometry/topology and Candidate-C bond rows are parsed. Candidate
B matrices/ranks and Candidate-D relations/results are never read into the
decision process. Smoke fixtures have a separately recorded non-sealable hash
set and are always marked provisional.

## 2. Raw rank and spectrum rules

Let binary64 `eps=2^-52`, `d=max(6,m,n)`, and `tiny` be the smallest positive
normal binary64 value. Existing complete Householder CPQR operates directly
on raw `R` with:

```
tau_qr = 512 d eps max(first_pivot,tiny)
ambiguity_qr = [tau_qr/8, 8 tau_qr].
```

The independent direct SVD threshold is:

```
tau_svd = 512 d eps max(sigma_max,tiny)
ambiguity_svd = [tau_svd/8, 8 tau_svd].
```

A singular value greater than `8 tau_svd` is accepted nonzero. A value below
`tau_svd/8` is a resolved zero. A value in the closed ambiguity band makes the
configuration ambiguous. Structurally absent tail values when `m<n` are
recorded as exact structural zeros rather than silently omitted.

The C++ rank is accepted only when raw CPQR and direct SVD agree and the
independent exact rank agrees. Complete accepted CPQR null vectors are
retained and individually checked. Normalized matrix-product, rigid-kernel,
projected non-rigid, and orthogonality residual tolerance is:

```
4096 d eps.
```

For a rigid-only graph:

```
mu = sigma_(3N-6) / sigma_max.
```

For a flexible graph, `sigma_min_nonzero` means the smallest accepted nonzero
singular value and `mu` is reported but is not a solid-safety claim. Evidence
also records:

```
nonzero separation = sigma_min_nonzero / (8 tau_svd)
null separation    = (tau_svd/8) / max_resolved_zero.
```

Both must exceed one, no value may be ambiguous, and every numerical/exact
rank must agree. Infinity is emitted only when the resolved null tail is
exactly zero. For robustness probes, the graph must remain rigid-only and its
`mu` must remain at least `1/1024` of the matching baseline. This retention
gate does not replace the absolute threshold-separation gate.

Every raw relation row must have Euclidean norm `sqrt(2)` within

```
64 eps sqrt(2).
```

The wire tables report the equivalent relative error and relative tolerance,
`abs(norm-sqrt(2))/sqrt(2) <= 64 eps`; this is the same gate, not a changed
tolerance.

No row is normalized before rank or spectrum analysis. Similarity spectrum
and operator comparisons use `16384 d eps`. Twin deterministic output must
be byte-identical.

## 3. Inherited configuration matrix

All 59 prior Candidate-C configurations are rerun. The accepted inventory has:

- 37 eligible generic rows (35 ordinary bulk/surface/deletion rows plus exact
  K4 and octahedron controls), each previously observed with rank `3N-6` and
  nullity six;
- 19 deliberately flexible rows (sheet, filament, underconnected, cube-edge,
  planar, and K4-minus-edge controls); and
- three additional non-generic resolved controls: low-radius jitter, low-radius
  simple cubic, and the 40-percent independently hashed deletion graph.

The exact rational controls remain K4, K4-minus-edge, octahedron, cube-edge,
planar square plus diagonal, and the existing enriched-square fixture viewed
strictly through its Candidate-C bond subset. The volume relation is ignored.

Inherited translation, proper rotation, rotation-plus-translation, uniform
half/double scale, packet permutation, relation permutation, lookup/brute-force,
finite-length objectivity, checkpoint, and exact-rank gates continue. Uniform
scale leaves the unit-direction operator spectrum unchanged; it scales only
physical reference lengths.

## 4. Geometry perturbations

Fixed relation topology is perturbed for one eligible identity representative
from each ordinary physical family:

```
bcc35.r180, corner_truncated.r180, edge_truncated.r180,
free_face.r180, jitter27.r180, sc3.r180, sc3_deletion.delete25.
```

For each, use amplitudes `{1/10000,1/1000,1/100}` times nominal spacing and
seeds `{260829,260830,260831}`. Directions are generated by SplitMix64 from
the tuple `(seed, packet_id, axis)`, mapped to signed 53-bit dyadic values in
`[-1,1]`, and then normalized per packet. A zero direction uses the fixed
`+x` direction. The perturbation is applied once to the inherited binary64
geometry; relations are never regenerated. The algorithm and emitted offsets
are independently reconstructed.

## 5. Finite homogeneous geometry probes

Every one of the 37 inherited eligible configurations receives these five
fixed-topology, nonsingular homogeneous deformation probes:

| Probe | Exact `F` | determinant |
|---|---|---:|
| isotropic compression | `(4/5) I` | `64/125` |
| isotropic expansion | `(5/4) I` | `125/64` |
| pure shear/stretch | `diag(5/4,4/5,1)` | `1` |
| simple shear | `[[1,1/4,0],[0,1,0],[0,0,1]]` | `1` |
| general affine | `[[1,1/5,-1/10],[1/10,9/10,1/8],[-1/12,1/10,11/10]]` | `11339/12000` |

All determinants lie in `[1/2,2]`. These are geometry probes, not time steps or
constitutive simulations. No spectrum equality is required for a
non-similarity; rank, rigid quotient, absolute separation, and `mu` retention
are required.

## 6. Nested topology transition

Starting from the 158-edge `base.sc3.r180.original` graph, sort every canonical
edge by the bytewise SHA-256 digest of:

```
260828|relational_observability_nested_delete_v1|first_id|second_id
```

with canonical endpoint IDs as decimal ASCII and digest/endpoint tie breaks.
Emit every state from zero deleted edges through complete deletion, one edge
per state. This path is distinct from, and does not rewrite, the inherited
10/25/40-percent controls whose deletion hashes included different
configuration IDs. Each step reports the complete raw spectrum, rank,
nullity, rigid/non-rigid partition, threshold separations, and `mu`. Exact
rank determines the transition-adjacent states used by the high-precision
audit; C++ rank never selects its own review subset.

Here `last_rigid` is the last state at exact rank `3N-6` and
`first_nonrigid` is the immediately following state below that rank. Their
immediate outer neighbors are marked `transition_adjacent` when they exist.
Only this first loss of generic rigidity defines the transition; later rank
drops inside an already floppy graph are reported but are not additional
selection events. The high-precision subset includes the two bracketing and
two outer rows in addition to its fixed deletion steps.

## 7. Stable-ID bijections

Every inherited configuration receives three deterministic nontrivial full
bijections over its packet IDs:

1. reverse semantic order;
2. cyclic semantic order by one position; and
3. SHA-256 order using
   `260828|relational_observability_id_v1|configuration_id|packet_id`.

New labels are the original label set permuted bijectively; packet physical
state and relation endpoints move together. Relations are canonicalized after
renaming. Comparisons map columns and physical edges back to the source
semantics and admit the corresponding row permutation/sign convention.
Physical graph, rank/nullity, rigid/non-rigid classification, raw singular
spectrum, and `mu` must agree within `16384 d eps`. IDs are labels only.

## 8. Independent verification

The Python verifier is separately implemented and does not call the C++ rank
or SVD code. It reconstructs unnormalized exact rigidity matrices from every
exported binary64 packet coordinate and topology, then computes rank with
exact small-control Fraction RREF or three independent modular primes for all
larger configurations. Unit row scaling cannot change those ranks.

A 90-decimal-digit direct rectangular one-sided-Jacobi SVD checks this bounded
subset, fixed before C++ final data:

- every exact control;
- one maximum-amplitude perturbation for each selected physical family;
- one general-affine deformation for each physical family;
- all three ID-bijection kinds on the SC representative; and
- deletion steps `0,25,50,75,100,125,150,158` plus every exact-rank
  transition-adjacent step.

The verifier recomputes row norms, ranks, rigid partitions, selected spectra,
all hashes/schema facts, checkpoints, derived geometry, metamorphic mappings,
decision ordering, and twin equality. Its mandatory binary64 spectrum path is
an independently implemented direct rectangular one-sided-Jacobi SVD. It may
not form `R^T R` or `R R^T`. A pseudoinverse or Gram spectrum may be used only
as an additional diagnostic and never as a decision premise.

### Pre-final-data evidence hardening amendment (2026-08-29)

Every CPQR null-vector candidate is exported component-by-component in canonical
configuration/mode/packet/axis order. The component table is bound by the same
summary and manifest hashes as every other payload. Its raw little-endian
binary64 component bytes must reproduce the per-vector SHA-256 already recorded
in `nullspace.csv`. Independent verification reconstructs each vector and
recomputes `Rz`, rigid projection, rigid/non-rigid orthogonality, and nullspace
span completeness. This amendment exposes previously hashed numerical witness
state; it does not change Candidate C, a tolerance, a configuration, or the
frozen decision order.

The same pre-final-data adversarial review found that the producer had selected
topology-transition labels from its own uncertified modular lower bound. An
independent exact-Fraction audit of the registered deletion ordering found the
first rank loss at step 54: step 53 attains the structural upper bound 75, and
exact Fraction RREF gives rank 74 at step 54. The registered markers are now
fixed independently of final C++ output: step 52 `transition_adjacent`, step 53
`last_rigid`, step 54 `first_nonrigid`, step 55 `transition_adjacent`, and step
158 `complete_deletion`. Smoke rows carry no transition markers. Every topology
rank now states whether it is an exact-Fraction result, a modular lower bound
that meets the structural upper bound, or an uncertified modular lower bound.
The high-precision deletion subset is expanded to include steps 52--55.

Finite bond-length objectivity is also made an explicit metamorphic gate before
final data. Translation, proper rotation, and rotation-plus-translation must
preserve every physical edge length; registered half/double similarity probes
must scale every length by exactly their declared factor to roundoff. Packet,
relation, and ID permutations must preserve the semantic graph and lengths
after semantic canonicalization. Relation-order testing begins from a reversed
order with reversed endpoint presentation before canonicalization, rather than
silently retesting the already canonical input.

Finally, the validator reconstructs the complete derived inventory from the
accepted fixture tables, registered SplitMix64 perturbations, homogeneous
deformation matrices, deletion ordering, and full ID bijections. Exported
nullspace components are checked independently for hashes, `Rz`, rigid
projection, orthogonality, and span completeness. Full evidence is rejected
unless the configured source branch is exactly
`relational-observability-confirmation`, the source tree was clean at configure
time, and the source SHA is exact. These amendments harden independence and
provenance; they do not change Candidate C or the frozen decision order.

The outer seal additionally requires the repository's current `HEAD`, branch,
and clean status to match the full bundle and successful CI run. It enumerates
the complete committed Git tree, copies every canonical commit blob (not a
hand-selected source subset), records every Git blob ID in sealed provenance,
and rejects a missing, extra, or changed source-snapshot file. It reconstructs
the Git tree object from that inventory and verifies the captured raw commit
object names exactly that tree. Creation also hashes every working-tree input
with Git's path-aware clean filter and compares it to the committed blob, so
`assume-unchanged` or `skip-worktree` cannot conceal a changed build input.
This prevents a post-configure edit or omitted transitive header from being
sealed under an older configure-time SHA.

The seal requires two distinct, non-aliasing full-run directories; byte-for-byte
twin equality; closed JSON field inventories; parsed zero-failure build, test,
producer, validator, formal, and version receipts; and all registered semantic
mutation regressions. CI metadata is fetched independently from the GitHub API
and must show the exact public branch/SHA and successful GCC, Clang, MSVC,
Python-oracle, and pinned-Lean jobs. The public branch and immutable evidence
tag must both resolve to the source SHA, and the repository must be public.
Standalone verification repeats those remote, source, log, CI, bundle, and
decision checks. The reported outer pre-hash is supplied again as an external
verification input so replacing an internally self-consistent seal is
detectable. Provisional smoke may record detached `HEAD` in CI; the full
producer, validator, and seal remain strict to the registered branch.

## 9. Frozen decision order

1. Any implementation, exact-reference, objectivity, ID-renaming,
   nondeterminism, decisive rank ambiguity, trust-gate, or replication failure:
   `stop_inconclusive_or_implementation_failure`.
2. Any eligible generic configuration with a resolved non-rigid mode:
   `reject_central_relational_representation`.
3. All eligible generic configurations rigid-only, but an ordinary registered
   perturbation/deformation becomes unresolved or has `mu` retention below
   `1/1024`:
   `retain_only_as_mathematically_rigid_numerically_unsafe`.
4. Otherwise, every registered generic configuration has exactly the realized
   rigid kernel and a clearly resolved robust margin:
   `retain_central_relational_representation_for_research`.

Even outcome 4 is **NO PROMOTION** to mechanics. If outcome 2 occurs,
Candidate D may be constructed only in a later explicitly amended run; this
confirmation stops and does not instantiate D after seeing the failure.
