# Occupied Matter Geometry Foundation — pre-data addendum

Governing source: `26ad3bab38d9a966f6cf7af42a0d3c1f1a2efdfa`.
Accepted mechanics parent: `639ab635769a7d244aa255281acbabad78c27057`.
This instantiates the amended preregistration, without changing candidates,
levels, physical fixtures, budgets, precision, information tiers or dispositions.
**NO_PROMOTION. No candidate measurements are authorized by committing this file.**

This is the normative input/verification specification, not a claim that expanded
fixture files, an input seal, numerical certificates or a scientific result
already exist. The closed materialized input manifest described in section 10
is mandatory before the first candidate evaluation. Its actual hashes must be
recorded, never replaced by the hash of this specification or of a generator.
Review of this addendum precedes data-gate authorization.

## 1. Byte contract and physical separation

Use three separate directories/process capabilities:

- `candidate/`: only numerical material samples, I2 cells where applicable,
  declared reference weights, motion coefficients, resolution descriptors and
numerical query arguments. No analytic shape names, true normals, expected
  answers, oracle patches or original construction coordinates.
- `oracle/`: analytical domain definitions, original reference construction,
  physical-volume integration witnesses, smooth/corner patch descriptions,
  expected exact-control answers and interval covering obligations.
- `control/`: manifests, byte-count tables, execution inventory and candidate-to-
  oracle query joins. The controller may join results; candidate processes may
  not read this directory or `oracle/`. Candidate and oracle logs are separate.

No candidate receives a mixed object containing hidden oracle fields. Deny
oracle paths to its process, not merely by programming convention. Candidate
working directories contain no oracle files, symlinks or inherited descriptors.
The later leakage test replaces oracle files while keeping candidate bytes fixed
and requires identical candidate outputs. Candidate code cannot invoke the
fixture generator. Shape recognition inferred from ordinary coordinates is not
an exemption for reading labels or dispatching to analytic fixture answers.

Canonical files are uncompressed binary payloads (transport compression is
non-authoritative). Integers U8/U32/U64 are unsigned little-endian; I64 is signed
two's-complement little-endian. Counts and IDs are U64, zero reserved for absent.
Large signed integers use U8 sign (0 nonnegative, 1 negative), U32 byte count,
then shortest little-endian magnitude; zero is sign=0/count=0. No leading zero
limb, negative zero, redundant padding or host-native structs. Rational Q is
`SignedBigInt numerator || U32 denominator_byte_count || denominator_bytes`.
The denominator byte count is >=1, little-endian; denominator_bytes is the
shortest little-endian magnitude of a strictly positive denominator, with no
zero most-significant byte. No denominator sign byte is present.
Require gcd(abs(numerator),denominator)=1 and canonical zero 0/1. Thus zero Q
is exactly the ten hexadecimal bytes `00 00 00 00 00 01 00 00 00 01`.
Coordinates and weights are exact Q, not decimal strings parsed to floats.

Every payload begins the 8 bytes `MLSOMG01`, U32 schema=1, U32 kind, U64 record
count, then records in the declared order. No timestamps, paths, platform names,
NaNs or implicit defaults. Kinds: 1 vertices, 2 tetrahedra, 3 facets, 4 incidence,
5 samples, 6 resolution, 7 motion, 8 queries, 9 transform. Field order:

1. vertex: ID, Q x, Q y, Q z;
2. tetrahedron: ID, four ordered vertex IDs;
3. facet: ID, three ascending vertex IDs;
4. incidence: tetrahedron ID, U8 opposite-local-vertex index, facet ID,
   U8 orientation parity;
5. sample: ID, Q x, Q y, Q z, Q reference-volume, Q material-amount;
6. resolution: Q DeltaSquared; Q total-reference-volume;
7. motion: ID, U8 target-kind, target-ID, three Q velocity components;
8. query: ID, U8 operation, U64 argument-byte-count, typed arguments below;
9. transform: ID, row-major nine Q matrix entries, three Q translations,
   three Q common velocities, Q scale, U8 ordering variant.

Tet centroids use the exact average of the four serialized vertices. A/C receive
samples/resolution/motion/queries only; B additionally receives vertices, cells,
facets/incidence. Sample IDs need not equal cell IDs in candidate files: their
join is oracle/control-only. No sphere IDs or connected-body labels are fields.
Numerical query selectors are permitted only for requesting an observable, not
for changing any candidate's global occupancy reconstruction.

