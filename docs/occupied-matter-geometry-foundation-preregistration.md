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
oriented, non-overlapping tetrahedral cells with shared vertex/facet incidence.
Boundary facets have exactly one incident cell; internal facets cancel. Reject
inverted/zero-volume cells, duplicate cells, invalid incidence and interior
overlap. Refine shared facets conformingly; never let two copies of a shared
vertex evolve independently. Candidate input contains only vertices, cells,
weights and stable IDs, not analytic shape names or object grouping.

Box/slab/U-domain fixtures use conforming tetrahedral subdivisions. Spherical
fixtures begin from an octahedral surface and recursively split each triangle
into four; newly generated surface vertices are radially projected by the fixture
generator before serialization. Join the surface to a central vertex to obtain
tetrahedral parcels. Analytical sphere knowledge belongs only to fixture
generation/oracle, not to B's queries. Curved boundary approximation error remains
measured; do not replace faceted geometry by the exact sphere during evaluation.
Reference weights partition the intended material amount; polyhedral occupied
volume is measured independently and need not equal those weights at finite
resolution.

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
use initial cell edge 1/4 m and halve it each level. For spherical surfaces, use
octahedral subdivision depths 1..5. Record actual maximum cell diameter Delta
and sample count; do not pretend the two constructions have identical counts.

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
2^22 subdivision boxes/cells or intersection predicates; 8 GiB emitted scientific
evidence across the new geometry corpus. Exceedance is inconclusive, never a
geometry rejection. Log operation counts deterministically; keep wall time/RSS
outside twin scientific hashes. No adaptive resource increase after data.

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
