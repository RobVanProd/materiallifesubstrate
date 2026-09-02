# Phase-Space/Time Co-Refinement Lab contract

## Scope

This laboratory tests one causal hypothesis raised by the sealed Time
Integration Foundation Lab: whether its failed repeated dynamics came from
holding the authoritative lattice fixed while the timestep was refined.  It
does not compare integrator families, add fractional/remainder state, change
the accepted force, or install dynamics in `World`.

The frozen parent is source
`243d52938ef22f7bf37e4e37decbe209bec504cf`, evidence tag
`time-integration-foundation-lab-evidence-v1`, and tag object
`855e89d86fa0192f7cd24a9743e545f588335c44`.  The accepted force domain remains
`r/l0 >= 2^-24` and the base representation remains `R=128`.

## Exact unit family

Each trajectory uses one immutable unit profile.  Across timestep levels
`k=0,...,4`, the candidate derives every quantum from

```text
Mq[k] = Mq[0]
Tq[k] = Tq[0] / 2^(3k)
Lq[k] = Lq[0] / 2^(6k)
Pq[k] = Pq[0] / 2^(3k)
Eq[k] = Eq[0] / 2^(6k)
Fq[k] = Fq[0]
```

The raw ballistic factor remains exactly one, `Fq*Tq=Pq`, and
`Eq=Pq^2/Mq`.  Co-refinement occurs only between complete experiments; no
trajectory changes representation while running.

Authoritative position, momentum, mass, and time remain signed 64-bit
integers.  Wider signed-magnitude scratch values may compute read-only exact
invariant and kinetic diagnostics, but are never checkpointed or treated as
state.  A state that cannot be represented in signed 64-bit integers fails
closed.

## Frozen time map and physics

The candidate is the parent's signed kick-drift-kick map, using the accepted
cancellation-resistant binary64 relation geometry, symmetric `H_force`,
stateless primitive-central impulse quantization, and stateless
primitive-momentum drift.  The first-order splitting remains an ineligible
diagnostic control.  Initial and complete drift-chord force-domain checks retain
the parent's atomic transaction semantics.

The level-zero reference geometry and initial conditions are compared field by
field with freshly reproduced parent evidence.  The relation topology,
orientation, rest lengths, and complete force operator are byte-anchored to the
parent scientific payload.

## Required evidence

The three parent convergence scenarios and their independent 110-decimal-digit
smooth ODE targets are reused without extension.  Three consecutive timestep
halvings must give candidate order in `[1.6,2.4]`; the first-order control must
remain distinguishable.

Every kick and drift exports the momentum gcd, primitive direction, primitive
norm, and minimum exact-angular-momentum drift.  Every relation kick also
exports the raw separation gcd, primitive central direction, requested scalar
multiple, nearest-even applied multiple, and minimum nonzero physical impulse.

At every representable level the single-operation bridge contracts, exact
total momentum, exact orbital angular momentum, signed-time recovery,
checkpoint replay, atomic domain rejection, proper lattice rotation, and
translation gates are rerun.  Galilean relative-motion discrepancies must
converge away or be at the exact lattice floor.

The short energy envelope and sixteen-second diagnostic remain nonphysical
observations only.  Maximum excursion, final error, and least-squares slope per
physical second must enter a three-halving second-order contraction window.
The per-sample slope is retained for audit but cannot substitute for the
physical-time slope as the sample interval changes.

## Formal and promotion boundaries

Lean proves an integer parallel-vector result under an explicit Bézout
primitiveness witness, the resulting minimum nonzero squared displacement,
the gcd-one physical drift identity, and the exact raw ballistic unit identity.
It proves no finite-width safety, floating-point accuracy, empirical
convergence, or symplectic property.

Even a positive outcome would retain only an experimental representation for
research.  This lab does not authorize fractional state, an integrator-family
comparison, or authoritative dynamics.

**NO PROMOTION TO AUTHORITATIVE WORLD DYNAMICS.**