Canonical semantic IDs are obtained before metamorphic relabeling. Vertices are
sorted by their exact reference-coordinate triples; tetrahedra by their sorted
reference-vertex ID tuples; facets by sorted triples; IDs are rank+1. Store a
positive-orientation vertex tuple by starting from ascending IDs and swapping
the last two if its determinant is negative. Zero determinant rejects the input.
Incidence follows tetrahedron ID then opposite vertex 0..3; facet parity is the
parity relative to the outward oriented face (-1)^i times the remaining local
vertex order. Samples are ranked independently by centroid then reference cell
tuple. Coincident centroids retain distinct IDs. Do not deduplicate samples.

## 2. Exact reference tetrahedralization

Boxes use grid spacing s=2^(-k-2). Enumerate integer grid cells in lexicographic
(i,j,l) order. Each cube is divided into six Kuhn tetrahedra: for each permutation
(a,b,c) of axes, vertices v, v+s e_a, v+s(e_a+e_b), v+s(1,1,1). Face diagonals
are therefore consistent on shared grid faces. For the U fixture, include cubes
in the union of the three registered boxes once; shared vertices/facets are
single entries, and internal facets do not become boundary.

For the sphere, keep an internal *ordered refinement tuple* distinct from the
serialized positive orientation. The eight initial tuples are
(0, sigma_x e_x, sigma_y e_y, sigma_z e_z), signs in lexicographic (-1,+1)
order. A parent ordered (v0,v1,v2,v3) has edge midpoints
a=m01,b=m02,c=m03,d=m12,e=m13,f=m23. Its ordered children, in this exact order,
are:

    (v0,a,b,c), (a,v1,d,e), (b,d,v2,f), (c,e,f,v3),
    (a,b,c,e),  (a,b,d,e),  (b,c,e,f),  (b,d,e,f).

This fixes central diagonal b--e. Do not reorder these tuples before recursive
refinement. Canonical output orientation is applied only after refinement.
Depth is d=k+1. Shared dyadic reference coordinates deduplicate exactly.
All face refinements are midpoint four-way splits, including octant boundaries.

The reference shape bound is checked by closure of ordered Gram matrices. Start
G=I for the unit reference edge matrix. For each child take C to be twice its
edge matrix in parent coordinates and form C^T G C. Saturate this exact integer
operation; it has six ordered Gram classes, all with maximum squared vertex-
pair distance <=3. An independent template check must establish this finite
closure, orientations and volume partition before materializing fixtures.
Thus diam(T_ref,d)<=sqrt(3) 2^-d; with the registered radial map the exact
mapped-vertex bound is Delta<=9*2^-d. This is a construction bound, not a
measurement of A/B/C and not a claim that their reconstructed boundaries pass.

Map nonzero reference q by F(q)=||q||_1 q/||q||_2, F(0)=0. Encode each component
as nearest-even multiple of 2^-256, with an independently obtained 512-bit
outward enclosure certifying the rounding choice. An unresolved rounding cell
is an input-generation failure, not permission to pick either endpoint or raise
precision. Add translation/rotation/scale afterward as exact rational operations.
Track coordinate encoding error separately; the above asymptotic statement is
about the exact construction, not an infinite fixed-bit sequence below its floor.

## 3. Reference weights, constants and Delta

The encoded sphere total is W=RN_even(2^256*(4*pi/3))*2^-256, certified by a
512-bit interval for pi. Each initial octant has W/8. Cube/slab/U reference
weights are their exact rational tetrahedral volumes. Material-amount weights
are reference weights divided by W_fixture; their exact sum is 1 at every level.
They are observer quadrature quantities, not fractional chemistry inventory.

Sphere weights approximate the physical volume of F(T_ref). On each orthant
the Jacobian density is J(q)=(||q||_1/||q||_2)^3; the point q=0 has measure zero.
Do not use flat tetrahedral volume or equal child counts as an exact substitute.
Independently enclose each child's integral. Use a degree-12 interval Taylor
polynomial on affine reference-simplex coordinates, exact rational monomial
integrals and an outward derivative remainder. At regions meeting q=0 use
1<=J<=3*sqrt(3), or exact homogeneous scaling for a scaled copy of an existing
reference region. Subdivide by the frozen eight-child rule, largest integral
width first, ties by reference ancestry. Every such subdivision/derivative-bound
evaluation is recorded separately as input-generation verification work; none
may later be sold as a free candidate certificate. Input preparation remains
subject to the memory, wall-time and evidence-size ceilings. The 2^22 counter
governs runtime certification after input loading, not pre-data materialization;
unresolved weights leave the input gate closed.

