# Occupied Matter Geometry Foundation Lab — preregistration

Parent: `639ab635769a7d244aa255281acbabad78c27057`.
Branch: `occupied-matter-geometry-foundation-lab`.
Parent evidence tag: `world-material-phase-unification-lab-evidence-v1`.
Parent tag object: `c04d9c35371e2d08810d131dc8663bfc3dd2902d`.
Parent archive: 1045668581 bytes; SHA-256
`60ab3b7ae748b8108747b586933cd74ae0e1cb44ba874d003735a6127bf4d261`.

**NO_PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**

Commit and push this protocol before candidate implementation, formal proof
implementation, or geometry measurements. This is a geometry/architecture lab,
not contact-force implementation. No contact solver or physical state migration
is selected here. Stop locally sealed for independent review; publication and
main merge require separate authorization.

## 1. Question and immutable boundary

Can generic material state define an objective, deterministic, refinement-
consistent occupied domain, separation and normal without semantic objects,
renderer geometry, numerical-support-as-matter, or hidden causal state?

Working ontology: packets are Lagrangian samples/parcels of a continuous material
domain. Same-volume spheres are an adversarial alternative, not the assumed
meaning of a packet. No `collision_radius` is added to MaterialPhasePacket.

Freeze all existing production/research mechanics and ownership sources:
B96 arithmetic/wire, Path-B, H_force, topology, reference geometry, KDK/Euler
control order, units, safe domain r/l0 >= 2^-24, material accounting, identity
binding, heat controls, checkpoint formats and scientific event streams.
New geometry code may only read immutable snapshots. It cannot return forces,
impulses, clock changes, state corrections or ledger entries. Geometry sidecars
are experimental inputs, never inserted into an accepted World checkpoint.

The accepted 40-case material/World corpus must be rerun with geometry observation
enabled, disabled and cache rebuilding. Require complete scientific stream and
material checkpoint byte identity, not endpoint/tolerance parity. The inherited
kernel/ownership files must remain byte-identical. Exact inventories remain
exact; approximate B96 mechanics is not relabeled exact conservation.

## 2. Identifiability comes before reconstruction

Audit the accepted packet, chemistry catalog, relation model and snapshot fields.
Distinguish absent state from an unavailable numerical algorithm. Exhibit two
different occupied domains compatible with the same accepted fields and relations.
Also exhibit equal-volume, equal-centroid domains with different boundaries: a
scalar volume alone need not determine shape, adjacency or a normal.

The exact logical claim is non-uniqueness over a declared class of possible
domains, not impossibility of selecting a convention. A chosen reconstruction
convention is a new geometry hypothesis, not recovery of already specified
physics. No theorem may assume that a packet's mass determines volume without
a specific-volume law.

Record `current_state_does_not_determine_occupied_geometry` when demonstrated;
this is an architecture finding and does not stop the candidate comparison.

## 3. Separate information tiers

- I0: exact accepted packet/relational state, with no volume/boundary sidecar.
- I1: I0 plus explicit per-parcel reference-volume weights and reference sample
  positions, with declared total volume. This is additional hypothetical physical
  input, not an existing chemistry property.
- I2: I1 plus oriented material-domain cells, shared vertex/facet incidence and
  boundary connectivity. This is additional domain information. It is not an
  object type, body label, collision mesh from rendering, or interpolation support.

Every row states its information tier. Removing sidecar information must either
produce the registered stateless construction or reject; it may not secretly
load the analytic fixture. A successful I2 construction cannot be advertised as
an I0 reconstruction.

Reference volume weights are an observer-only quadrature inventory. For each
physical fixture, children partition their parent's weight exactly; total mass,
material amount and reference volume remain fixed across resolutions. These are
not runtime splits of exact integer constituents. No fractional chemistry
inventory, equation of state or density law is introduced. Analytical constants
such as pi are enclosed independently; any finite encoding and its error must
be carried in the oracle, never called an exact irrational volume.

