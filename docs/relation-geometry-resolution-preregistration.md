# Relation Geometry Resolution Lab preregistration

## 1. Immutable parent and stop condition

The only accepted parent is:

```text
source commit: 7ee2555521b2c3a86ece87fad961500e413244c5
evidence tag: conservative-force-consistency-lab-evidence-v1
tag object: aeee2202019ea6eecd0b3b31c58e7855edd79ef2
decision: retain_force_but_block_dynamics_on_degeneracy
```

The force evidence archive has SHA-256
`fe6f34cad1e2794ec50ce9df6f2f88ea4f0aca07322f64f78bf003aa4ceb2ca4`.
The frozen parent Constitutive Expressivity archive used as producer input has
SHA-256
`1bc4dccee877cd4a3d4ee05df7d3aab00d4643b400186a6a5ef5447b6cbb1123`.

The branch must stop with `stop_inconclusive_or_wrong_parent` if any immutable
identity differs or if Path A does not reproduce the parent blocker
fingerprint.

On 2026-09-01 the initial Linux Path-A replay from the downloaded parent
`bundles/full-a` reproduced:

- three octahedron `r/l0=1` rows with zero one-ULP force sensitivity and
  `adjacent_length_resolved=false`;
- unresolved binary64 tangent classification at `r/l0=2^-32` for all three
  octahedron policies and K4 at `K/G=1/3`;
- six registered exact-coincidence evaluations failing closed; and
- the same 84-row compression inventory, 3 producer failures, and complete
  unresolved-row set as the sealed evidence.

The Linux control CSV is not required to be byte-identical to the MSVC CSV:
resolved Jacobi condition estimates may differ by a few ulps under the inherited
cross-runtime envelope.  The registered resolved/unresolved classifications,
adjacency predicates, exact-coincidence statuses, row identities, and counts
must be identical.

## 2. Question and hypotheses

The lab asks:

```text
Can the already-accepted force physics be evaluated robustly, and where does
that physics itself become singular?
```

The causal hypotheses are preregistered as follows.

- **H-arithmetic:** ordinary-scale adjacency is lost in one or more of endpoint
  subtraction, squared-norm accumulation, square root rounding, or direct
  subtraction of two rounded norms.  A stateless bounded evaluator can recover
  the sign and magnitude without changing the real-arithmetic coordinate.
- **H-intrinsic:** as `r -> 0` with nonzero conjugate `g`, the tangential
  geometric Hessian contribution `g/r (I-n n^T)` becomes intrinsically large
  or singular.  The high-precision oracle will show the same growth.
- **H-both:** avoidable arithmetic loss occurs before an independently
  confirmed intrinsic boundary.

The objective is not to make inherited red rows green.  Every failure is first
classified as arithmetic, intrinsic, both, or inconclusive.

## 3. Frozen arithmetic control

Path A uses the exact accepted C++ operation sequence and the accepted
independent binary64 reconstruction.  The following fingerprint is mandatory:

1. Octahedron policies `K/G={1/3,2,10}` fail the registered one-ULP adjacency
   predicate at `r/l0=1`.
2. Octahedron policies `K/G={1/3,2,10}` and K4 `K/G=1/3` have a classification
   disagreement/unresolved tangent at `r/l0=2^-32`.
3. Every exact-coincidence path returns no energy, force, direction, or tangent.

No candidate result is evaluated if this gate fails.

## 4. Candidate operation sequences

All paths consume identical binary64 endpoint bit patterns.

- **A:** frozen endpoint subtraction, scaled norm, direct norm subtraction.
- **B:** binary64 endpoint differences plus explicit error-free/compensated
  primitives and FMA residuals for the squared-distance difference, followed by
  the positive-denominator rationalized extension.  Its exact operation order
  is part of the source and evidence.
- **C:** deterministic double-double endpoint subtraction, squared norm,
  square root, extension, and direction.  High/low words are transient.
- **D:** independent Python high-precision arithmetic at 120 decimal digits,
  reconstructed from uint64 binary64 encodings.  It is ineligible.

If B passes every registered gate, C cannot be retained merely for smaller
diagnostic error.  C is retained only if B fails a registered gate and C passes
it without changing the physical model.

## 5. Ordinary-scale adjacency inventory

For each of the three octahedron constitutive policies, freeze the parent
configuration and relation index zero.  Apply semantic perturbations

```text
{-4,-2,-1,+1,+2,+4} binary64 ULPs
```

to the same registered endpoint coordinate chosen by the frozen producer, with
all other endpoint and graph values bit-identical.  Both signs are explicit;
no `nextafter` loop may silently skip zero or change axes.

For every perturbed state the oracle first records whether the exact length of
the exact binary64 endpoints differs from the reference and from every adjacent
registered state.  A selectable path passes a distinguishable/output-eligible
row only if:

- the extension sign matches the oracle;
- the extension is nonzero whenever the correctly rounded binary64 oracle
  extension is nonzero;
- the exact length ordering is exposed by the evaluator's stateless order
  classification, even if the rounded binary64 length field aliases;
- binary64 length and extension are each within four ulps of their separately
  rounded oracle values (zero is compared by exact sign and output eligibility);
- each direction component is within eight ulps or `64*epsilon64` relative
  error, whichever is larger; and