At a node with encoded parent weight w and eight certified child integrals
[l_i,u_i], use their rational midpoints m_i and normalized shares
p_i=m_i/sum(m_j). Allocate w*floor(2^128*p_i)/2^128 to each child and distribute
the remaining units of w/2^128 in descending fractional-remainder order, ties by
child index. This exactly partitions w. Require every allocated weight positive.
The verifier propagates the parent-weight discrepancy and ratio enclosures,
including the correlated normalization denominator, rather than treating w as
the exact physical volume. Across all leaves at each level require the sum of
absolute physical-weight-error upper bounds <=2^-24*W. This fixed input-fidelity
allowance is stricter than, and does not replace, the registered volume/oracle
budgets. Failure leaves inventory inconclusive; no fitting/rescaling to a
candidate occupied-volume result. Ancestor/child allocations are oracle-only
witnesses; final numerical weights are candidate input.

Pi is independently enclosed using Machin's identity
pi=16 atan(1/5)-4 atan(1/239). Use alternating rational series with the next-term
remainder until width <=2^-600, then round endpoints outward to 512 significant
binary bits. This exact-arithmetic construction is distinct from the candidate's
256-bit library constant. Sqrt is enclosed by exact rational square comparisons;
transcendental oracle operations use 512-bit downward/upward MPFR rounding,
with explicit interval domain tests and no default nearest-round witnesses.
Finite encoding errors remain terms in the oracle; no exact-pi claim.

**DeltaSquared is exactly the maximum squared edge length of all mapped straight
tetrahedra in the decoded candidate input.** Compute it as a reduced rational
from those coordinates, not from the reference mesh, a bounding box, a mean edge,
the analytic sphere or the bound 9*2^-d. The maximum tetrahedral diameter equals
its maximum vertex-pair distance. Candidate C evaluates sqrt(DeltaSquared) at
its frozen precision. An independent streaming check of all six edges of every
cell must reproduce the descriptor exactly. Descriptor generation is input
preparation, not a candidate metric; its verification is recorded and charged.
For similarity transforms DeltaSquared scales by scale^2 exactly. During a
prescribed motion it remains the reference descriptor at t=0: it is not an
adaptive bandwidth. Verify radial centroid min/max squared norms from input
against independently generated construction enclosures at every sphere level.

## 4. Input primitive counts

For a rectangular grid (nx,ny,nz): C=nx*ny*nz, T=6C, V=(nx+1)(ny+1)(nz+1),
boundary triangles B=4(nx*ny+ny*nz+nz*nx), facets F=2T+B/2, incidence records=4T,
samples=T. Cube dimensions are (8,8,8)*2^k; slab (16,16,2)*2^k. Both T sequences
are 3072,24576,196608,1572864,12582912. Do not confuse primitive count with work.

For U, with m=2^k, C=44m^3, T=264m^3; compute V by the exact set union of its
three closed lattice-vertex boxes, B by exposed unit-square faces times two,
F=2T+B/2 and incidence=4T. Report the resulting integers in the input manifest;
do not separately count shared interface vertices/faces. Set-union enumeration
is canonical format construction, not a candidate geometry validity certificate.

For one sphere, n=2^(k+1): T=8n^3, V=(4n^3+6n^2+8n+3)/3,
B=8n^2, F=16n^3+4n^2, incidence=32n^3, samples=T:

| k | V | T / samples | F | incidence |
|---|---:|---:|---:|---:|
| 0 | 25 | 64 | 144 | 256 |
| 1 | 129 | 512 | 1088 | 2048 |
| 2 | 833 | 4096 | 8448 | 16384 |
| 3 | 6017 | 32768 | 66560 | 131072 |
| 4 | 45825 | 262144 | 528384 | 1048576 |