## 4. Candidates and fixed construction rules

**A — same-volume pinball control (I1).** Each sample at its material centroid
occupies a closed ball of volume V_i, radius (3 V_i / (4 pi))^(1/3). Occupancy is
the union, not the sum of sphere volumes. Overlaps and voids count. Radii are
recomputed from V_i at every spatial level; no packing, displacement, radius
inflation, shape-specific calibration or contact-stiffness parameter is allowed.
Measure internal holes as boundary, not just the outer silhouette. This candidate
tests this registered sampling/refinement construction, not every DEM ontology.

**B — explicit conforming material parcels (I2).** Occupancy is the union of
oriented tetrahedral cells with shared vertex/facet incidence. A material complex
is a maximal connected component of B's own tetrahedral incidence graph, with
adjacency only through a shared full triangular facet. Shared vertices or edges
alone do not join complexes. No semantic object/body label supplies this graph.
Within each complex, reject inverted/zero-volume cells, duplicate cells, invalid
incidence, gaps in required conforming incidence, and positive-volume interior
overlap between distinct cells at every registered time. Refine shared facets
conformingly; never let two copies of a shared vertex evolve independently.
Candidate input contains only vertices, cells, weights and stable IDs, not
analytic shape names or object grouping.

Component boundary facets have exactly one incident cell; internal facets cancel.
Such a component boundary facet is not necessarily an exterior boundary of the
occupied union: the cross-complex collision rule below remains mandatory.

### Pre-data validity-scope amendment: prescribed cross-complex collision

This amendment preserves the exact input-gate audit introduced at
`03e0d3971643541d2b9459ad767df07aec7a2df4`
and the subsequent formatting-only head
`1942e62a5d9b18a0b40aa1a110a77a22db9eedf6`. It is authorized and frozen before
any A/B/C candidate evaluation or complete input root seal. It does not erase
or reinterpret that audit as a candidate result.

The former unqualified global non-overlap rule conflicted with mandatory
fixture 5: the prescribed two-sphere motion continues through time 2, after
analytical first contact at time 1. The preserved level-0 exact witness places
one rational point strictly inside cells 60 and 83 from different complexes at
time 2. Each individual complex remains valid under its rigid translation.

Overlap between different material complexes is not automatically a mesh-input
validity failure. Specifically for the registered moving two-sphere collision
benchmark (including its registered transforms and refinements):

- For `t < 1`, the distinct complexes must remain disjoint.
- At `t = 1`, touching is the analytical contact condition.
- For `t > 1`, cross-complex penetration is intentional prescribed geometry and
  remains in the benchmark through `t = 2`.

These analytical conditions do not replace certification for B's actual straight
tetrahedra, C's level set, or A's sphere union. Each candidate still answers its
registered geometry/CCD questions against the independent oracle. This exception
does not permit arbitrary overlapping components in unrelated static fixtures,
nor does it relax any within-complex validity requirement.

**B occupancy remains the union of all tetrahedral cells.** Overlapping volume
between complexes must not be double-counted. Surfaces lying inside the occupied
union are not exterior boundary merely because they are boundary facets of one
component. Component decomposition is available for validity and intersection
reasoning, not as permission to replace union volume by a sum or union boundary
by an unfiltered concatenation. Components may not be independently evaluated
in a way that drops cross-complex interactions from any required observable.

Retain every registered post-contact volume, boundary, normal, separation,
closest-set, overlap-classification, transform/refinement/covariance and swept
query. Zero separation alone does not distinguish touching from penetration.
Do not clip the trajectory, stop at first contact, delete post-contact rows or
relabel them expected-invalid controls. The graph is derived from frozen
incidence; geometric proximity or penetration does not create new incidence.

