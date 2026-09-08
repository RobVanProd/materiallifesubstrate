# Root-bound Cartesian structural validity argument

Scope: B's registered cube/slab inputs only. This is a pre-data structural
validity proof, not an occupied-volume/boundary/contact answer. The authorized
amendment is `0bb3c2c`; earlier validity-budget and input attempts remain intact.

## Unit-cell template

For each permutation `(a,b,c)` of the three coordinate axes take the simplex
with chain vertices `0, e_a, e_a+e_b, (1,1,1)`. Swap the final two vertices when
necessary to give positive orientation; this changes orientation, not the set.
The independent checker enumerates four-element subsets of the eight Boolean
corners and recovers precisely these six maximal chains, without importing the
fixture generator or certificate constructor.

Its four barycentric affine forms (in chain order) are
`1-x_a, x_a-x_b, x_b-x_c, x_c`. The checker verifies their delta values at every
vertex, that they sum to one identically, and that they are exactly these four
forms, allowing the orientation permutation. Since the affine determinant is
one, the forms uniquely give barycentric coordinates. Consequently the closed
simplex is exactly `1 >= x_a >= x_b >= x_c >= 0`.

Every cube point has at least one weak coordinate order. The Lean theorem
`cartesian_six_orders` proves the exhaustive six-way alternative;
`cartesian_chain_weights` proves nonnegativity, partition and reconstruction
for the sorted triple. Thus the six closed simplices cover the complete cube,
including equality planes. No sampling or volume-sum inference is used.

Two distinct axis orders have an inverted pair. The independent checker
exhausts all 15 pairs. In simplex interiors all four weights are positive, so
the orders are strict. An inverted strict pair cannot hold simultaneously
(`cartesian_strict_inversion`), proving disjoint interiors. Each oriented
determinant is exactly one, not a floating sign test.

The 24 oriented simplex faces reduce to six canceling internal pairs and
twelve exterior triangles. Exactly two triangles lie on each cube face. The
independent checker translates the low-face triangles to their opposite face,
checks exact matching vertex triples and opposite incidence signs in each of
the three axes. This establishes conforming neighbor-face triangulations.

## Finite Cartesian replication

Closed Cartesian unit cells cover the closed registered rectangular index
domain: each coordinate admits an integer cell index, with a boundary point
assigned to either incident cell where both exist. Distinct cell interiors
cannot intersect: a differing integer index separates them in at least one
coordinate (`cartesian_separated_cells`). The unit-cell proof applies after
translation and positive grid scaling. Matching face triangulations are the
same translation-invariant template in every neighbor, so there are no missing
internal faces or overlapping cell interiors anywhere in the replicated grid.

This argument depends on *complete, unique instantiation*. That premise is
checked against freshly copied root-bound input bytes by the existing independent
streaming checker, not assumed from grid metadata. It checks the complete sorted
vertex inventory; each positive oriented cell is a unique monotone chain in an
allowed Cartesian cell; and the unique cell count is exactly six times the
number of allowed cells. A subset of that finite allowed set with its full
cardinality is the whole set. It checks every facet join and every signed
incidence, including boundary counts and interior cancellation. Samples and
resolution fields are also independently checked, though they do not supply
extra candidate geometry answers. Ten cube/slab levels are replayed separately
under 2 GiB and 1,800 seconds each, with explicit primitive-count receipts.

## Transforms, order and identity

Each registered transform is checked from its exact rational wire: `R^T R=I`,
`det R=1`, and scale `s>0`. Hence `x -> s R x+b` is an invertible affine map.
An invertible affine map preserves intersections, interiors, coverage and shared
faces, while the determinant multiplies by `s^3>0`. The checker additionally
evaluates the transformed determinant of every template simplex for every
bound row exactly. Common translation/velocity terms cancel from edges and do
not affect validity at any shared time. This does not qualify a moving-complex
or non-Cartesian fixture for the exception.

Reverse/shuffle/relabel variants use their independently decoded whole-stream
identities, including incidence parity adjustments. They cannot borrow a
certificate by matching only counts or nominal transform parameters.

## Trust boundary and claims

The certificate binds the candidate-manifest SHA-256 (the candidate-input root),
base blob identities, exact grid dimensions, template version/hash, transform
blob and all fully decoded I2 stream hashes. The final controller seal must
authenticate that root, this certificate and the independent verification
receipt. This avoids a self-referential final-root hash. The candidate trusts
only a validity capability for matching authenticated bytes; it must not accept
a caller-supplied replacement root as trusted merely because its hash is valid.

The candidate receives no oracle labels or precomputed query answers from this
certificate. All union, boundary, overlap, normals, distance and swept-search
work is still charged normally. A changed vertex, incidence, grid, transform or
decoded stream either breaks authentication or fails structural validation.

Lean proves the named exact algebra/order statements, not the executable
checker, SHA-256 security or arbitrary mesh validity. The global tiling argument
above and its finite instantiation checks are stated separately from those
formal theorems. No claim of empirical geometry convergence follows merely
from structural validity. **NO_PROMOTION remains.**