Two separated sphere inputs have twice these counts with no initial shared IDs.
Transforms/order variants do not change counts. Preflight actual encoded sizes
and peak decoded layout, including oracle arrays, caches and input loading.
The 2 GiB/30-minute/8 GiB limits apply unchanged. Counts or memory estimates are
not claims that a candidate will fit or certify its metrics.

## 5. U motion and exact transform/order inventory

The U approach is the global affine map A(t)=diag(1-t/4,1,1), t in [0,2].
Apply it to every vertex/sample, including the base. No disconnected arm label
or conflicting displacement of shared vertices exists. det A(t)>=1/2 on this
interval. Facing-arm separation decreases from 3/2 to 3/4; this is an approach
test, not a claimed collision. The validity control t=4 is singular and must be
rejected. Reference weights/material amount stay fixed; the analytical current
domain volume changes by det A(t). Do not silently rescale A/C weights to match
B or the analytic compressed volume. This is prescribed geometry, not a material
compressibility or heat law. Subsequent transformations act after A(t).

For each registered fixture/level use the following finite variants independently,
not a Cartesian product: identity; all other proper signed-axis permutations;
translation b=(3,-2,5); Rz; Rx*Rz; uniform scales 1/2 and 2; common velocity boost
(1/4,-1/2,1/8); reversed record order; shuffled record order; ID relabeling.
Rz=[[3/5,-4/5,0],[4/5,3/5,0],[0,0,1]],
Rx=[[1,0,0],[0,3/5,-4/5],[0,4/5,3/5]].
There are 33 variants (24 rotations including identity, plus nine others).
For scale a, positions, all query lengths and velocities scale by a, volumes by
a^3, and time remains unchanged. Rotation acts on both motion and queries;
translation/common boost acts on every material coordinate, query witness and
external control plane. Do not boost matter while leaving the comparison plane
in another frame. The U validity control uses only identity.

Proper signed permutations are enumerated by axis permutation lexicographically,
then signs lexicographically (-1,+1); retain determinant +1; identity gets ordinal
0 and the rest retain enumeration order. Other variant ordinals follow the list
above. IDs relabel by id -> count+1-id independently for each primitive namespace,
updating every reference and query; sorting relabeled records restores canonical
wire order. Semantic remapping is retained only by the controller.

Shuffle each record table independently using Fisher-Yates from last index down
to 1. Seed state is U64(260908) XOR U64(kind<<32) XOR U64(fixture_ordinal<<16)
XOR U64(level<<8). Use SplitMix64 modulo 2^64: add 0x9e3779b97f4a7c15; xor-shift
30/multiply 0xbf58476d1ce4e5b9; xor-shift 27/multiply 0x94d049bb133111eb;
xor-shift 31. For a uniform integer in [0,b), reject draws x < (2^64 mod b),
then use x mod b. No platform RNG. Reverse/shuffle alters storage, not IDs or
oriented simplex order. Frozen fixture ordinals 1..7 are control/oracle-only;
candidate directories use opaque content digests.

## 6. Complete query inventory

Operations: 1 union volume; 2 global boundary covering for Hausdorff certification; 3 boundary
distance/closest-set at a point; 4 smooth-normal set at closest boundary;
5 separation/closest-set between numerical witness regions; 6 swept contact;
7 point membership; 8 invalid-input rejection. Queries carry numeric arguments
only. There is no analytic-shape opcode or expected result in candidate files.
Global oracle joins and smooth patch labels exist only in `oracle/`. Operation 2
requests candidate boundary covers/witnesses, not access to the true boundary;
the independent verifier constructs both directed Hausdorff comparisons.

Query argument bytes have no optional fields. A point is three Q in x,y,z order.
A region is U64 half-space count followed by that many tuples (Q nx, Q ny, Q nz,
Q d0, Q d1), meaning n dot x <= d0+t*d1; n must be nonzero. Sort planes by their
exact five-Q tuple, without floating normalization. Whole space has count=0.
Bounded U windows use six planes; sphere-pair half spaces use one. Operation
arguments in exact order are: (1) Q time; (2) Q time; (3) point,Q time;
(4) point,Q time; (5) region,region,Q time; (6) U8 mode,Q t0,Q t1 then either
region,region for mode=0 or five Q plane coefficients for mode=1;
(7) point,Q time; (8) U64 invalid-control-ID,U64 payload-size,raw payload bytes.
Mode=1 compares the complete candidate occupancy with the explicit external
plane. Moving regions/planes must carry the transformed d1 coefficient. The
controller rejects a byte-count mismatch, unknown opcode/mode or trailing bytes.
Unique/smooth/nonunique expected types belong only to the oracle join, not to
a candidate dispatch flag. Query IDs are rank+1 after sorting operation then
argument bytes; duplicate operation/argument pairs are stored once and all
oracle obligations reference the same ID. The singular U t=4 control is the
prescribed invalid motion input, not an invitation to evaluate candidate geometry
outside the registered valid motion interval.