This is an offline prescribed collision benchmark, not a physical contact
simulation or permission for authoritative MLS matter to interpenetrate. No
contact forces, state changes, candidate arithmetic changes, new labels, changed
fixtures, levels, query inventory, thresholds, resource ceilings, information
tiers or dispositions are introduced. Candidate C's predeclared finest
cube/slab resource-inconclusive rows are unchanged. All other preregistration
and addendum requirements remain in force. **NO_PROMOTION remains.**

Box/slab/U-domain fixtures use conforming tetrahedral subdivisions. Spherical
fixtures use the conforming volumetric angular-and-radial refinement specified
by the pre-data amendment below, not a surface-only fan to one central vertex.
Analytical sphere knowledge belongs only to fixture generation/oracle, not to
B's queries. Curved boundary approximation error remains measured; do not replace
faceted geometry by the exact sphere during evaluation. Reference weights
partition the intended material amount; polyhedral occupied volume is measured
independently and need not equal those weights at finite resolution.

### Pre-data spherical-refinement amendment

Preserve original preregistration `5ac51c754a12e6cccb6e23b48e291ed2f1c2b1b7`
and resource amendment `f94f449d03ddd45a2501a4fca70587c4ec81fdb6` in history.
The original spherical construction subdivided only the octahedral surface and
joined every resulting triangle to the centre. For each tetrahedron [0,a,b,c]
with unit surface vertices, a centre-to-surface edge remains exactly 1 m, hence
Delta_k >= 1 m at every refinement. Its centroid (a+b+c)/4 approaches (3/4)u as
the angular triangle shrinks toward u. Thus the centroid samples concentrate on
a shell rather than refining the interior. Since L is fixed, h=sqrt(Delta L)
cannot tend to zero. This is an input-refinement defect, not an observed failure
of A, B or C. It was identified before the addendum, implementation, formal proofs
or candidate measurements; no candidate output has been computed.

Supersede only that spherical construction. Retain five levels k=0..4, the same
physical unit sphere (and its registered copies/motions), fixed total reference
volume/material amount, A/B/C definitions, information tiers, h=sqrt(Delta L),
all scientific/oracle/resource budgets and all dispositions.

Constrain the replacement before data as follows:

1. Start from the reference octahedron |q_x|+|q_y|+|q_z| <= 1, divided into its
   eight centre-to-face reference tetrahedra. At depth d=k+1, use a conforming,
   nested dyadic volumetric refinement: all six edge midpoints, four corner
   tetrahedra and a consistent four-tetrahedron split of the central octahedron
   give eight children per parent. Shared reference vertices/faces are unique.
   The addendum must freeze a globally compatible, shape-regular central split
   rule and orientation/ID convention; no choice may depend on candidate results.
   Boundary triangles retain the registered four-way angular subdivision.
2. Map every reference vertex, including interior vertices, by the same radial
   fixture map F(0)=0 and F(q)=||q||_1 q/||q||_2 for q != 0. The reference
   octahedron maps onto the unit ball; boundary vertices lie on the unit sphere.
   Interior radial coordinates refine along with the angular coordinates.
   B receives straight tetrahedra joining these mapped vertices, not an oracle
   evaluator for F. A/C receive the centroids of those same straight tetrahedra
   and their declared reference-volume weights. Neither receives oracle labels,
   analytic normals or hidden corrections during candidate evaluation.
3. Require an a-priori bound max_T diam(T_ref,d) <= C_ref 2^-d with an explicit
   level-independent C_ref justified for the frozen split rule. The map has the
   Lipschitz bound ||F(q)-F(p)||_2 <= 3 sqrt(3) ||q-p||_2. Consequently mapped
   tetrahedral diameter is bounded by 3 sqrt(3) C_ref 2^-d in exact geometry.
   This construction-level bound, not five measured values, must establish
   shrinking radial/angular extent and interior-filling samples. A valid mesh
   and vanishing diameter do not by themselves prove the reconstruction gates.
