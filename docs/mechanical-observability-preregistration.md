# Mechanical Observability Lab preregistration

**Frozen before final sweep:** 2026-08-29 on branch
`mechanical-observability-lab`.  
**Accepted parent:** `2e175396ff30faea8a4d96d5a0336ab9ba042f12`.  
**Seed:** `260828` for rational jitter, relation deletion, mutation order, and
evidence provenance.

No candidate, configuration, tolerance, rank rule, or decision rule below may
change after the final full producer is run. Exploratory output is marked
dirty/provisional and cannot be sealed.

## 0. Pre-final affine-realization amendment (2026-08-29)

The rejected full sweep produced at source `2e563edac0bb7dfe721e471a0c171ca84b8b9075`
remains unchanged. Its two preserved bundles exposed an implementation-level
inconsistency before any evidence was sealed: independently rounding every
coordinate of an exact rational similarity transform made an intended
filament microscopically three-dimensional and made several intended sheets
microscopically nonplanar. In particular, the emitted
`base.filament.r205.original.rotation_translation` packet positions had exact
dyadic affine rank three and rigid-generator rank six, while the binary64
rigid-basis construction resolved rank five. The rejected sweep and this
finding remain negative provenance; they are not rewritten by this amendment.

Before the next full producer run, every rational fixture is realized through
one common dyadic affine lattice. For each configuration, write all untransformed
rational packet coordinates as integer triples over their least common
denominator `D`. Apply the registered rational rotation, scale, and translation
to one affine origin and to the three `1/D m` coordinate increments. Round
those twelve affine-frame quantities once, ties-to-even, to the fixed quantum

\[
q_x=2^{-50}\ \mathrm{m}.
\]

Reconstruct every emitted packet position from the resulting integer origin,
integer basis increments, and the packet's unchanged integer coordinate
triple. Jitter-offset evidence uses the same quantized linear basis without
the affine origin. This rule is generic: it is not conditional on a filament,
sheet, candidate, observed rank, or outcome. The emitted binary64 packet
positions remain the sole state consumed by every observability operator; the
integer frame is fixture-construction machinery and is not persistent physical
or numerical auxiliary state.

The producer must fail closed unless every reconstruction intermediate fits a
signed 64-bit integer and every final dyadic numerator has magnitude at most
`2^53`, so conversion to binary64 is exact. It must also rederive radius edges,
affine span, incident-direction rank, and rigid-generator rank from the emitted
packet positions. The final sweep must retain the existing finite-objectivity,
metamorphic, exact-rank, nullspace, compiler, checkpoint, and independent-
validator gates.

This amendment changes no candidate, physical configuration, support radius,
field, scientific tolerance, numerical-rank threshold, ambiguity band,
residual rule, or decision rule. It specifies a correlated binary64
realization of the already registered rational transforms so a rigid transform
does not acquire a false geometric dimension solely through independently
rounded coordinates. A q=50 pre-run diagnostic bounded the largest coordinate
departure from the ideal rational transforms by `2.78e-15 m`, retained the
registered filament and sheet edge inventories, and remained more than four
orders of magnitude inside the unchanged spectral-invariance tolerances. Those
diagnostics are design checks only; the regenerated producer evidence must
pass the frozen gates independently.

Two narrower responses were rejected. Lowering or bypassing the exact-rank
check would hide actual emitted-state topology and weaken the registered gate.
Forcing a sixth orthonormal rigid vector from the old, roundoff-warped filament
could satisfy a local residual check, but it would promote an approximately
ULP-sized coordinate artifact into the physical rigid/non-rigid partition and
would leave the sheet topology drift unresolved. Neither response is used.

## 1. Frozen candidates

- **A — frozen quadratic-grid control.** Use the accepted tensor-product
  quadratic B-spline sampling and analytic derivative unchanged. Report
  `S_A`, `D_A`, complete accepted sampling-null modes, and the quotient test
  `ker(S_A) subset ker(D_A)`. Never construct a grid lift. The two operators
  are one acceptance pair: `S_A` is rank-applicable only when both operators
  build, `D_A` is never rank-applicable, and a failure in either half
  suppresses all pair rank/null/gauge evidence while retaining the successful
  raw half and the failed half's closed witness. Even for a fully built pair,
  gauge evidence requires an analyzed, unambiguous, basis-complete sampling
  rank. A partial or unresolved pair makes the negative-control and decisive-
  rank gates false and forces the implementation STOP.