At every fixture/level/variant: one volume query; both directed global boundary
distance obligations (one symmetric Hausdorff report); and the following finite
point nets, deduplicated by exact coordinates and operation, sorted lexicographically.
Finite maxima never replace global coverings.

- Box/slab/U: every exposed planar rectangular patch has a 9x9 tensor net at
  local fractions i/8,j/8, i,j=0..8. Normal-error samples use i,j=1..7 only;
  edges/vertices use closest-set/nonunique-normal queries. For U derive patches
  from the explicit union of the three oracle boxes, excluding shared interiors.
- Sphere: six dominant-axis charts u(a,b)=normalize(+-e_j+a e_l+b e_m), axes
  j ascending, remaining axes l<m; a,b=-1+i/4, i=0..8. Deduplicate seams; encode
  points at nearest-even 2^-256 with directed oracle enclosures. All sphere
  normals are smooth; candidate points are numerical queries, not oracle normals.
- At each net point also query membership and closest boundary at offsets
  0,+1/64,-1/64 along the analytical outward normal. Encode those points using
  the same rule; keep the normal itself only in oracle files. Edge/vertex offsets
  are omitted; do not choose an arbitrary normal there.
- Add the cube centre (six closest face points), slab centre (two closest faces),
  all box corners/edge midpoints, sphere centre (entire spherical closest set),
  and U reentrant edges/vertices. Report normal cone/nonunique sets where needed.
- For two spheres, query global inter-component separation/closest sets and the
  line-of-centres witness at the midpoint. Query regions are the two closed half
  spaces through that midpoint with normals +-e_x, transformed with the fixture.
  They restrict the observable only: all candidates reconstruct their full input
  occupancy first. A connected bridge across the separator is not discarded.
  The separator belongs to both regions. In particular, the analytical t=1
  touching point remains in both restricted closest sets, not an unattained
  infimum. This uses the same <= inequality as the region byte contract.
- For U, query facing boundaries within y in [0,3/4], z in [-1/8,1/8], x in
  [-1,0] and [0,1]. Transform these closed query windows with A(t)/the variant.
  Include their entire closest sets, not only one sampled point pair. This does
  not exclude contact between parts of the same connected material component.

Moving fixtures 5,6 and the U map additionally use t=j/8, j=0..16 for all static
observables, and complete swept queries over [0,2] plus each [j/8,(j+1)/8].
The original two-sphere and sphere-plane controls have first contact t=1.
Include the following analytical CCD primitive controls, independent of candidates:
Q(t)=a t^2+b t+c on [0,2], rows (a,b,c): (0,0,1), (0,0,0), (0,0,-1),
(1,-2,1), (1,0,1), (1,-6,8), (1,2,0), (1,-3,2), (1,1,-2).
They cover stationary separation/touch/overlap, tangency, no roots, boundary/outside
roots, separating initial touch and interior crossings. Linear plane controls
g(t)=2-t, 1-t, t, -t, 1, 0, -1 use the same interval. Controls are oracle/test
inputs, never extra material fixtures or substitutions for candidate CCD.

Every query-net row must be enumerated in the materialized query manifest with
its exact bytes and an oracle-only expected-type/patch join. Do not add/remove
samples after candidate outputs. Changes require a preserved pre-data amendment.

## 7. Certified covering/search algorithm

Do not claim completeness from the finite net. Start from a closed rational
bounding cube covering the full candidate and oracle occupancy. For A enlarge
the sample-coordinate box by an outward upper maximum radius. For B use vertex
extrema. For C choose the smallest positive integer R satisfying, with outward
bounds, V_total*exp(-R^2/(2h^2))/((2*pi)^(3/2)*h^3)<1/2, and expand coordinate
extrema by R; outside that box every sample is at least R away. This proves no
occupied C component is omitted. Searching for R is charged runtime work.