4. Curved reference regions F(T_ref) partition the intended ball hierarchically;
   straight tetrahedra are its discrete geometry approximation, not identically
   those curved regions. Reference-volume weights must represent the same fixed
   physical volume measure, not equal weights justified solely by equal reference
   tetrahedron counts. The addendum must freeze their independent integration/
   enclosure and canonical allocation rule. Positive child weights partition
   each parent weight exactly in the stored encoding; the total encoded volume
   is fixed across levels. Account for integration/encoding deficits explicitly.
   No per-level rescaling chosen from candidate volume error is permitted.
5. Preserve conforming incidence under the mapped straight-cell construction.
   Invalid orientation, degeneracy, overlaps or gaps cannot be fixed by moving
   samples after evaluation. The addendum must specify independent inventory
   validity checks, not assume that a valid curved partition proves every
   straight-cell property. Failure is an inventory gate, not a candidate result.
6. The exact tessellation, split/orientation rule, encoding and primitive counts
   must be frozen in the addendum before measurements. For the eight-child rule,
   tetrahedron counts per unit sphere are 8*8^(k+1): 64, 512, 4096, 32768,
   262144. Report samples, shared vertices, facets and incidence counts separately,
   including multiple-sphere fixtures. Recheck serialized size, memory layout,
   loading time and the deterministic work schedule against the unchanged
   2 GiB / 30-minute / 8 GiB ceilings and 2^22 certification-work cap. Input
   counts alone do not establish that runtime certification fits those caps.
7. At every spherical level, independently compute/enclose maximum tetrahedral
   diameter and radial centroid-support range from the frozen candidate input
   bytes. Check them against the amended construction and declared encoding
   bounds; reject a mismatched fixture inventory, including accidental restoration
   of the centre-fan sequence. Record finite coordinate/volume encoding floors
   separately from the exact geometric refinement limit. No hidden precision
   increase or measured-Delta substitution may rescue a failed inventory.

This is a pre-data protocol correction only. It adds no physical domain state
to World, density law, mechanics transition, contact force, proof implementation
or geometry result. The addendum is still pending and the data gate remains shut.

**C — stateless smooth reconstruction (I1).** From exactly the same centroid/
volume samples as A, use

    f_h(x) = sum_i V_i exp(-|x-x_i|^2/(2 h^2)) / ((2 pi)^(3/2) h^3),
    occupied = { x : f_h(x) >= 1/2 },
    h = sqrt(Delta L),  L = V_total^(1/3).

Delta is the maximum diameter of the registered reference parcels, supplied as
a resolution descriptor, not fitted to results. All samples contribute: no
unbounded unaccounted Gaussian truncation or fixed-neighbor shortcut. Bandwidth
shrinks while h/Delta grows. A vanishing gradient is ambiguous; do not invent a
normal. Finite-domain search/tail truncation requires an outward bound. The SPH
prior art motivates this scaling distinction but does not prove C converges.
No threshold, width or boundary correction may be tuned per shape or level.

A/C receive no cell boundaries; B receives them explicitly. Candidate code may
not read oracle values, true normals, shape names or semantic connected-body IDs.
Deterministic query fixtures may designate material subsets for comparison;
those labels cannot enter occupancy reconstruction or force eligibility.

## 5. Fixed corpus and refinement

Use metres and seconds. Five nested spatial levels k=0..4. For box-type fixtures,
use initial cell edge 1/4 m and halve it each level. For spherical volumes, use
the amended volumetric octahedral refinement depths 1..5, whose surface retains
four-way angular subdivision. Record actual maximum cell diameter Delta and
sample count; do not pretend the constructions have identical counts.

Physical fixtures:

1. Cube [-1,1]^3.
2. Finite slab [-2,2] x [-2,2] x [-1/4,1/4].
3. Unit sphere centred at zero.
4. Two unit spheres centred at (-3/2,0,0) and (3/2,0,0).
5. The same pair moving with velocities (+1/2,0,0), (-1/2,0,0)
   over [0,2]; analytical first contact is t=1.