- **B — packet WLS gradient.** Use the exact cutoff and weight
  `w=(1-r^2/H^2)^2` from the contract, sorted Euclidean packet IDs, and
  `G=B M^-1`. Its observability operator is `vec(sym G)`.
- **C — central-distance graph.** Use explicit canonical simple edges and the
  actual rigidity matrix. The graph is physical input.
- **D — objective volume enrichment.** This type is frozen now but is included
  in the final candidate sweep only if a `generic_solid_gate=true` C row has a
  resolved non-rigid null mode and every independently generic non-exact C row
  has first passed its complete local contract. That contract requires a built
  and normalized C operator, analyzed/unambiguous rank, a complete kernel
  basis, rigid-subspace containment, a resolved non-rigid quotient, and every
  registered null/rigid/quotient/orthogonality residual within tolerance. Any
  invalid generic C row blocks enrichment and forces the implementation stop.
  That trigger is global: if it fires, D is
  instantiated across every non-exact configuration using the selector frozen
  on that configuration's original/base geometry; metamorphic variants retain
  those physical relation IDs. A D operator is built exactly when the selected
  tuple set is nonempty. Only generic-solid D rows enter the scientific
  decision. D concatenates C with at most one explicit ordered volume relation
  per center packet. The exact enriched-square control is always built and is
  exempt from the global trigger.

The D relation-selection rule is fixed before data. At a center with at least
three incident neighbors, enumerate sorted neighbor triples. For
`a,b,c` choose the triple maximizing

\[
\lVert b\times c\rVert^2+\lVert c\times a\rVert^2+
\lVert a\times b\rVert^2,
\]

breaking exact ties lexicographically by stable IDs. Emit no tuple when that
score is zero. The tuple order is `(center,j,k,l)` with `j<k<l`; its determinant
sign is not canonicalized away. No second enrichment type may be introduced.

The exact edge-count bound makes the cube-edge and deliberately underconnected
controls C-floppy before any numerical sweep. They do not trigger D because
they are not generic-solid gates. D is triggered only by an adequately
connected ordinary 3D C failure, preventing enrichment from being justified by
an intentionally flexible control.

## 2. Physical graph and solid-gate classification

For radius-generated C profiles, edges are generated once by an exact
Euclidean-radius rule, canonicalized `(min_id,max_id)`, recorded in the
authoritative laboratory state, and then treated as explicit input. A lookup
grid may reproduce this generation for auditing but cannot change it.

Before operator rank is evaluated, a graph is marked
`generic_solid_gate=true` only when all of these topology/geometry facts hold:

1. the packet positions have affine span three;
2. the graph is connected;
3. `|E| >= 3N-6`;
4. every packet has at least three incident edges whose direction span has
   exact or high-precision rank three; and
5. the sampled rigid-motion generator has rank six.

These are a frozen eligibility screen, not a proof of rigidity. A graph that
passes the screen and still has extra kernel modes is an accidental C failure.
Sheet, filament, and explicit underconnected controls are always intentionally
flexible. Deleted graphs are classified by the same facts before their
rigidity rank is inspected.

The affine-span, incident-direction, and rigid-generator eligibility ranks are
computed exactly over the rational values represented by the emitted
binary64 coordinates (dyadic arithmetic, no floating rank threshold). The
producer and independent validator must agree exactly on those topology facts.

## 3. Frozen base configuration matrix

Nominal spacing is `a=1/4 m` unless stated otherwise. Base coordinates are
rational. The seeded jitter table adds independently generated integer offsets
in `[-7,7]/100*a` and is stored verbatim; it is never regenerated from a
different RNG implementation.

| Family | Packets | Physical/support profiles |
|---|---:|---|
| regular simple-cubic `3x3x3` | 27 | `H/a = 21/20, 3/2, 9/5` |
| finite BCC-like: `3^3` corners plus `2^3` centers | 35 | same three ratios |
| seeded jittered simple-cubic `3x3x3` | 27 | same three ratios |
| free-face `4x4x3` patch | 48 | `H/a = 3/2, 9/5` |
| edge-truncated `4x3x3` patch | 36 | `H/a = 3/2, 9/5` |
| corner-truncated `3x3x3` patch | 27 | `H/a = 3/2, 9/5` |
| thin sheet `5x5x1` | 25 | `H/a = 21/20, 3/2` |
| filament `8x1x1` | 8 | `H/a = 21/20, 41/20` |
| explicit noncoplanar underconnected graph | 4 | K4 with one edge removed |
| simple-cubic high-radius relation deletion | 27 | `10%, 25%, 40%` of edges |