- the complete force remains inside the inherited energy-gradient bound.

The registered representable-output floor for a scalar is round-to-nearest-even
binary64: a nonzero exact result is output-eligible exactly when its correctly
rounded binary64 value is nonzero.  No tolerance may turn an output-eligible
nonzero result into zero.

## 6. Collapse and conditioning inventory

For K4 and octahedron at `K/G={1/3,2,10}`, use relation index zero and ratios

```text
registered: 1, 2^-4, 2^-8, 2^-12, 2^-16, 2^-20, 2^-24, 2^-28, 2^-32
diagnostic: 2^-36, 2^-40, 2^-44, 2^-48
```

Each path exports exact input bits, oracle and computed length, extension,
direction, energy, conjugate, packet force, material/geometric/total tangent,
non-rigid singular spectrum, condition estimate/classification, one-ULP
coordinate sensitivity, and forward error.

The high-precision tangent is assembled from the unchanged `H` and exact
high-precision geometry.  Intrinsic deterioration is recorded when its
geometric norm or non-rigid condition grows consistently with decreasing
radius and the same failure/classification persists in high precision.  Extra
precision is not credited with repairing that result.

The inherited singular-value classifier remains a cross-check.  The new oracle
also records all non-rigid singular values directly so an algorithmic
resolved/unresolved label cannot conceal the physical `1/r` trend.

## 7. Forward-error and identity gates

For selectable paths:

- length and extension use the four-ulp gates in section 5;
- direction uses the eight-ulp/`64*epsilon64` component gate;
- energy, force covariance, conservation, power, tangent decomposition, and
  symmetry retain the force lab's registered dimension-scaled tolerances;
- a high-precision directional derivative must satisfy relative `1e-40` or
  absolute `1e-50` after the inherited dimensional normalization; and
- a row with a nonfinite selectable output, wrong sign/order, unexplained zero,
  classifier disagreement, or failed one-ULP behavior is unresolved.

No aggregate score is used.  Every required predicate must pass.

## 8. Mechanical safe-domain rule

The safe-domain selection rule is fixed before candidate results:

1. Evaluate the ratios in descending order from `1` through `2^-48`.
2. A ratio passes only if every graph/policy row passes length, extension,
   direction, force, energy-gradient, finite tangent, condition
   classification, oracle agreement, and one-ULP sensitivity gates.
3. Passing ratios must form a contiguous prefix.  Any lower pass after a
   failure is diagnostic only and cannot reopen the domain.
4. Let `r_fail` be the first failing ratio and `r_pass` the immediately higher
   registered ratio.  Set `rho_min` to one additional four-bit sweep step above
   `r_pass`.  This is the mandatory safety margin.
5. If the first failure is `1`, no tested safe domain exists.  If all ratios
   through `2^-48` pass, set `rho_min=2^-44`, retaining one registered sweep
   step of margin to the tested floor.

Example only: first failure at `2^-32` implies last passing ratio `2^-28` and a
declared `rho_min=2^-24`, not `2^-28`.

## 9. Regression inventory

For every surviving selectable path, rerun bounded instances of:

- `f=-grad U`;
- total internal force and torque about two origins;
- virtual power;
- translation and proper-rotation covariance;
- registered uniform scaling;
- packet-ID bijection and packet/relation permutations; and
- relation endpoint reversal.

These are regressions on accepted physics.  They cannot expand the claim.

## 10. Independent implementation and mutations

The oracle reads uint64 encodings and never treats decimal rendering as source
arithmetic.  It separately implements A, the selectable candidate, and D.
Mutation tests must reject at least:

- direct norm subtraction substituted into B;
- modified `H` or reference endpoint bits;
- epsilon clamping or fabricated direction;
- hidden repulsion or force/tangent caps;
- reversed/incorrect endpoint handling;
- persisted double-double packet state; and
- an intrinsic-conditioning result relabeled as an arithmetic pass.

## 11. Formal boundary

Lean work is limited to exact mathematics:

- `sqrt(a)-sqrt(b)=(a-b)/(sqrt(a)+sqrt(b))` under explicit nonnegative and
  positive-denominator assumptions;
- the corresponding squared-distance relation-extension identity;
- preservation of inherited central-force force/torque and virtual-work
  theorems; and
- if tractable, radial/tangential Hessian decomposition away from zero with all
  differentiability assumptions stated.

No claim of binary64 verification is made without an actual floating-point
proof.

## 12. Decision order

Apply the first matching outcome:

1. `stop_inconclusive_or_wrong_parent` if Path A or immutable identity fails.
2. `reject_current_relation_geometry_arithmetic` if the oracle distinguishes an
   output-eligible ordinary-scale state but every bounded candidate aliases it.
3. Retain B if it passes all gates; do not escalate precision.
4. `retain_transient_extended_relation_geometry_for_research` only if B fails
   and C passes.
5. Record `intrinsic_collapse_domain_boundary_confirmed` wherever the oracle
   confirms the near-zero deterioration.
6. Record `retain_relation_geometry_with_explicit_safe_domain_for_research`
   only if one selectable path passes and section 8 produces `rho_min`.

Every outcome remains **NO PROMOTION TO DYNAMICS** and the lab stops after its
evidence is sealed and publicly reverified.
