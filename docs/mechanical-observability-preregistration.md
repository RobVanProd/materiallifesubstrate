# Mechanical Observability Lab preregistration

**Frozen before final sweep:** 2026-08-29 on branch
`mechanical-observability-lab`.  
**Accepted parent:** `2e175396ff30faea8a4d96d5a0336ab9ba042f12`.  
**Seed:** `260828` for rational jitter, relation deletion, mutation order, and
evidence provenance.

No candidate, configuration, tolerance, rank rule, or decision rule below may
change after the final full producer is run. Exploratory output is marked
dirty/provisional and cannot be sealed.

## 1. Frozen candidates

- **A — frozen quadratic-grid control.** Use the accepted tensor-product
  quadratic B-spline sampling and analytic derivative unchanged. Report
  `S_A`, `D_A`, complete accepted sampling-null modes, and the quotient test
  `ker(S_A) subset ker(D_A)`. Never construct a grid lift.
- **B — packet WLS gradient.** Use the exact cutoff and weight
  `w=(1-r^2/H^2)^2` from the contract, sorted Euclidean packet IDs, and
  `G=B M^-1`. Its observability operator is `vec(sym G)`.
- **C — central-distance graph.** Use explicit canonical simple edges and the
  actual rigidity matrix. The graph is physical input.
- **D — objective volume enrichment.** This type is frozen now but is included
  in the final candidate sweep only if a `generic_solid_gate=true` C row has a
  resolved non-rigid null mode. D concatenates C with at most one explicit
  ordered volume relation per center packet.

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
`square-plus-diagonal=5/7`. The volume-enriched square expectation is tested,
not assumed; if its exact rank is not `6`, the counterexample is preserved and
the preregistration records the actual oracle result before any full sweep.

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
or promote. Rank is always called a numerical threshold estimate. Emit every
free-column null basis vector and the full pivot/permutation trace.

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

## 8. Affine, objectivity, and invariance tolerances

For a linear observable target `y`, use

\[
\eta=\frac{\lVert Rv-y\rVert_2}
{\max(\lVert R\rVert_F\lVert v\rVert_2+\lVert y\rVert_2,
\mathrm{minnormal})}
\]

with threshold `4096*max(m,n)*epsilon64`.

For finite length/volume operations let
`gamma(k)=k epsilon64/(1-k epsilon64)`. Each row records its actual operation
count and operand-magnitude scale; the pass bound is `256 gamma(k)` times that
scale plus `256*minnormal`. No rounded display value participates in a gate.

Metamorphic rank/nullity and topology must agree exactly. Normalized residuals
and singular values agree within `16384*max(m,n)*epsilon64` after the declared
scale transformation. Packet/relation permutation must reproduce canonical
evidence byte-for-byte after sorting.

Candidate-A `S`-null acceptance and derivative visibility reuse the sealed
Projection Exactness + Nullspace formulas. The negative control passes this
lab only by reproducing at least one accepted `S_A` null mode whose symmetric
`D_A` image exceeds `max(1e-10 1/s,10^4*roundoff_bound)`.

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
2. If B has any resolved non-rigid mode on a B-eligible ordinary 3D bulk row,
   record `reject_averaged_single_gradient_packet_kinematics`.
3. If C has only the realized rigid kernel across every
   `generic_solid_gate=true` row, record
   `retain_central_relational_representation_for_research`; do not run D as a
   selectable candidate.
4. If an eligible C row has a non-rigid mode, run the already frozen D operator
   on the complete matrix. If D removes every such ordinary-3D mode, record
   `retain_volume_enriched_relational_representation_for_research` and exactly
   which tuples were necessary.
5. If D is triggered and an ordinary eligible row still has a non-rigid mode,
   decide `stop_reconsider_packet_abstraction`.

Every outcome is **NO PROMOTION** and ends the lab. B failure does not prevent
the independent C/D diagnosis. Intentionally flexible controls cannot cause a
solid representation rejection by themselves.

## 11. Evidence tables and sealing gate

The deterministic bundle contains:

- `configurations.csv`, `packets.csv`, and checkpoint/topology digests;
- `neighbor_pairs.csv` with brute-force/lookup agreement;
- `relations.csv` for every explicit edge and volume tuple;
- `operator_status.csv` and selected raw `operator_entries.csv`;
- `moment_diagnostics.csv`;
- `affine_objectivity.csv` and `invariance.csv`;
- `rigid_basis.csv`, `rank_status.csv`, `nullspace_modes.csv`, and
  `nullspace_metrics.csv`;
- `grid_gauge.csv` for A;
- `exact_reference.csv`, `summary.json`, and `manifest.json`.

Every table has a frozen schema and deterministic lexicographic order. Raw
operators must be exported for every exact/high-precision or decision-driving
row; unexported rows carry an explicit digest and no stray entries.

Before sealing, require two byte-identical full producers; a clean warnings-
as-errors build; all C++ tests; canonical checkpoint round-trip/read-only
hashes; exact oracle and validator mutation tests; Linux GCC, Linux Clang,
Windows/MSVC, Python, and pinned Lean CI; `lake --wfail build`; zero proof
placeholders or project axioms; and `#print axioms` coverage for every exported
theorem. Preserve all failed runs and publish the immutable bundle. Stop
without starting a mechanics solver or material law.