For deletion controls, sort edges by SHA-256 of
`seed || configuration_id || low_id || high_id`, then remove the requested
floor percentage. The complete retained and deleted edge lists and digests are
evidence. No disconnected or underconnected result is dropped.

### Exact small controls

- noncoplanar K4 tetrahedron;
- K4 with one edge removed;
- octahedron edge graph;
- cube edge graph;
- planar square plus one diagonal; and
- that square plus the single ordered volume tuple `(0,1,2,3)`.

Exact Fraction RREF preregisters expected central ranks/nullities:
`K4=6/6`, `K4-minus-edge=5/7`, `octahedron=12/6`, and
`square-plus-diagonal=5/7`. Before any C++ full sweep, the independent
Fraction oracle confirmed that adding the registered oriented-volume
derivative gives the square rank/nullity `6/6`; its canonical pre-hash is
`86b4d4c3d024f3cee683cf90ee6e757b68b4e57d55ad607bde84d87e111c0a83`.
This confirmation freezes D's only enrichment type; it is not final numerical
candidate evidence.

## 4. Metamorphic matrix

For the high-radius representatives `SC`, `BCC`, `jitter`, `corner`, the
mid-radius sheet, and the long-radius filament, add these five variants while
retaining the original:

1. translation `t=(13,-7,21)/100 m`;
2. proper rational-quaternion rotation from `q=(1,2,2,0)`;
3. that rotation followed by `t`;
4. scale `1/2` followed by that rotation; and
5. scale `2` followed by that rotation.

Scale `a`, `H`, and diagnostic grid spacing with geometry. Packet IDs and
physical relation IDs are unchanged. The rational quaternion rotation is
orthogonal with determinant one in exact arithmetic.

Candidate A runs on these six representative originals at grid phases
`p000=(0,0,0)` and `p037_011_029=(0.37,0.11,0.29)h`. B, C, and D use no grid
quantity, but their brute-force neighbor/relation outputs must be identical
when a lookup-grid enumerator is translated through those phases.

## 5. Affine and finite-objectivity fields

At every applicable row use:

- translation: `A=0`, `b=(2,-3,5)/10 m/s`;
- infinitesimal rotation with
  `omega=(3,-2,4)/10 1/s` and `A x=omega cross x`;
- isotropic expansion `A=(1/5)I 1/s`;
- pure symmetric shear `A_xy=A_yx=3/10 1/s`; and
- general affine
  `A=[[1/5,-1/10,3/20],[1/4,-3/20,1/10],[-1/5,1/8,1/20]] 1/s`,
  `b=(-1,2,1)/10 m/s`.

Candidate B reports the full `G_p-A`; its symmetric operator is tested
separately. Candidate C's analytic target is
`n dot (A r)=l n^T sym(A)n`. Candidate D's volume target is
`trace(A)*tau`.

Candidate D has no mixed-dimension affine norm. Every field emits and gates a
bond-only block in `m/s` and, when present, a volume-only block in `m^3/s`,
each using only its homogeneous operator rows, values, target, Frobenius norm,
and tolerance. A failing volume block cannot be diluted by many correct bond
rows.

Finite C/D objectivity uses actual edge lengths and oriented volumes under the
rational-quaternion rotation above, under a proper signed-axis 180-degree
rotation, and with translation. Scale covariance is recorded separately.

## 6. Moment acceptance

A B moment must be finite, symmetric to roundoff, and positive definite. Dense
three-by-three eigen diagnostics are numerical estimates. Fail a packet when

\[
\kappa_2(M_p)>10^{10}
\]

or the smallest estimated eigenvalue is nonpositive. There is no inverse,
operator row, or fabricated affine pass for a failed packet. A configuration
is B-rank eligible only when every packet moment is accepted.

For accepted moments require

