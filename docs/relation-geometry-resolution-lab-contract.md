# Relation Geometry Resolution Lab contract

## Status and boundary

This is a bounded, read-only numerical experiment rooted at the accepted
Conservative Force Consistency source commit
`7ee2555521b2c3a86ece87fad961500e413244c5` and immutable evidence tag
`conservative-force-consistency-lab-evidence-v1`.

The experiment asks whether the accepted central-distance force can be
evaluated reliably from binary64 packet coordinates, and where that force
geometry becomes intrinsically ill-conditioned as relation length approaches
zero.  It is **NO PROMOTION TO DYNAMICS**.  It installs no force in `World`,
advances no clock, and creates no authoritative evolution path.

## Frozen scientific inputs

The following are inherited without reselection or repair:

- Candidate-C central-distance relation topology and endpoint identities;
- reference packet coordinates and reference relation lengths;
- the accepted local collective energy and symmetric `H_force`;
- relation extension `e_a=|r_a|-l0_a`;
- energy `U=(1/2)e^T H e`, conjugate `g=H e`, and central force assembly
  `f_i=+g_a n_a`, `f_j=-g_a n_a`;
- every registered graph, constitutive policy, coefficient, weight, seed, and
  semantic mapping inherited from the force evidence.

The accepted force result already establishes the energy gradient,
force/torque cancellation, virtual-power identity, objectivity, finite tangent
consistency, and label/order invariance on its resolved noncoincident domain.
Those claims are regression gates here, not selection criteria for a new force
law.

## Allowed numerical object

A selectable relation-geometry evaluator is a deterministic, stateless
function of:

1. the four binary64 endpoint positions for the reference and current
   relation;
2. the frozen binary64 reference length recorded by the accepted operator; and
3. an explicitly named arithmetic path.

It may return only transient relation geometry: offset diagnostics, current
length, extension, unit direction, an exact-sign/order classification, and
error/status metadata.  It may not read velocities, time, prior evaluations,
packet history, checkpoint-private state, or any semantic material label.

All selectable paths return ordinary binary64 physical outputs.  A path may
use bounded multiword intermediates, but those intermediates are not packet or
relation state and are never serialized into an authoritative checkpoint.

## Registered paths

### A — frozen binary64 control

This is the accepted operation sequence: binary64 endpoint subtraction,
scaled binary64 norm, direct subtraction of the two rounded norms, and three
binary64 direction divisions.  It is a negative/control path and is not a
candidate repair.

### B — cancellation-resistant binary64

This path preserves the same real-arithmetic distance coordinate.  It uses an
audited, fixed-order binary64/FMA computation of the squared-distance
difference and evaluates

```text
|r|-|r0| = (r.r-r0.r0)/(|r|+|r0|)
```

when the denominator is positive.  The numerator evaluation must expose the
sign of distinguishable endpoint-bit perturbations instead of first collapsing
them through direct norm subtraction.  No compiler-dependent excess precision,
ambient rounding mode, or implicit contraction is part of this path.

### C — transient extended relation geometry

This path may use deterministic double-double/multiword arithmetic for
endpoint subtraction, squared norm, square root, extension, and direction.  It
rounds declared physical outputs to binary64 and exposes any retained low word
only as ineligible diagnostic evidence.  No multiword value may enter a
checkpoint or a later evolution step.

### D — independent high-precision oracle

The oracle reconstructs the exact values of exported binary64 coordinate bit
patterns and evaluates them at no less than 100 decimal digits.  It is
separately implemented and permanently ineligible for selection.

## Domain and failure behavior

Exact coincidence remains outside the force domain.  Every selectable path
must return a deterministic, output-empty `coincident_relation` failure before
force or tangent assembly.  A nonfinite input or nonfinite intermediate is a
hard numerical failure; it is never converted to coincidence or a finite
fallback.

The experiment may establish a dimensionless safe domain

```text
r/l0 >= rho_min > 0
```

only by the mechanical rule fixed in the preregistration.  The domain applies
to the accepted force evaluator using the selected geometry path.  It is not a
contact model, a collapse model, or permission to integrate time.

## Forbidden repairs

This branch may not introduce epsilon-normalized directions, clamped lengths,
force or tangent caps, artificial repulsion, diagonal shifts, hidden
regularization, relation deletion, contact, fracture, topology mutation,
altered `H`, rebuilt constitutive coefficients, persistent high-precision
positions, or time integration.  Any such mechanism changes the physical
model and requires a separate authorized experiment.

## Evidence and determinism

Evidence inputs serialize all binary64 values by their exact 64-bit patterns;
human-readable decimal text is diagnostic only.  Candidate implementations,
the high-precision oracle, and the validator remain separate.  Twin runs must
be byte-identical after provenance fields fixed by the evidence schema are
held constant.  Failed attempts are preserved and may not be rewritten into a
passing lineage.