6. Unit sphere centre (0,0,2) moving with velocity (0,0,-1) toward
   analytical plane z=0 over [0,2]; first contact t=1. The plane is an
   explicitly external oracle fixture, not a named physical World object.
7. Self-near U-domain: union of closed boxes
   [-1,1] x [-1,-3/4] x [-1/4,1/4],
   [-1,-3/4] x [-3/4,1] x [-1/4,1/4], and
   [3/4,1] x [-3/4,1] x [-1/4,1/4]. Shared faces are internal.
   Query the facing arm surfaces; do not exclude all pairs in one connected
   component. Include a prescribed affine arm-approach geometry test separately
   from rigid motion, and reject any invalid parcel map instead of hiding overlap.

Repeat static fixtures and moving pairs under translation (3,-2,5), all proper
signed-axis permutations, and the proper rational rotation about z with cos=3/5,
sin=4/5. Apply a further rational proper rotation about x with the same cosine/
sine as a non-axis-aligned control. Geometry input transformations are exact
rational observer operations; no claim of exact arbitrary-rotation B96 dynamics.
Reverse/shuffle input order using fixed seed 260908; bijectively relabel IDs.
Apply uniform scale factors 1/2 and 2 with the dimensionally corresponding volume
and velocity changes. Repeat common velocity boost (1/4,-1/2,1/8).

The exact U arm-approach map, serialization schema, finite query net and certified
search partition must be fixed in a pre-data protocol addendum before any
candidate measurements. The addendum may instantiate these constructions but
may not change candidates, fixtures, levels, budgets or decisions. No final
trajectory/geometry data before that executable input inventory is frozen.

## 6. Quantities, bounds and gates

Export occupied union volume, material-reference volume, symmetric boundary
Hausdorff distance, smooth-boundary normal error, nonnegative separation distance,
overlap/first-contact classification, closest-point set and first-contact time/
location. Separation zero alone does not distinguish touching from penetration;
report them separately. Do not present a generic signed penetration depth without
a definition for nonconvex/interlocking sets.

All errors are against an independent analytical/certified geometry oracle, not
another candidate or the fine-level candidate. Report lower and upper bounds.
Sampling maxima are diagnostics, not whole-boundary Hausdorff certificates.
Use outward subdivision/covering bounds for global quantities; exact polyhedral
predicates where available. If a complete bound is unavailable within budget,
that gate is inconclusive. Preserve ambiguous zero/tangency cases explicitly.

Normalize lengths/gaps by fixture L=V_total^(1/3), volume by V_total and time by
the registered horizon. The finest-level upper-error budgets are: volume 0.02,
Hausdorff 0.05, smooth normal angle 0.10 rad, gap 0.05, contact time 0.05 and
contact location 0.05. These are coarse foundation screening budgets, not future
contact-force tolerances. Same-world refinement additionally requires the finest
upper error <= half the coarsest lower error wherever the coarsest error is
resolved above the oracle floor. Exact constructions may instead remain inside
the floor on every level. Report all intermediate errors/orders; no requirement
that every adjacent realized error follow an arbitrary ratio.

Oracle widths must be <= 1/100 of the relevant budget. Unresolved classification
is not a pass. Positive/negative controls must distinguish deliberately changed
gap, volume and normal by at least ten oracle widths. Frozen precision: 256-bit
candidate observer scratch; separately implemented 512-bit directed oracle or
exact rational predicates. These are not B96 state changes. No precision increase
after candidate data. Exact transformations/permutations require canonical result
equivalence; numeric enclosures must overlap the exact transformed result and
fit the oracle-width allowance. Corners/edges report normal cones or a nonunique
flag. Smooth-normal metrics exclude true corners using explicit oracle patches,
never a normal chosen to make error small. Multiple closest pairs are set-valued.

Pinball volume must be union volume. In particular, comparing sum_i V_i with
V_total cannot certify occupied volume. Parcel overlap/gap checks concern full
cells, not only their vertices. Smooth reconstruction must certify topology/
boundary search coverage sufficiently for each claimed global metric.