\[
\frac{\lVert M_pM_p^{-1}-I\rVert_F}
{\max(1,\lVert M_p\rVert_F\lVert M_p^{-1}\rVert_F)}
\le 4096\cdot 3\epsilon_{64}.
\]

## 7. Numerical rank and nullspace gates

Before numerical rank, divide each nonzero operator row by its L2 norm. This
does not change its exact kernel. A zero or nonfinite row is an explicit
operator failure.

Use deterministic binary64 Householder QR with column pivoting. If `d0` is the
first absolute diagonal,

\[
\tau_R=512\max(m,n)\epsilon_{64}\max(d_0,\mathrm{minnormal}).
\]

Any pivot in `[tau_R/8,8 tau_R]` makes the row `rank_ambiguous`; it cannot pass
or promote. Rank is always called a numerical threshold estimate. Ambiguity
retains the complete pivot trace but quarantines derived bases/metrics and
records `rank_estimation,ambiguity_band_overlap`. For an analyzed row, emit
every free-column null basis vector and the full pivot/permutation trace.

Independent validation uses a two-path QRCP audit without changing that
threshold or ambiguity band. It first replays the producer's complete claimed
permutation to derive `d0`, `tau_R`, and `tau_R/8`. It then requires a maximal
(or roundoff-tied) claimed pivot whenever the independently measured remaining
suffix norm exceeds `tau_R/8`; a nonzero suffix wholly below that registered
resolution floor may have a different pivot order. An identically zero suffix
may not be permuted. A separately factored greedy QRCP trace must agree with
the claimed-path trace on rank above the lower and upper band limits and on
ambiguity classification. Every claimed diagonal, acceptance bit, rank/nullity
field, basis, and residual remains independently replayed and gated.

Let `Q` be an orthonormal basis of the realized rigid-generator range and `Z`
the complete accepted null basis. Require

\[
\rho_{rigid}=\frac{\lVert RQ\rVert_F}
{\max(\lVert R\rVert_F\lVert Q\rVert_F,\mathrm{minnormal})},
\]

\[
\rho_{null}=\frac{\lVert RZ\rVert_F}
{\max(\lVert R\rVert_F\lVert Z\rVert_F,\mathrm{minnormal})}
\]

to be at most

\[
4096\max(m,n)\epsilon_{64}.
\]

Project the null basis through `I-QQ^T`, reorthogonalize, and report a complete
non-rigid basis. Verify its `R` image and orthogonality to `Q` to the same
bound. Never determine non-rigidity from a plotted mode.

A generic 3D row passes only with complete bases, rigid containment, no rank
ambiguity, and `rank(R)=3N-rank(Q)`. Degenerate controls compare against the
actual `rank(Q)` and remain ineligible for a generic-solid pass.

If a completed kernel basis measures that rigid motion is visible,
`nonrigid_nullity` is undefined (`NA`): retain complete-kernel evidence, omit
the non-rigid quotient, and fail generic observability. Basis-construction
failures retain raw rigid generators only and use one of the closed reasons
`incomplete_kernel`, `rigid_span_failure`, `nonrigid_quotient_failure`, or
`nonfinite_basis`; unevaluated summary fields are `NA`.

## 8. Affine, objectivity, and invariance tolerances

For a linear observable target `y`, use

\[
\eta=\frac{\lVert Rv-y\rVert_2}
{\max(\lVert R\rVert_F\lVert v\rVert_2+\lVert y\rVert_2,
\mathrm{minnormal})}
\]

with threshold `4096*max(m,n)*epsilon64`.

For finite length/volume operations let
`gamma(k)=k epsilon64/(1-k epsilon64)`. The registered end-to-end operation
counts are 72 for a bond row and 134 for an oriented-volume row. They cover the
actual similarity-transform construction, reference and transformed
observable, scale target, and final subtraction. The measured, target, and
absolute-error cells retain that binary64 path.

The forward-error operand scale includes coordinate construction and
cancellation, rather than only the final result. For point `x`, similarity
`(Q,t,s)`, and axis `a`, define, in the written left-to-right grouping,

`P_a(x)=|s|*((|Q_a0*x_0|+|Q_a1*x_1|)+|Q_a2*x_2|)+|t_a|`.

For site `p` relative to center/endpoint `c`, define
`R_a(p,c)=|x_p,a|+|x_c,a|` and `T_a(p,c)=P_a(x_p)+P_a(x_c)`. A bond uses

