# Phase-Space/Time Co-Refinement Lab result

## Disposition

```text
decision: reject_order_matched_space_time_corefinement
candidate: order_matched_space_time_corefinement
base representation: R=128
authoritative integer width: signed64
remainder state: none
World integration: none
promotion: NO_PROMOTION
```

The proposed co-refinement fixes the isolated primitive-momentum drift scale,
and it restores the expected second-order KDK window for the initially static
K4 breathing and octahedron cases.  It does **not** restore convergence for the
generic internal-velocity case.  The fixed decision order therefore stops at
`reject_order_matched_space_time_corefinement`.

The new diagnostics localize the surviving obstruction more sharply than the
parent lab: once evolving relation-coordinate triples become primitive, exact
central relation impulses lie on a lattice that becomes physically coarser,
not finer, under the tested unit family.  This is not evidence against smooth
Störmer-Verlet and it is not repaired by the authorized stateless unit scaling.

## Parent and exact-unit fingerprints

A detached checkout of `time-integration-foundation-lab-evidence-v1` reproduced
the sealed fixed-`R=128` twins, negative oracle decision, twenty mutations,
internal-velocity plateau, exact invariants/reversibility, frame diagnostic,
and secular energy classification.  Candidate level zero matches all 28 parent
initial-state rows and all 20 parent reference rows.  The complete relation and
force-operator payloads match their accepted parent hashes.

All five exact rational unit profiles satisfy

```text
Mq[k] = Mq[0]
Tq[k] = Tq[0] / 2^(3k)
Lq[k] = Lq[0] / 2^(6k)
Pq[k] = Pq[0] / 2^(3k)
Eq[k] = Eq[0] / 2^(6k)
Fq[k] = Fq[0]
```

together with `Fq*Tq=Pq`, `Eq=Pq^2/Mq`, and raw ballistic factor one.

## Independent trajectory result

The independent 110-digit oracle reused the accepted potential from exact
binary64 coordinate/operator bit patterns.  Its two refinements differed by:

| scenario | independent-oracle refinement difference |
|---|---:|
| K4 breathing | `1.79656855064857e-34` |
| K4 internal velocity | `1.80029147550743e-34` |
| octahedron deformation | `2.39542473419810e-34` |

Candidate endpoint errors and observed orders for physical timesteps
`1/16,...,1/256` were:

| scenario | five endpoint errors | four observed orders |
|---|---|---|
| K4 breathing | `1.32110e-6, 3.61108e-7, 8.68894e-8, 2.15670e-8, 5.57231e-9` | `1.871, 2.055, 2.010, 1.952` |
| K4 internal velocity | `1.27317e-3, 1.31023e-3, 1.32881e-3, 1.33813e-3, 1.34279e-3` | `-0.041, -0.020, -0.010, -0.005` |
| octahedron deformation | `1.76148e-6, 4.81478e-7, 1.15853e-7, 2.87560e-8, 7.42975e-9` | `1.871, 2.055, 2.010, 1.952` |

The first-order control remains approximately first order for breathing and
octahedron.  Its internal-velocity path is lattice-blocked as well.  The
required three-halving second-order window therefore fails on the decisive
generic scenario.

## Causal primitive-lattice diagnosis

The maximum minimum nonzero drift magnitude in the internal-velocity case
decreases as intended:

```text
6.00272e-7, 7.37300e-8, 9.19050e-9, 1.14881e-9, 1.43403e-10 m
```

This is approximately an eightfold improvement per level and falsifies the
claim that the old drift quantum necessarily remains the active blocker.

The relation-kick evidence points the other way.  Out of respectively
`288, 576, 1152, 2304, 4608` internal-velocity relation-kick rows,
`276, 564, 1140, 2292, 4596` had a nonzero requested scalar multiple round to
zero.  Only twelve relation kicks per level were nonzero.  The maximum minimum
nonzero physical central impulse grew as:

```text
96.4503, 15283.8, 122273, 345776, 1383104 kg m/s
```

For a generic raw relation vector with gcd one, `Lq = O(h^6)` makes its integer
magnitude `O(h^-6)`, while `Pq = O(h^3)`.  The minimum exact-central impulse can
therefore scale as `O(h^-3)`.  Co-refining the momentum lattice is insufficient
when exact orbital angular momentum restricts the applied impulse to the
primitive raw relation direction.  The experiment thus exposes a structural
central-kick counterpart to the parent's primitive-drift obstruction.

## Invariants, frame, width, and energy

Every representable bridge row passed.  All evaluated trajectories preserved
literal total momentum and orbital angular momentum and recovered their initial
state bit-for-bit under signed-time reversal.  Checkpoint/resume, event suffix,
proper lattice rotation, atomic domain rejection, and translation before the
width limit were exact.  The registered Galilean relative-motion discrepancies
were exactly zero at every level.

The translated K4 reference exceeds signed-64 position range at level four,
after the expected `2^24` raw-position growth.  It fails closed and is preserved
as a real fixed-width limitation, but all three decisive convergence scenarios
remain representable through level four; width therefore does not precede the
scientific rejection.

Short KDK energy envelopes recover second-order behavior for breathing and
octahedron.  Internal-velocity envelopes worsen from `2.01134e-7` to
`5.03440e-7` J.  Over sixteen seconds, maximum/final error changes only from
`2.81572e-4` to `2.74640e-4` J.  The least-squares slope per physical second is
nearly refinement independent:

```text
1.76037e-5, 1.73605e-5, 1.72281e-5, 1.71871e-5, 1.71694e-5 J/s
```

Its contraction orders fall from about `0.020` toward `0.0015`, so the energy
gate independently records a nonconvergent secular bias.  The earlier temporal
gate remains the authoritative disposition under the preregistered order.

## Independent, mutation, and formal validation

The oracle independently anchors accepted physics and exact level-zero state,
recomputes all integer invariants/gcds with unbounded integers, and detects 33
mutations.  The suite covers unit exponents and derived-unit inconsistencies,
hidden refinement/width/remainders, changed `H`, reference coordinates,
relation orientation, false overflow/order/boost/reversibility/invariant/domain
claims, omitted primitive evidence, altered traces, and checkpoint divergence.

Lean proves the exact integer primitive-direction obstruction under an explicit
Bézout witness, its minimum nonzero squared-displacement consequence, the
gcd-one physical drift identity, and the order-matched raw ballistic identity.
It introduces no project axioms or proof placeholders and makes no binary64,
finite-width, empirical-order, or symplectic claim.

## Promotion boundary

The accepted single-operation force, impulse, and drift results remain intact.
This negative experiment shows that the tested stateless integer Cartesian
phase-space architecture does not recover generic second-order dynamics under
the authorized order-matched unit family.  No further exponent tuning, wider
integer state, or hidden accumulation is authorized here.

The next scientifically motivated question is an explicitly authorized
fractional phase-state experiment, but it must begin only after review of this
sealed result.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