Resource ceilings per candidate/fixture/level: 2 GiB process memory, 30 minutes,
2^22 certification/search work units; 8 GiB emitted scientific evidence across
the new geometry corpus. The pre-data amendment below defines the separate
input-inventory and certification-work counters. Exceedance is inconclusive,
never a geometry rejection. Log counts deterministically; keep wall time/RSS
outside twin scientific hashes. No adaptive resource increase after data.

### Pre-data resource-counter amendment

This amendment preserves the original protocol at
`5ac51c754a12e6cccb6e23b48e291ed2f1c2b1b7`. Under its conservative reading,
Candidate B's input tetrahedra consume the cell/work ceiling. At finest spacing
1/64 m, both the cube and slab contain 2,097,152 Cartesian cells; six tetrahedra
per cell require 12,582,912 input parcels, exceeding the original 4,194,304 cap
before certification. Unamended, those rows would be resource-inconclusive,
not evidence against the geometry hypothesis.

The conflict was identified by exact inventory arithmetic before implementation,
formal proofs, candidate measurements, or freezing the required addendum. No
candidate output has been computed. This is an explicit pre-data correction of
a protocol design defect, not a reinterpretation based on observed performance.

Apply these two counters equally to A, B and C:

1. **Frozen input inventory.** Candidate input means the exact canonical bytes
   frozen and hashed by the pre-data addendum. Required samples, vertices,
   tetrahedral parcels, facets and incidence records contained in those bytes
   are input primitives, not certification-work units. Report their complete
   counts separately, by primitive type, for every candidate/fixture/level.
   Input primitives remain subject without exception to the 2 GiB process-memory,
   30-minute wall-time and 8 GiB evidence-size ceilings. Loading, decoding and
   canonical-format validation do not consume the certification-work counter;
   their memory and elapsed time still count. Encoding must not serve as an
   instruction to generate uncounted adaptive geometry.
2. **Runtime certification/search work.** The unchanged 2^22 ceiling counts
   work generated after loading the frozen input: adaptive subdivision regions,
   covering cells, intersection/pair predicates, root-isolation boxes and
   equivalent certification work units. Anything generated after those bytes
   are loaded counts as runtime/certification work unless explicitly classified
   otherwise in this amendment. Merely deriving data deterministically from
   input does not exempt it. Candidate-generated adaptive geometry, geometric
   validity tests and runtime refinements cannot be relabeled input. The
   addendum must freeze a deterministic accounting schedule for equivalent
   work, without creating new exemptions or weakening the cap.

The input generator is restricted to the registered fixture constructions; it
may not execute candidate-dependent adaptation, precompute candidate answers or
move certification searches into the frozen input. Candidate-visible and
oracle-only artifacts remain physically separate. Both inventories must be
closed before any candidate output is computed.

### Pre-data proof-carrying Cartesian validity amendment

Preserve the runtime-validity escalation at
`7bb3eeaee9ec1d32e9438ed99ddce88e1cf1f373` and every earlier protocol/attempt.
This amendment is authorized before any candidate evaluation or complete input
root seal. It changes a validity trust boundary only: no physical geometry,
candidate definition, fixture, precision, query, threshold, disposition or
resource ceiling changes.

Only B's registered regular Cartesian cube/slab six-tetrahedron construction
may carry an independently verified structural validity precondition. Establish
positive orientation, disjoint interiors, complete unit-cell coverage and
conforming shared faces for the fixed template, and establish that replication
on the registered Cartesian lattice preserves these properties globally.
Prove/check preservation by the registered proper rotations, translations and
positive uniform scales. Check canonical order/ID changes without changing the
underlying incidence. This exception does not cover sphere, U, moving-complex
or arbitrary/non-template mesh validity.