`S_b=max(minnormal, (((|s|*((R_x+R_y)+R_z))+((T_x+T_y)+T_z))`
`+|measured|)+|target|))`.

For nonnegative component envelopes define

`E(a,b,c)=a_x*(b_y*c_z+b_z*c_y)+a_y*(b_x*c_z+b_z*c_x)`
`+a_z*(b_x*c_y+b_y*c_x)`,

with the three outer terms also added left to right. An ordered volume uses the
three `R` and `T` vectors from its non-center sites and

`S_v=max(minnormal, (((((|s|*|s|)*|s|)*E(R1,R2,R3))`
`+E(T1,T2,T3))+|measured|)+|target|))`.

The pass bound remains `256*gamma(k)*S+256*minnormal`; normalized error is
`absolute_error/S`. These formulae are scoped to the five registered
similarity transforms. They deliberately expose large-translation cancellation
instead of hiding it behind a unit-valued absolute floor. No rounded display
value participates in a gate.

Metamorphic rank/nullity and topology must agree exactly, and both rank
diagnostics must be unambiguous before a spectrum comparison is admissible.
Sort singular values descending and compare every independently resolved
nonzero value through the common exact rank using
`abs(s1[i]-s2[i])/max(s1[i],s2[i],1)`. The maximum resolved-spectrum delta and
the normalized-residual delta must each be at most
`16384*max(m,n)*epsilon64` after the declared scale transformation. The
numerical null tail is not used as a magnitude metric; its invariance remains
mandatory through exact rank/nullity agreement and the complete nullspace
gates. No resolved singular value may be dropped.

Every registered base/variant/candidate pair remains in invariance evidence if
a build is unavailable. Comparable analyzed builds use numerical metrics.
Unavailable pairs use `NA` metrics and may pass transformation parity only
when the complete closed failure tuple (status, stage, reason, witness
row/column/value/bits/class) matches exactly. Mandatory generic
B/C/triggered-D unavailability still fails the overall invariance/build gate;
status parity never converts it into a viable representation.

Packet permutation is an actual rerun, not a producer equality flag. For each
configuration, sort packet IDs by SHA-256 digest bytes of the exact UTF-8 ASCII
preimage `260828|packet_permutation|configuration_id|packet_id`, with packet ID
as the tie break. If that order is accidentally canonical and `N>1`, rotate it
left once. For C/D, likewise sort retained relation IDs by SHA-256 digest bytes
of `260828|relation_permutation|configuration_id|candidate|relation_id`, with
relation ID as the tie break, and rotate left once if an order with more than
one relation remains canonical. B records no relation order.

Rebuild every built B/C/D operator from packets supplied in the non-identity
packet order. Export the alternate operator in an order-sensitive raw layout:
B row blocks and every column block follow packet order; C/D rows follow
relation order and columns follow packet order. Each raw index carries its
semantic packet/relation/component mapping. Bind both the complete raw dense
row-major binary64 payload and all nonzero raw entries before restoring
semantic order for the canonical comparison. The validator derives both
orders, reconstructs the raw layout and hashes, and then canonicalizes it
independently. Canonical bytes must match exactly. A copied canonical primary
matrix, a multi-packet identity control, or a multi-relation identity control
is invalid. The frozen enum is
`sha256_packet_relation_permutation_v2`; raw grouped and dense domains are
`MLS-MECHANICAL-OBSERVABILITY-PERMUTATION-OPERATOR-v2` and
`MLS-MECHANICAL-OBSERVABILITY-RAW-PERMUTED-OPERATOR-v2`.

Candidate-A `S`-null acceptance and derivative visibility reuse the sealed
Projection Exactness + Nullspace formulas. The negative control passes this
lab only when its emitted null basis is nonempty and **every** emitted `S_A`
null mode passes the sampling residual gate and has a symmetric `D_A` image
exceeding `max(1e-10 1/s,10^4*roundoff_bound)`. One passing mode can never hide
another mode's failed residual or visibility contract, and every registered A
phase must pass the same aggregate.

## 9. Independent exact and high-precision checks

The Python oracle is standard-library-only and shares no C++ solver code. It
uses `Fraction` RREF for the registered rational B/C/D controls, exact rational
proper rotations, and exact ranks/nullities/augmented rigid-span comparisons.
It emits a canonical fixture and result hash.