Partition boxes by their longest side, x/y/z tie order, at the exact rational
midpoint. Queue order is depth then Morton/binary ancestry order, never candidate
error ranking. Children are closed and share their split boundary. For volume,
sum disjoint-interior boxes only; shared faces have zero Lebesgue volume. Bound
inside/outside/undecided with exact A/B predicates or outward C function ranges.
Undecided total volume is the remaining error allowance, not an ignored region.

For boundary searches, exclude boxes only with a proof that they contain no
boundary (including hole boundaries). Retained boxes form an outer cover, not
proof each box contains a boundary. Boundary existence needs a separate certified
witness: feature intersection, root bracket/interval-Newton inclusion or exact
boundary point. Nearest-distance upper bounds need such existence witnesses;
distance to an unverified outer box is only a lower bound. Use 1-Lipschitz distance
and box diameters for whole-cover directed Hausdorff bounds. An unclosed boundary
existence obligation is inconclusive, never zero error.

For B surface triangles use barycentric midpoint four-way subdivision; interval
feature-pair bounds must cover every relevant pair (or prune it with a valid
lower bound). For sphere oracle patches use the six dominant-axis charts with
closed [-1,1]^2 domains and exact seam coverage. Planar patches use closed
parameter rectangles and separate edge/vertex strata. Interval derivatives bound
normals on smooth patches; zero gradients or feature ties retain sets. A corner
normal cannot be certified through a smooth-patch assumption.

For closest sets retain all cells whose lower bound is <= the best certified
upper bound; equal minima cannot be pruned by ID. Return a cover and witnesses,
not an arbitrarily selected closest point. Numeric query-window boundaries are
part of the closed coverage obligation, not permission to omit a touching point.

Swept searches add t in [0,2] (or the requested subinterval). Bisect the longest
normalized spatial/time side (time normalized by horizon), ties x,y,z,t. Candidate
motions and reference geometry must be enclosed over the entire space-time cell.
Search possible earliest times in increasing interval lower endpoint, then
ancestry. No-hit requires exclusion of every covered cell. First-hit requires an
existence witness and exclusion of every earlier interval; an unresolved tangency
is inconclusive. Exact quadratic controls can use their algebraic interval-minimum
predicate instead. It does not substitute for B/C moving-boundary certification.

Stop only when both bounds decide the frozen gate with width <=1/100 its budget,
or on a frozen resource/ambiguity limit. No guessed normals, uncovered gaps,
endpoint-only sweeps, nominal-force assumptions or inward witness bounds.

## 8. Deterministic work accounting

Keep the input-inventory counter separate. All stored samples/vertices/cells/
facets/incidences count there even when read lazily. Loading/canonical decoding
uses the explicit exemption from the accepted amendment, but consumes memory/time.
Every generated certification object or predicate below consumes the shared
2^22 runtime-work counter per candidate/fixture/level. Each transformed instance
is a separately identified fixture row; sum across all queries of that row,
and do not reset at each query to evade the ceiling:

- one unit per generated bounding/search/cover/root-isolation region, including
  roots and every child (octree children cost eight, not one);
- one per evaluated primitive validity, overlap, intersection, distance or pair-
  pruning predicate, including every member hidden inside a batched/vector call;
- one per primitive contribution to an interval field/derivative bound; C's
  all-sample sum is not one free operation;
- one per generated BVH node, runtime face/adjacency entry, cache entry, derived
  geometry object or refinement cell; retaining only final nodes does not refund;
- one per root/interval-Newton/Taylor bound update in addition to constituent
  primitive contributions and generated regions;
- one per sampled diagnostic query evaluation plus its primitive/search work.

Charge before execution/allocation; refuse unit 2^22+1, with the pending operation
recorded. Fixed scalar arithmetic inside one primitive evaluation is included
in that evaluation's unit, not an exemption for arbitrary loops. Reading a stored
input facet is not a new facet; independently validating it is a predicate.
Cached certificates may be reused only with authenticated identical inputs and
recorded dependencies; creation costs remain charged. No cross-level/candidate
free cache. Canonical twins each receive the same cap. OS resource diagnostics
are non-scientific fields; deterministic work exhaustion must reproduce exactly.