The certificate must bind the exact frozen candidate-input root, numerical grid
dimensions, template version and transform, including the fully decoded stream
identities. To avoid circular hashing, the candidate-manifest digest defines
the candidate-input root; the final controller input root binds both that
manifest and the certificate. No certificate may contain or authorize use of
oracle shape labels, analytical geometry answers, query results or adaptive
geometry. Numerical lattice facts already represented by B's exact vertices
and incidence are permitted proof premises, not a new occupancy law.

An independent verifier, not the fixture generator alone, must reproduce/check
the certificate before sealing. Creation and verification are pre-data input
certification with explicit work/count receipts and the unchanged 2 GiB memory,
30-minute time and 8 GiB evidence ceilings. At runtime B may rely on this
authenticated structural validity precondition instead of redundantly checking
each tetrahedron. This narrowly supersedes the prohibition on input validation
establishing candidate validity; all other input-validation rules remain.

All actual geometry work, including union evaluation, buried-face filtering,
overlap, boundary, Hausdorff, normals, closest sets and CCD, remains charged to
the unchanged 2^22 runtime counter. This certificate supplies no precomputed
geometry answer or runtime search structure. Malformed-input mutations must
invalidate the root/certificate binding or fail registered validity controls;
there is no fallback to trusting a familiar grid name or nominal transform.

If the certificate cannot be established under these restrictions, classify
the affected B rows resource-inconclusive and stop the lab as inconclusive;
do not consume the full candidate run budget on a predetermined unselectable
inventory. **NO_PROMOTION remains.**

This amendment changes no spatial level, tetrahedralization, candidate definition,
geometry budget, oracle width, disposition or fixture. The certification-work
cap remains exactly 2^22. No other resource ceiling is raised. The data gate
remains closed until the separate pre-data addendum and its exact input inventory
have been frozen and reviewed.

## 7. Swept geometry and disposability

For sphere controls, use r(t)=r0+t v and

    Q(t)=|v|^2 t^2 + 2 (r0 dot v) t + |r0|^2 - (R1+R2)^2.

Check the minimum over the complete closed interval, including zero velocity,
initial overlap, tangency, separating motion, negative discriminant and roots
outside the interval. Sphere-plane control similarly uses the full linear gap.
Return a certified first-root interval or exact algebraic result, not a rounded
time declared exact. Candidate B/C sweeps require bounds for their actual derived
geometry; analytic sphere CCD does not certify a polyhedron/level set by proxy.

Prescribed linear motions are observer benchmark paths, not accepted new World
dynamics. For inherited KDK, the existing drift chord remains unchanged. Later
nonlinear contact trajectories need their own continuous-collision proof.

All acceleration structures derive canonically from the supplied geometry state.
Run with none, freshly rebuilt, permuted insertion, and deleted/recreated caches.
Checkpoint a geometry fixture, rebuild caches in a fresh process and require the
same complete query stream. Experimental explicit domain sidecars must roundtrip
canonically; this does not authorize persisting them in World. Any output that
depends on retained cache history is a failed architecture/control gate.

## 8. Independent validation and formal scope

Independent implementation consumes canonical coordinate/volume bit patterns or
exact numerator/denominator encodings. No human decimal re-rounding. Candidate
geometry never consumes analytic fixture labels; oracle code must not call
candidate occupancy/distance/normal predicates. Validate primitive arithmetic
first using exact rational/algebraic controls. Preserve failed implementations.

Mutations must detect: operation-support-as-radius; sum-of-sphere-volumes used
as union; changed refinement dimensions/amount; hidden radius/bandwidth tuning;
using oracle shape labels; dropped internal boundary/hole; missing/shared facet;
incorrect orientation/normal; arbitrary corner normal; endpoint-only CCD;
missed tangency; cached-state feedback; omitted domain-sidecar checkpoint data;
resource/ambiguity relabeled pass; changed inherited mechanics bytes.