The independent bundle validator rebuilds neighbor eligibility, WLS moments,
explicit rigidity/volume rows, affine targets, rigid generators, and selected
Fraction or 100-decimal-digit ranks from exported packet/topology tables. It
does not accept a C++ rank or decision as a premise. Binary64 and high-
precision findings are labeled numerical, never certified.

## 10. Decision order

1. Malformed state/topology, failed negative control, rigid-motion image
   failure, incomplete basis, ambiguous decisive rank, independent mismatch,
   or nondeterminism:
   `stop_inconclusive_or_implementation_failure`.

For each decision-driving B/C/D operator, the decisive-rank aggregate requires
the analyzed/unambiguous disposition, complete accepted kernel basis, rigid
containment, registered aggregate null/rigid/non-rigid/orthogonality residuals,
and every emitted complete-kernel/non-rigid per-mode residual/projection gate.
Independent exact-reference agreement is also part of this aggregate as well
as its separately reported gate. Diagnostic non-decision B/D rows remain
exported without driving the aggregate.
2. If B has any resolved non-rigid mode on a B-eligible ordinary 3D bulk row,
   record `reject_averaged_single_gradient_packet_kinematics`.
3. If C has only the realized rigid kernel across every
   `generic_solid_gate=true` row, record
   `retain_central_relational_representation_for_research`; do not run D as a
   selectable candidate.
4. If an eligible C row has a non-rigid mode, run the already frozen D operator
   on every `generic_solid_gate=true` configuration in the complete matrix. If
   D removes every ordinary-3D mode across that complete generic inventory, record
   `retain_volume_enriched_relational_representation_for_research` and exactly
   which tuples were necessary.
5. If D is triggered and an ordinary eligible row still has a non-rigid mode,
   decide `stop_reconsider_packet_abstraction`.

Every outcome is **NO PROMOTION** and ends the lab. B failure does not prevent
the independent C/D diagnosis. Intentionally flexible controls cannot cause a
solid representation rejection by themselves. The scientific B reducer uses
only rows that are simultaneously built, `b_rank_eligible=true`,
`generic_solid_gate=true`, and `decision_driving=true`; all other B rows remain
in the evidence as controls. Candidate D uses the same generic-solid-only
`decision_driving` rule: non-generic and exact enriched D rows are retained as
diagnostics but do not enter the raw-export, rank, affine, finite, or scientific
decision reducers. Candidate C remains decision-driving for every registered
attempted C operator because it is the primary relational representation under
test, including its deliberately flexible validation controls.

## 11. Evidence tables and sealing gate

The deterministic bundle contains:

- `configurations.csv`, `packets.csv`, and checkpoint/topology digests;
- `neighbor_pairs.csv` with brute-force/lookup agreement;
- `relations.csv` for every explicit edge and volume tuple;
- `operator_status.csv` and selected raw `operator_entries.csv`;
- `permutation_controls.csv` and full alternate `permutation_entries.csv`;
- `moment_diagnostics.csv`;
- `affine_objectivity.csv` and `invariance.csv`;
- `rigid_basis.csv`, `rank_status.csv`, `nullspace_modes.csv`, and
  `nullspace_metrics.csv`;
- `grid_gauge.csv` for A;
- `exact_reference.csv`, `summary.json`, and `manifest.json`.

Every table has a frozen schema and deterministic lexicographic order. Raw
operators must be exported for every exact/high-precision or decision-driving
row; an unexported row has `operator_payload_sha256=NA` and no stray entries.
There is no digest for an empty unexported group. Any decision-driving
unexported B/C/D row, including a generic B local-moment failure, clears the
raw-decision gate and forces the implementation stop even when its closed
failure witness is otherwise valid.
Attempted A/C/D construction or row-normalization failure is retained using
the closed failure fields in the wire contract. A finite pre-normalization
operator remains completely exported when representable; rank, affine/gauge,
and promotion claims are suppressed. B local-moment failures retain the full
moment witness and no fabricated partial operator. Successful, not-triggered,
local-moment, row-normalization, and nonfinite-cell status tuples are closed;
unsupported failures make the bundle invalid.
For each configuration, checkpoint evidence contains the exact closed sequence
`authoritative_before`, `round_trip_reserialized`, and `after_diagnostics`.
Every payload must be structurally valid and canonically reserializable. A
byte-valid round-trip or read-only mismatch is retained as a failed gate and
forces the inconclusive/implementation-failure stop; it is not discarded or
rewritten into producer success.
The exact headers, unavailable-value convention, summary enums, manifest
inventory, and deletion-hash byte preimage are frozen in
`mechanical-observability-evidence-schema.md` before the final producer run.

