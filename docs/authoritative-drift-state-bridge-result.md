# Authoritative Drift State Bridge Lab result

## Disposition

```text
decision: retain_refined_stateless_mechanics_representation_for_research
selected path: primitive_directional
selected coherent representation: R=128
explicit position remainder evaluated: no
force integration: none
promotion: NO_PROMOTION
```

The lab retains a stateless primitive-momentum directional drift evaluator for
research.  The accepted mechanics representation must be coherently refined
from `R=16` to `R=128` for the combined impulse-plus-drift bridge.  This changes
resolution only; the represented SI state and the accepted force, energy, and
kinetic laws are unchanged.

## Parent fingerprint

The inherited authoritative ballistic transition was called directly.  The
registered exactly divisible packet advanced by one raw length quantum.  The
registered nonintegral packet threw `std::domain_error` without changing its
physical-state hash, `Tick`, or physical time.  Thus the experiment reproduces
the accepted exact-pass/fractional-reject parent rather than a reconstructed
surrogate.

## Candidate result

Cartesian component rounding is rejected.  Across the registered corpus it
produced 514 rows with resolved nonzero
`Delta L = displacement x momentum`.  The primitive-directional evaluator
instead writes nonzero integer momentum as `p=g*u`, rounds only `g*dt/m`, and
applies the resulting integer multiple of `u`.

All 1,008 directional rows had exactly unchanged momentum, mass, integer kinetic
energy, and orbital angular momentum.  No rounding residual entered heat,
stored, structural, or any other energy.  The equal-exact-velocity packet pair
received identical displacement at every registered refinement, horizon, and
subdivision.

## Refinement selection

The exact-rational oracle evaluated 2,016 total rows over eight coherent
refinements, three horizons, six subdivision counts, seven packets, and two
paths.  Errors below are in the base physical length quantum `Lq=10^-9 m`.

| R | max component error | max vector error squared | max component spread | max vector spread squared | max COM component error | pass |
|---:|---:|---:|---:|---:|---:|:---:|
| 16 | `224/41` | `84992/1681` | `7` | `83` | `2` | no |
| 32 | `98/41` | `16268/1681` | `7/2` | `83/4` | `23/21` | no |
| 64 | `63/41` | `6723/1681` | `7/4` | `83/16` | `199/336` | no |
| 128 | `28/41` | `1328/1681` | `7/8` | `83/64` | `61/224` | **yes** |

`R=16`, `R=32`, and `R=64` fail at least one preregistered component/vector
error or spread bound.  `R=128` is the first profile satisfying all six drift
bounds.  The full accepted K4 impulse corpus was rerun at every fallback
refinement; exact momentum/orbital identities, the inherited impulse error and
subdivision bounds, and the shrinking kinetic-floor bound all pass at `R=128`.

The coherent selected quanta are therefore:

```text
Lq(128) = 1 / 128,000,000,000 m
Mq(128) = 1 / 524,288 kg
Tq      = 1 / 1,000,000,000 s
Pq(128) = 1 / 67,108,864 kg m s^-1
Eq(128) = 1 / 8,589,934,592 J
Fq(128) = 1,953,125 / 131,072 N.
```

## Overflow and force-domain controls

The largest registered safe signed-64-bit displacement product was accepted.
Its adjacent product was rejected before rounding; no wrap occurred.

The exact chord oracle classified the ordinary safe chord as admissible, an
interior zero crossing as a force-domain event, and an endpoint at ratio
`2^-25` as below the retained `2^-24` boundary.  No endpoint was clipped or
moved.  This is a regression for a future dynamics contract, not a stepper.

## Remainder disposition

Candidate C was not opened because a bounded stateless coherent refinement
passes.  `PositionRemainder3` remains unactivated and semantically unchanged.
There is no hidden numerical memory, checkpoint field, replay input, or
subquantum physical-position claim in the selected evaluator.

## Independent and formal validation

The independent Python oracle reconstructs all integer inputs, signed rational
nearest-even decisions, refinement mappings, displacements, errors, cross
products, center-of-mass translations, exact chord minima, and selection gates.
It rejects 14 registered mutations, including Cartesian rounding disguised as
directional, changed gcd/sign/mass/momentum/units, half-away ties, hidden energy
mutation, omitted torque, false equal-velocity results, overflow acceptance,
force-domain relabeling, false coarser selection, altered inherited impulse, and
wrong parent identity.

Lean proves the exact force-free momentum identity, scalar-along-momentum and
primitive-direction orbital identities, and coherent raw refinement identity.
It makes no floating-point, empirical error, or time-integration claim.

## Promotion boundary

This result defines a read-only mapping from fixed authoritative momentum to a
prescribed displacement.  It does not connect accepted force to repeated
impulse and drift updates and does not authorize `World` motion under force.

**NO PROMOTION TO DYNAMICS.**