Input-generation integration/validation costs have separate count receipts,
not a candidate pass or a new 2^22 exemption for runtime work. They cannot establish candidate
validity merely by having generated the input. No runtime work moves into the
input generator except the explicit nonadaptive fixture construction and weight/
descriptor certification prescribed here. Input preparation stays under the
unchanged memory/time/evidence ceilings. Exhaustion leaves a gate incomplete.

### Pre-materialization closure and accepted C resource consequence

Preserve addendum commit `9588e1ed2a2ffe36c02f149af2d0f72c7b1a649f` in history.
The explicit denominator length and consistently closed sphere-pair selectors
above are pre-materialization semantic errata. No candidate, physical fixture,
budget, oracle or disposition is changed. No input materialization or candidate
measurement has occurred at this correction.

Keep the existing resource-accounting architecture unchanged. At cube/slab k=4,
C has 12,582,912 samples. Even one all-sample interval-field evaluation requires
at least 12,582,912 primitive contributions, exceeding the unchanged 4,194,304
runtime certification-work cap. Accept this predetermined resource consequence
explicitly rather than exempting a sum, raising the cap, or adding an unregistered
accelerated/certified aggregation scheme.

These C rows are resource-inconclusive, not resolved geometry failures. C cannot
qualify for full-inventory positive selection under this protocol, and its
inconclusiveness cannot serve as the required resolved stateless failure for
`explicit_material_domain_state_required_before_contact`. Other resolved
candidate findings remain reportable under the governing disposition rules;
do not turn this administrative/resource limitation into a physical necessity
claim or silently omit the mandatory rows. This consequence is known by exact
input-count arithmetic before data, not inferred from a candidate execution.

## 9. Oracle accuracy and identities

Normalized allowed enclosure widths remain volume <=0.0002, Hausdorff/gap/time/
location <=0.0005 and smooth-normal angle <=0.001 rad. These are widths, not
allowances to shift the physical budget. Report bounds and units, not only a
midpoint. Transform uncertainty, encoding deficits, material-weight uncertainty,
quadrature remainder and search-cover widths must all enter the relevant bound.

For Delta compare exact rationals, then independently enclose sqrt for C. For
radial support compare exact squared norms. Oracle volume of cube/slab/U uses
exact disjoint-interior box sums; sphere volumes use the independently enclosed
pi. Oracle U current volume follows det A(t), not conserved reference weight.
Normals at true edges/vertices remain set-valued. Signed least-squares or contact
forces are outside this lab. No B96/binary64 trajectory is geometric truth.

## 10. Closed input seal before evaluation

Materialize all prescribed primitive/query/transform payloads with a generator
that contains no candidate evaluator. Record per-table counts, encoded/decoded
sizes and exact coordinate/weight diagnostics. Cache-free independent decoding
must reproduce the canonical byte stream. Duplicate payloads may be content-
addressed once; a run's manifest lists every referenced blob. Factored exact
global transforms may be a canonical coordinate encoding only if the pre-data
seal also records the hash/count of its fully decoded logical stream. This is
fixed input decoding, not adaptive geometry generation; its cost remains in
memory/time and cannot hide a certification search.

Manifest is ASCII JSON, sorted keys, no whitespace, final LF, integer counts
only and lowercase SHA-256. `files` maps each relative POSIX path to size and
SHA-256. Reject absolute paths, '..', symlinks, duplicates and extra/missing files.
Have separate `candidate-manifest.json` and `oracle-manifest.json`; a controller
root lists their digests, this addendum's digest, governing source, generator
source, primitive/query counts, decoded-stream hashes and constant/weight/
descriptor audit receipts. Manifests exclude only themselves and the root seal;
the root contains no self-referential hash. Hash every generated input, not merely
the recipe. Preserve any failed materialization in a separate attempt directory.

Before opening data: commit/push this addendum, obtain its review, materialize
and independently validate the exact inputs, close their manifests, and record
the resulting root digest before running any candidate. If materialization
cannot satisfy this specification, preserve the attempt and report the missing
input gate. Do not revise recipes, weights, queries, ceilings or widths after
seeing candidate behavior. This document alone is not an input-seal receipt.

No source mechanics, World state, contact implementation, formal proof or
candidate output is part of this addendum commit. **NO_PROMOTION remains.**