Release review uses the canonical
`mls.mechanical-observability.validator-findings.v1` artifact and the v3 outer
seal contracts frozen in that schema document. The findings bind both inner
manifest pre-hashes, exact per-path byte mismatches, producer summary claims,
independently derived gates and decision, the exact validator-byte SHA-256,
and their own before-hash-field preimage. The outer manifest and metadata both
bind the same fresh-pinned-replay outcome plus the captured findings and
validator-log byte hashes. Captured Git, GitHub/CI, command, tool, and local
result metadata remains explicitly unauthenticated by the offline integrity
seal.

There are two release routes. `deterministic_success` requires byte-identical
full bundles, no claim mismatch, every independently derived gate passing, and
one of the two retained-research-direction decisions. All other structurally
valid results use `preserved_negative`: this includes a byte-identical failed-
gate STOP, a conclusive `stop_reconsider_packet_abstraction`, or a fully
enumerated two-run divergence whose independently valid bundles are quarantined
as inconclusive STOP/no-promotion. Malformed evidence, incomplete mismatch or
claim inventories, an incorrect validator pin, or structurally invalid
divergence is rejected rather than preserved.

A well-formed producer basis-construction failure that the independent
reconstruction successfully resolves is an implementation/oracle disagreement:
`independent_basis_agreement=false` and
`first.independent_basis_agreement` and/or
`second.independent_basis_agreement` enters the closed claim-mismatch list,
`producer_claims_consistent=false`, and the decision is
`stop_inconclusive_or_implementation_failure`. The independent basis is not
substituted into the producer record. If the independent reconstruction also
fails in agreement with the producer's valid failure, the oracle-agreement
gate may be true, but the incomplete producer basis still fails the decisive-
rank gate. Any malformed failure stage/reason, pivot trace, nullable cell, raw
generator, or suppressed basis inventory remains INVALID.

The rank wire uses only three closed status/failure combinations:
`analyzed` with `NA,NA`; `ambiguous` with
`rank_estimation,ambiguity_band_overlap`; and `numerical_failure` with
`basis_construction` plus a closed basis-failure reason. In particular,
`analyzed` plus a basis-construction failure is malformed rather than a
preservable negative.

The deterministic-success target requires two byte-identical full producers.
A structurally valid divergent pair may instead be sealed only through the
preserved-negative inconclusive STOP route defined above. Both routes also
require a clean warnings-as-errors build; all C++ tests; canonical checkpoint
round-trip/read-only hashes; exact oracle and validator mutation tests; Linux
GCC, Linux Clang, Windows/MSVC, Python, and pinned Lean CI; `lake --wfail
build`; zero proof placeholders or project axioms; and `#print axioms`
coverage for every exported theorem. Preserve all failed runs and publish the
immutable bundle. Stop without starting a mechanics solver or material law.

The producer's `--smoke` mode is validation-only and permanently
promotion-ineligible. Its frozen three-configuration subset contains the
filament high-radius original, its registered translation, and the enriched
planar-square exact control. This compact positive fixture exercises the
Candidate-A gauge, an actual metamorphic comparison, and built-D/non-rigid
quotient paths. The registered filament rotation remains mandatory in the
59-configuration full matrix and is intentionally not suppressed or
reinterpreted by the smoke fixture.

The closed diagnostic command
`--a-pair-failure-fixture {sampling,derivative} --output DIR` uses the same
three-configuration subset and is permanently provisional, incomplete, and
unsealable. It injects exactly one all-zero finite pre-normalization operator
at `base.filament.r205.original.A.p000.S` or `.D`, respectively, so both
one-sided Candidate-A build failures can be validated end to end. The partner
operator remains built/raw, all other operators remain ordinary smoke output,
and the fixture can support only validator regression—not a scientific
candidate finding, retained direction, or promotion.