Lean proves only tractable exact statements with explicit domain assumptions:
non-uniqueness witness logic; gap symmetry; normal antisymmetry where unique;
translation and proper-rotation covariance; volume scaling and exact subdivision
additivity under disjoint-interior assumptions; swept-sphere squared quadratic
identity and interval-minimum intersection criterion. It does not prove an
empirical reconstruction converges, arbitrary mesh validity, executable MPFR
correctness, or contact dynamics. No sorry/admit/project axioms. Report dependencies.

GCC/Clang/MSVC observer/control builds, independent Python oracle/mutations and
pinned Lean/trust checks must pass on the exact final source. Deterministic twins,
closed source/input/oracle/config manifests and fresh bundled replay precede a
local seal. No old certificate may be presented as certifying new geometry.

## 9. Dispositions and interpretation

Use these exact findings/dispositions; findings may coexist:

- `current_state_does_not_determine_occupied_geometry`: established I0 ambiguity;
  expected architecture finding, continue comparison.
- `reject_discrete_packet_occupancy_on_refinement`: A has a resolved failure of
  the registered same-world construction; not rejection of all particle physics.
- `retain_continuum_material_domain_geometry_for_research`: B or C passes every
  applicable registered geometry/refinement/control gate. State its information
  tier explicitly; no implied I0 reconstruction or force-law selection.
- `explicit_material_domain_state_required_before_contact`: an information-
  nonuniqueness witness establishes missing domain data, all registered stateless
  reconstruction candidates fail resolved gates, and a declared explicit-domain
  construction demonstrates the missing information can resolve the ambiguity.
  Failure of one heuristic alone cannot establish universal necessity.
- `stop_geometry_foundation_inconclusive`: parent/oracle/platform/inventory,
  resource, ambiguity or other required gate incomplete. This blocks a positive
  selection; incomplete comparisons cannot be relabeled architectural necessity.

Report candidate statuses separately and retain all resolved negative findings
even if the overall result is inconclusive. No priority rule may turn one
candidate's resource exhaustion into a physical rejection of another.

Done means the same-world construction and missing information are explicit,
every required metric/control is resolved or honestly inconclusive, all frozen
mechanics bytes are preserved, independent/mutation/platform/formal gates have
run, and evidence is locally sealed. This remains **NO_PROMOTION**. A frictionless
contact-law experiment requires its own authorization after geometry review.

## 10. Prior-art anchors and limits

- Bardenhagen and Kober, *The Generalized Interpolation Material Point Method*
  (2004), https://doi.org/10.3970/cmes.2004.005.477.
- Sadeghirad, Brannon and Burghardt, *A convected particle domain interpolation
  technique to extend applicability of the material point method for problems
  involving massive deformations* (2011), and subsequent enriched CPDI work:
  https://upcommons.upc.edu/entities/publication/2be8ba58-2f48-4c4e-9b28-b793a2156f65.
  Finite interpolation domains motivate an audit; they do not automatically
  establish MLS physical boundaries or guarantee non-overlapping material cells.
- *The pinball contact algorithm for the material point method*,
  https://doi.org/10.1007/s40571-024-00893-x. Same-volume spheres motivate A;
  neither a radius ontology nor a refinement guarantee is inherited.
- Zhu, Hernquist and Li, *Numerical Convergence in Smoothed Particle Hydrodynamics*,
  https://arxiv.org/abs/1410.4222. Particle count, bandwidth and neighbor count
  limits must be distinguished. This is not a proof of candidate C.
- *Incremental Potential Contact*, https://ipc-sim.github.io/, and
  *Convergent Incremental Potential Contact*, https://arxiv.org/abs/2307.15908.
  Coupled contact-solver guarantees and spatial-discretization consistency are
  separate questions; no IPC guarantee is imported into KDK or this geometry lab.

Primary sources must be retrieved and their applicable assumptions recorded
before making detailed algorithm-attribution claims. Unavailable papers remain
an explicit literature-access limitation, not authority for invented equations.
