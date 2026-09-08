# Pre-data input-gate escalation: moving-pair overlap scope

Governing frozen protocol: `2874a31c2e5302c2ca5053e1f76fef3430ab99c3`.
Accepted mechanics/main: `639ab635769a7d244aa255281acbabad78c27057`.
Initial input-tooling commit: `d8dfd00`.

**This is an input-validity/interpretation audit, not a candidate result or a
completed lab seal. Zero A/B/C evaluations. NO_PROMOTION.**

## Exact finding

The preregistration defines B as a union of non-overlapping tetrahedral cells
and requires rejection of interior overlap without specifying an exception for
different connected parcel complexes. The same protocol registers the moving
two-sphere fixture through time 2, with first contact at time 1. The addendum
requires every static observable at all 17 times j/8 as well as complete sweeps.

The prescribed motion necessarily creates cross-complex penetration after
contact. This is not an inference from an analytical sphere substituted for B.
The materialized **level-0 straight tetrahedra themselves** give an exact witness:

- Registered fixture 5, level 0, time `2`.
- Point `(1/32, 1/16, 3/32)` lies strictly inside cells **60** and **83**.
- Their vertex-connectivity roots are different (1 and 26).
- Each set of four exact rational barycentric coordinates sums to 1, reproduces
  the same point exactly, and has every coordinate strictly greater than `1/256`.
- Both cell affine bases have full rank. This is positive-volume interior
  overlap, not an ambiguous touching point or a rounding-floor effect.

The full coordinates, rational barycentric witnesses, and byte identities of
the input vertices, cells and explicitly serialized motion are preserved in
`occupied-matter-geometry-moving-input-witness.json`. The separate checker
`tools/occupied_geometry_overlap_witness_check.py` authenticates those input
bytes and verifies the convex combinations and affine rank by exact elimination;
it does not run the determinant search used to produce the witness.

The registered motion file has 178 records, 8,568 bytes, SHA-256
`31dddf35b3a74a3be122567f39c5484381ee1a9d041f25c09618fd26bad74e5c`.
The pair vertex and tetrahedron identities appear in the witness record.

## Why this needs a scientific interpretation, not a numerical repair

All initial sphere levels pass positive orientation, conforming face-incidence,
and an exact sufficient global injectivity certificate. Each prescribed rigid
translation preserves its individual parcel complex. The conflict concerns
overlap **between** two otherwise valid moving complexes.

It would be inappropriate to silently:

- exempt cross-complex overlap from B's global rejection rule;
- stop the registered horizon at first contact;
- remove post-contact volume/normal/closest-set queries;
- add contact forces or change the prescribed trajectories; or
- call the resulting mandatory-row rejection evidence against continuum parcels.

The protocol needs to say whether cross-complex penetration is a required
collision observable over the full horizon (with parcel validity scoped within
each connected complex), or whether post-contact rows are expected-invalid
controls with an explicit rule for their remaining metric obligations. Either
choice must be frozen before candidate evaluation. No such change is made here.

## Work preserved and remaining gates

`build/occupied-geometry-input-attempt-v1/` is retained without deletion or
replacement. Completed pre-data checks include:

- all five cube, slab and U levels independently checked, including both
  12,582,912-tetrahedron finest Cartesian inputs;
- all five sphere coordinate/diameter/radial-support and incidence checks;
- all five sphere cellwise symmetric-Jacobian positivity checks, supporting
  strict monotonicity of the continuous piecewise-affine map on the convex
  reference octahedron and hence global injectivity;
- exact hierarchical sphere-weight allocation and registered aggregate
  physical-weight-error bounds at all five levels;
- seven encoding/template/cubature/allocation unit tests;
- thirteen Lean statements checked successfully, with no `sorryAx` dependency;
- all seven fixture query inventories materialized for the 33 variants;
- independently reconstructed cube/slab finite query nets and exact query
  transform covariance for all 33 variants; and
- independent exact confirmation of the overlap witness above.

These are partial input checks, not a complete input certificate. The separate
full binomial-polynomial weight replay was explicitly interrupted at this
scientific pause, not classified as a resource or arithmetic failure. The
spherical query checker encountered a Python Fraction/gmpy2 conversion error;
the correction is preserved in source, but its remaining full inventory replay
is pending. Prior Lean invocation/import/proof diagnostics and the original
polynomial implementation/pilot receipts are retained in the attempt directory.
No candidate output exists, no root input seal has been issued, no inherited
40-case observer replay is claimed, and no final lab disposition is assigned.

The original main, mechanics, governing preregistration, thresholds, resource
ceilings and Candidate-C predeclared resource-inconclusive rows are unchanged.
No evidence tag, release or main merge is performed by this audit.
