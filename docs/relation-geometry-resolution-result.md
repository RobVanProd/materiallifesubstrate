# Relation Geometry Resolution Lab result

## Decision

```text
ordinary-scale cause: avoidable direct-norm-subtraction cancellation
retained evaluator: cancellation_resistant_binary64 (Path B)
extended precision disposition: not retained; Path C adds no required capability
collapse cause: intrinsic 1/r conditioning plus eventual binary64 classifier loss
safe force domain: r/l0 >= 2^-24
decision: retain_relation_geometry_with_explicit_safe_domain_for_research
promotion: NO_PROMOTION
```

The accepted relation graph, reference coordinates, local collective energy,
symmetric `H_force`, extension coordinate, and central force/tangent equations
were not changed.  The retained object is a stateless relation-geometry
evaluation path, not an authoritative world-force API or an evolution step.

## Parent fingerprint

Path A reproduced the sealed Conservative Force Consistency parent rooted at
`7ee2555521b2c3a86ece87fad961500e413244c5`:

- all three octahedron policies lost the one-ULP ordinary-scale adjacency at
  `r/l0=1`;
- the inherited binary64 tangent classifier was unresolved at `r/l0=2^-32`
  for the three octahedron policies and K4 `K/G=1/3`; and
- every registered exact-coincidence path failed closed without partial
  energy, force, direction, or tangent output.

This gate was completed before candidate results were interpreted.

## Ordinary-scale causal result

The independent oracle reconstructed every exported binary64 coordinate from
its uint64 encoding.  The smallest perturbation is of order `2^-1074` beside
unit coordinates, so the oracle used 420 decimal digits; the preregistered
120-digit minimum was insufficient to distinguish the exact input before the
square root.

Across the three octahedron policies and six perturbations
`{-4,-2,-1,+1,+2,+4}` ULP:

- Path A failed all 18 rows while exactly reproducing the accepted operation
  sequence;
- Path B passed all 18 rows and its independent binary64 reimplementation was
  bit-exact on every exported length, extension, direction, and order field;
- Path C also passed all 18 rows; and
- the oracle confirmed that every perturbed exact binary64-coordinate state
  has a distinct exact relation length.

The direct subtraction of two rounded norms is therefore the ordinary-scale
cause.  Path B retains the factored squared-distance numerator even where two
correctly rounded extension outputs coincide at the binary64 output floor, so
the evaluator does not relabel those exact input states as the same geometry.

## Collapse causal result

For K4 and octahedron under all three policies, the 420-digit tangent exhibits
strict growth of both the geometric Hessian norm and the non-rigid condition
estimate over `2^-8` through `2^-48`.  This agrees with the accepted radial
term

```text
g/r (I - n n^T).
```

The growth persists in the high-precision oracle and is therefore intrinsic,
not a norm-evaluation bug.  Both candidate paths pass the complete registered
gate through `2^-28`.  The inherited binary64 condition classification first
becomes unresolved at `2^-32`; later numerical re-openings are diagnostic and
cannot reopen the domain under the preregistered contiguous-prefix rule.

The last contiguous pass is `2^-28`.  Applying the required full four-bit
safety step gives

```text
rho_min = 2^-24.
```

This is a noncoincident force-domain contract only.  It is not a collapse,
contact, fracture, or time-integration rule.

## Regression and independence result

The selectable paths preserve the bounded accepted-force regressions:

- `f=-grad U`, total force, torque about two origins, and virtual power;
- material/geometric tangent decomposition and symmetry;
- translation and proper-rotation covariance and uniform scaling;
- packet-ID relabeling, packet/relation permutation, and endpoint reversal;
- exact-coincidence fail-closed behavior.

The independent oracle consumes raw bit patterns, mirrors the sealed parent
coordinate and full `H` inventories, separately implements Paths A and B, and
assembles the 420-digit energy, force, and Hessian.  Its mutation suite rejects
direct subtraction masquerading as Path B, changed `H`, changed reference
coordinates, epsilon clamping, wrong relation orientation, hidden repulsion,
persistent multiword position state, and intrinsic failures relabeled as
passes.

Lean proves only the exact square-root rationalization and its squared-distance
specialization.  It does not claim a binary64 error proof.

## Boundary

No epsilon normalization, clamp, cap, repulsion, regularization, diagonal
shift, topology change, relation deletion, persistent double-double packet
state, force installation, or time integration was introduced.

The final disposition remains **NO PROMOTION TO DYNAMICS**.
